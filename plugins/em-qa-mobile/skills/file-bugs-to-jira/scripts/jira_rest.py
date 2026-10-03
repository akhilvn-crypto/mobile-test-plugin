#!/usr/bin/env python3
"""Jira REST fallback for what the Atlassian connector cannot do: the assignable-user list and, for mobile bugs,
uploading attachments (screenshots, MP4 recordings, device log excerpts). Without the REST settings nothing is
uploaded and the user attaches the files by hand (as for web bugs).

Settings (optional) in .env or mobile-automation/.env, both git-ignored:  JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN.
The token is read from there only; it is never printed, logged or written anywhere else.

  python jira_rest.py check                         -> {configured, missing[], auth_ok, user, site_matches}
  python jira_rest.py assignable --project PROJ     -> [{accountId, displayName}] (people who can be assigned)
  python jira_rest.py limit                         -> {enabled, upload_limit_bytes} (the site's attachment settings)
  python jira_rest.py attach --key PROJ-45 --file <path> [--file <path> ...]
                                                    -> {attached: [{file, id, size}], failed: [{file, error}]}

Exit 1 when something failed; the JSON says what and why (HTTP status and Jira's own message, never the token).
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import SYNC_FILE, dump, find_root, read_env, utf8_stdio  # noqa: E402
import sync_state  # noqa: E402

VARS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


class Jira:
    def __init__(self, env):
        self.base = env["JIRA_BASE_URL"].rstrip("/")
        raw = f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()
        self._auth = "Basic " + base64.b64encode(raw).decode()

    def call(self, method, path, body=None, headers=None, timeout=120):
        h = {"Authorization": self._auth, "Accept": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                return r.status, (json.loads(data) if data else None)
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                j = json.loads(e.read() or b"{}")
                msg = "; ".join((j.get("errorMessages") or []) + [f"{k}: {v}" for k, v in (j.get("errors") or {}).items()])
            except (ValueError, OSError):
                pass
            return e.code, {"error": msg or e.reason}
        except (urllib.error.URLError, OSError) as e:
            return 0, {"error": f"connection failed: {getattr(e, 'reason', e)}"}

    def get(self, path):
        return self.call("GET", path)


def settings():
    env = read_env(".env")  # also reads mobile-automation/.env
    for k in VARS:  # the process environment may also carry them
        if not env.get(k) and os.environ.get(k):
            env[k] = os.environ[k]
    missing = [k for k in VARS if not env.get(k)]
    return env, missing


def client_or_exit():
    env, missing = settings()
    if missing:
        dump({"ok": False, "configured": False, "missing": missing,
              "error": "The Jira REST settings are not in .env (" + ", ".join(missing) + ")."}, code=1)
    return Jira(env)


def cmd_check(a):
    env, missing = settings()
    if missing:
        dump({"ok": True, "configured": False, "missing": missing})
        return
    j = Jira(env)
    st, me = j.get("/rest/api/3/myself")
    out = {"ok": st == 200, "configured": True, "missing": [], "auth_ok": st == 200, "base_url": j.base}
    if st != 200:
        out["error"] = f"HTTP {st}: {(me or {}).get('error', '')}".strip()
        dump(out, code=1)
    out["user"] = me.get("displayName")
    site = (sync_state.load(SYNC_FILE).get("site") or "").rstrip("/")
    out["site_matches"] = (not site) or site.lower() == j.base.lower()
    dump(out)


def cmd_limit(a):
    j = client_or_exit()
    st, meta = j.get("/rest/api/3/attachment/meta")
    if st != 200:
        dump({"ok": False, "error": f"HTTP {st}: {(meta or {}).get('error', '')}"}, code=1)
    dump({"ok": True, "enabled": bool(meta.get("enabled")), "upload_limit_bytes": meta.get("uploadLimit")})


def _multipart(path):
    import mimetypes
    import uuid
    boundary = "----qa" + uuid.uuid4().hex
    name = os.path.basename(path)
    ctype = mimetypes.guess_type(name)[0] or ("video/mp4" if name.lower().endswith(".mp4") else
                                              "text/plain" if name.lower().endswith((".txt", ".log")) else
                                              "application/octet-stream")
    with open(path, "rb") as f:
        data = f.read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def cmd_attach(a):
    j = client_or_exit()
    out = {"ok": True, "key": a.key, "attached": [], "failed": []}
    for path in a.file:
        if not os.path.isfile(path):
            out["failed"].append({"file": path, "error": "file not found"})
            continue
        body, ctype = _multipart(path)
        st, res = j.call("POST", f"/rest/api/3/issue/{urllib.parse.quote(a.key)}/attachments", body=body,
                         headers={"X-Atlassian-Token": "no-check", "Content-Type": ctype}, timeout=600)
        if st == 0 or st >= 300:  # one retry
            st, res = j.call("POST", f"/rest/api/3/issue/{urllib.parse.quote(a.key)}/attachments", body=body,
                             headers={"X-Atlassian-Token": "no-check", "Content-Type": ctype}, timeout=600)
        if 200 <= st < 300 and isinstance(res, list) and res:
            out["attached"].append({"file": path, "id": res[0].get("id"), "size": res[0].get("size")})
        else:
            out["failed"].append({"file": path, "error": f"HTTP {st}: {(res or {}).get('error', '') if isinstance(res, dict) else ''}"})
    out["ok"] = not out["failed"]
    dump(out, code=0 if out["ok"] else 1)


def cmd_assignable(a):
    j = client_or_exit()
    users, start = [], 0
    while True:
        st, page = j.get(f"/rest/api/3/user/assignable/search?project={urllib.parse.quote(a.project)}"
                         f"&startAt={start}&maxResults=100")
        if st != 200:
            dump({"ok": False, "error": f"HTTP {st}: {(page or {}).get('error', '')}"}, code=1)
        users += [{"accountId": u.get("accountId"), "displayName": u.get("displayName")}
                  for u in page or [] if u.get("active", True) and u.get("accountType", "atlassian") == "atlassian"]
        if len(page or []) < 100 or start > 900:
            break
        start += 100
    dump({"ok": True, "project": a.project, "users": users})


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check").set_defaults(fn=cmd_check)
    p = sp.add_parser("assignable")
    p.add_argument("--project", required=True)
    p.set_defaults(fn=cmd_assignable)
    sp.add_parser("limit").set_defaults(fn=cmd_limit)
    p = sp.add_parser("attach")
    p.add_argument("--key", required=True)
    p.add_argument("--file", action="append", required=True)
    p.set_defaults(fn=cmd_attach)
    a = ap.parse_args()
    find_root()
    a.fn(a)


if __name__ == "__main__":
    main()
