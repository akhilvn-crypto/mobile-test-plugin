#!/usr/bin/env python3
"""Wording and safety lint for everything a human reads: bug reports, the test report, Actual Result text
(execute-mobile-test-cases; web bugs in the shared bugs/ folder keep the web rules).

  python lint_human_text.py [--bugs bugs] [--report "<report.md>" ...] [--testcase "<test cases .md>"]
                            [--env .env] [--terms <banned-terms.txt>] [--json]

Checks
- Banned machine/tool terms from assets/banned-terms.txt (whole words, case-insensitive; "re:" lines are
  regexes). In a bug's "Insights for Developers" section, text inside double quotes is exempt (console and
  server messages are quoted exactly as the app produced them).
- Secrets: any password/token/key value from .env, password/token assignments, Bearer tokens, JWTs.
- Bugs: H1 "# BUG-NNN: <title>", the field table (Severity, Priority, Status, Test case(s), Reported on),
  every section of the template, steps written as user actions, a screenshot in screenshots/, listed
  attachments that exist, unique titles across bugs, matching folder and file names.
  Mobile bugs (a Platform row of Android or iOS) also need the Test case file and Jira rows, the mobile
  Environment lines (App, Device ... (real device), Operating system, Network, Screen, User/role) and a screen
  recording (MP4) in recordings/. Device log excerpts in logs/ must hold no secrets.
- Test report: front matter keys (project_id, document_id, approved_date empty), all sections, empty
  "Executed by" / "Overall testing by lead", no unfilled {{placeholders}}, at most 5 UX suggestions.
- Test cases: only the Actual Result cells (and Comments of executed cases) are checked.

Exit 1 when there is any ERROR.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_front_matter, parse_testcase_md, utf8_stdio  # noqa: E402

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TERMS = os.path.join(SKILL, "assets", "banned-terms.txt")

BUG_SECTIONS = ["Summary", "Description", "Steps to Reproduce", "Expected Result", "Actual Result", "Environment",
                "Insights for Developers", "Attachments"]
BUG_FIELDS = ["Severity", "Priority", "Status", "Test case(s)", "Reported on"]
MOBILE_BUG_FIELDS = ["Platform", "Test case file", "Jira"]
MOBILE_ENV_LINES = ["App:", "Device:", "Operating system:", "Network:", "Screen:", "User/role:"]
SEVERITIES = {"Critical", "Major", "Minor", "Trivial"}
PRIORITIES = {"High", "Medium", "Low"}
BUG_STATUSES = {"Open", "Fixed - verified", "Closed", "Closed in Jira", "Reopened", "In Progress", "Rejected"}
JIRA_FIELD_RE = re.compile(r"^(Not filed|\[[A-Z][A-Z0-9]+-\d+\]\(https?://\S+\))$")
REPORT_SECTIONS = ["Summary", "Results at a glance", "Results by test suite", "Defects raised",
                   "Blocked and unexecuted cases", "Observations", "UX suggestions"]
REPORT_KEYS = ["title", "document_type", "project_id", "document_id", "version", "approved_date", "privacy", "tags"]
ACTION_VERBS = ("open", "go to", "navigate", "enter", "type", "click", "tap", "select", "choose", "scroll", "press",
                "hover", "search", "log in", "sign in", "log out", "sign out", "fill", "clear", "check", "uncheck",
                "upload", "drag", "resize", "refresh", "reload", "wait for", "close", "switch", "submit", "add",
                "remove", "change", "set", "paste", "copy", "use", "repeat", "return", "move", "expand", "collapse",
                "note", "observe", "look", "read", "zoom", "rotate", "send", "call", "make", "create", "delete",
                "edit", "apply", "sort", "filter", "view", "start", "leave", "keep", "turn", "replace", "visit",
                "follow", "go back", "log", "swipe", "long press", "long-press", "minimise", "minimize", "reopen",
                "allow", "deny", "launch", "install", "uninstall", "put", "pull", "grant", "revoke", "unlock", "lock",
                "connect", "disconnect", "background", "bring", "double tap", "pinch", "type", "dismiss")
SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_ -]?key|token)\b\s*[:=]\s*(?!\*{3,}|<[^>]+>|\[)(\S{4,})"),
     "looks like a credential value"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]{12,}"), "bearer token"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "JWT token"),
]


class Lint:
    def __init__(self):
        self.items = []

    def add(self, level, path, line, msg):
        self.items.append({"level": level, "file": path, "line": line, "msg": msg})

    @property
    def errors(self):
        return sum(1 for i in self.items if i["level"] == "ERROR")


def load_terms(path):
    terms = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            t = raw.strip()
            if not t or t.startswith("#"):
                continue
            if t.startswith("re:"):
                terms.append((re.compile(t[3:], re.I), t[3:]))
            else:
                terms.append((re.compile(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", re.I), t))
    # longest first, so "test runner" is reported instead of "runner"
    return sorted(terms, key=lambda x: -len(x[1]))


def load_env_secrets(path):
    """Secrets from the given .env and from mobile-automation/.env (the mobile framework's own file)."""
    strong, weak = [], []
    paths = [x for x in dict.fromkeys([path, os.path.join("mobile-automation", ".env"), ".env"]) if x and os.path.exists(x)]
    lines = []
    for one in paths:
        with open(one, encoding="utf-8") as f:
            lines += f.read().split("\n")
    for line in lines:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not m or not m.group(2):
            continue
        k, v = m.group(1).upper(), m.group(2).strip().strip("\"'")
        if len(v) < 4:
            continue
        if re.search(r"PASS|SECRET|TOKEN|KEY|PWD|PIN|OTP", k):
            strong.append((k, v))
        elif re.search(r"USER|EMAIL|LOGIN", k):
            weak.append((k, v))
    return strong, weak


def strip_jira(text):
    """Jira keys and links are allowed everywhere: [PROJ-45](https://…), bare URLs and keys are not checked."""
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)\s]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\b[A-Z][A-Z0-9]+-\d+\b", " ", text)


def check_terms(lint, terms, path, line_no, text, where=""):
    text = strip_jira(text)
    found = set()
    for rx, term in terms:
        for m in rx.finditer(text):
            span = m.group(0).lower()
            if any(span in f for f in found):
                continue
            found.add(span)
            lint.add("ERROR", path, line_no, f"{where}machine term '{term}' – describe what the user sees instead")


def check_secrets(lint, env_strong, env_weak, path, lines):
    for i, line in enumerate(lines, 1):
        for rx, what in SECRET_PATTERNS:
            if rx.search(line):
                lint.add("ERROR", path, i, f"{what}: mask it (********)")
        for k, v in env_strong:
            if v in line:
                lint.add("ERROR", path, i, f"contains the value of {k} from .env – remove it")
        for k, v in env_weak:
            if v in line:
                lint.add("WARN", path, i, f"contains the value of {k} from .env – name the role instead")


def strip_quoted(text):
    return re.sub(r"\"[^\"]*\"|“[^”]*”", '""', text)


# ---------------------------------------------------------------- bugs

def sections(lines):
    out, cur = {}, None
    for i, l in enumerate(lines):
        m = re.match(r"^##\s+(.+?)\s*$", l)
        if m:
            cur = m.group(1).strip()
            out[cur] = [i + 1, []]
        elif cur:
            out[cur][1].append((i + 1, l))
    return out


def lint_bug(lint, terms, env, path, titles):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    folder = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    if os.path.basename(folder) != stem:
        lint.add("ERROR", path, 1, f"file name must match its folder ({os.path.basename(folder)})")
    h1 = next(((i + 1, l) for i, l in enumerate(lines) if l.startswith("# ")), None)
    if not h1 or not re.match(r"^# BUG-\d{3,}: .+ - .+", h1[1]):
        lint.add("ERROR", path, h1[0] if h1 else 1, "H1 must be '# BUG-NNN: <Feature> - <what is wrong>'")
    else:
        title = h1[1].split(":", 1)[1].strip().lower()
        if title in titles:
            lint.add("ERROR", path, h1[0], f"same title as {titles[title]} – duplicate bug?")
        titles[title] = os.path.basename(path)
        if not stem.startswith(h1[1][2:].split(":")[0]):
            lint.add("ERROR", path, h1[0], "bug ID in the H1 does not match the file name")
    fields = {}
    for l in lines[:25]:
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", l)
        if m and m.group(1) not in ("Field", "---"):
            fields[m.group(1)] = m.group(2)
    for k in BUG_FIELDS:
        if not fields.get(k):
            lint.add("ERROR", path, 1, f"field '{k}' missing or empty")
    if fields.get("Severity") and fields["Severity"] not in SEVERITIES:
        lint.add("ERROR", path, 1, f"Severity must be one of {sorted(SEVERITIES)}")
    if fields.get("Priority") and fields["Priority"] not in PRIORITIES:
        lint.add("ERROR", path, 1, f"Priority must be one of {sorted(PRIORITIES)}")
    if fields.get("Status") and fields["Status"] not in BUG_STATUSES:
        lint.add("WARN", path, 1, f"unusual Status '{fields['Status']}'")
    if fields.get("Jira") and not JIRA_FIELD_RE.match(fields["Jira"]):
        lint.add("ERROR", path, 1, "Jira must be 'Not filed' or a link like [PROJ-45](https://…/browse/PROJ-45)")
    mobile = fields.get("Platform", "").strip() in ("Android", "iOS")
    if "Platform" in fields and not mobile:
        lint.add("ERROR", path, 1, "Platform must be 'Android' or 'iOS'")
    if mobile:
        for k in MOBILE_BUG_FIELDS:
            if not fields.get(k):
                lint.add("ERROR", path, 1, f"field '{k}' missing or empty (mobile bug)")
    elif "Test case file" not in fields:
        lint.add("WARN", path, 1, "field 'Test case file' missing (needed to find the right test case file)")
    if fields.get("Reported on") and not re.match(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2} IST$", fields["Reported on"]):
        lint.add("ERROR", path, 1, "Reported on must be dd-mm-yyyy hh:mm:ss IST")
    secs = sections(lines)
    for s in BUG_SECTIONS:
        if s not in secs:
            lint.add("ERROR", path, 1, f"section '## {s}' missing")
        elif not any(l.strip() for _, l in secs[s][1]):
            lint.add("ERROR", path, secs[s][0], f"section '## {s}' is empty")
    for name, (start, body) in secs.items():
        for ln, l in body:
            check_terms(lint, terms, path, ln, strip_quoted(l))
    check_terms(lint, terms, path, h1[0] if h1 else 1, h1[1] if h1 else "")
    for ln, l in secs.get("Steps to Reproduce", [0, []])[1]:
        m = re.match(r"^\s*\d+[.)]\s*(.+)$", l)
        if m and not m.group(1).lower().startswith(ACTION_VERBS):
            lint.add("WARN", path, ln, "step should be a user action (Open, Enter, Click, Select, Scroll …)")
    shots = glob.glob(os.path.join(folder, "screenshots", "*.png")) + glob.glob(
        os.path.join(folder, "screenshots", "*.jp*g"))
    if not shots:
        lint.add("ERROR", path, 1, "no screenshot in screenshots/")
    if mobile:
        env_body = [l.strip().lstrip("-").strip() for _, l in secs.get("Environment", [0, []])[1] if l.strip()]
        for want in MOBILE_ENV_LINES:
            if not any(l.startswith(want) for l in env_body):
                lint.add("ERROR", path, secs.get("Environment", [1])[0], f"Environment line '{want} …' missing (mobile)")
        dev = next((l for l in env_body if l.startswith("Device:")), "")
        if dev and "(real device)" not in dev:
            lint.add("ERROR", path, secs.get("Environment", [1])[0], "Device line must end with '(real device)'")
        if not glob.glob(os.path.join(folder, "recordings", "*.mp4")):
            lint.add("ERROR", path, 1, "no screen recording (MP4) in recordings/")
        for lf in glob.glob(os.path.join(folder, "logs", "*")):
            if os.path.isfile(lf) and os.path.getsize(lf) < 5 * 1024 * 1024:
                with open(lf, encoding="utf-8", errors="replace") as fh:
                    check_secrets(lint, *env, lf, fh.read().split("\n"))
    for ln, l in secs.get("Attachments", [0, []])[1]:
        m = re.match(r"^\s*-\s*(\S.+?)\s*$", l)
        if m:
            target = re.sub(r"^\[.*?\]\((.*)\)$", r"\1", m.group(1))
            if not os.path.exists(os.path.join(folder, target)):
                lint.add("ERROR", path, ln, f"attachment not found: {target}")
    check_secrets(lint, *env, path, lines)


# ---------------------------------------------------------------- report

def lint_report(lint, terms, env, path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    fm, _ = parse_front_matter(text)
    for k in REPORT_KEYS:
        if k not in fm:
            lint.add("ERROR", path, 1, f"front matter key '{k}' missing")
    for k in ("project_id", "document_id", "approved_date"):
        if fm.get(k):
            lint.add("ERROR", path, 1, f"'{k}' must stay empty")
    if fm.get("document_type") and fm["document_type"] != "Test Report":
        lint.add("ERROR", path, 1, "document_type must be 'Test Report'")
    if fm.get("privacy") and fm["privacy"] != "Confidential":
        lint.add("ERROR", path, 1, "privacy must be 'Confidential'")
    if fm.get("version") and not re.match(r"^V\d+\.\d+$", fm["version"]):
        lint.add("ERROR", path, 1, "version must look like V1.0")
    tags = fm.get("tags") or []
    if "test-report" not in tags or "qa" not in tags or not ({"web", "mobile"} & set(tags)):
        lint.add("ERROR", path, 1, "tags must be test-report, qa and web|mobile")
    if "mobile" in tags:
        if not ({"android", "ios"} & set(tags)):
            lint.add("ERROR", path, 1, "a mobile report needs the tag android or ios")
        for row in ("Platform", "Device", "OS version", "App version and build"):
            if not re.search(r"^\|\s*" + re.escape(row) + r"\s*\|", text, re.M):
                lint.add("ERROR", path, 1, f"header row '{row}' missing (mobile report)")
        if "Out of scope for now: API, security and accessibility" not in text:
            lint.add("ERROR", path, 1, "missing the line 'Out of scope for now: API, security and accessibility'")
    secs = sections(lines)
    section_of = {}
    for name, (start, body) in secs.items():
        for ln, _ in body:
            section_of[ln] = name
    for s in REPORT_SECTIONS:
        if s not in secs:
            lint.add("ERROR", path, 1, f"section '## {s}' missing")
    for i, l in enumerate(lines, 1):
        if "{{" in l or "}}" in l:
            lint.add("ERROR", path, i, "unfilled placeholder")
        m = re.match(r"^\|\s*(Executed by|Overall testing by lead)\s*\|\s*(.*?)\s*\|\s*$", l)
        if m and m.group(2):
            lint.add("ERROR", path, i, f"'{m.group(1)}' must stay empty (filled by the team)")
        if re.search(r"(?i)\b(approved for release|ready for (release|production)|sign[- ]?off granted)\b", l):
            lint.add("ERROR", path, i, "the report states facts; it does not approve a release")
        if i > 1 and not l.startswith(("title:", "tags:", "  - ")):
            check_terms(lint, terms, path, i, report_text_to_check(l, section_of.get(i, "")))
    ux = [l for _, l in secs.get("UX suggestions", [0, []])[1] if l.strip().startswith("- ")]
    if len(ux) > 5:
        lint.add("ERROR", path, secs["UX suggestions"][0], f"{len(ux)} UX suggestions; at most 5")
    check_secrets(lint, *env, path, lines)


def report_text_to_check(line, section):
    """Case titles and descriptions are copied from the reviewed test case file; in the per-flow tables and the
    blocked/unexecuted table only the last column (Comments / Reason) is new wording."""
    if line.lstrip().startswith("|") and (section.startswith("TestSuite") or section.startswith("Blocked")):
        cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        return strip_quoted(cells[-1]) if cells else ""
    return strip_quoted(line)


# ---------------------------------------------------------------- test case actual results

def lint_testcase(lint, terms, env, path):
    doc = parse_testcase_md(path)
    for f in doc["flows"]:
        for c in f["cases"]:
            ln = c["line"] + 1
            cid = c.get("Test Case ID", "")
            if c.get("Actual Result"):
                check_terms(lint, terms, path, ln, c["Actual Result"], f"{cid} Actual Result: ")
            if c.get("Comments") and (c.get("Executed On") or (c.get("Execution Status") or "PENDING") != "PENDING"):
                # the runner-style "Passed on retry …" note is allowed in Comments; the report rewrites it
                com = re.sub(r"(?i)^passed on retry, intermittent\.?\s*worth watching\.?", "", c["Comments"])
                com = re.sub(r"(?i)^could not be automated:", "", com)
                check_terms(lint, terms, path, ln, com, f"{cid} Comments: ")
            if (c.get("Execution Status") or "") == "FAIL" and not c.get("Actual Result"):
                lint.add("ERROR", path, ln, f"{cid}: a failed case needs an Actual Result")
            if (c.get("Execution Status") or "") == "BLOCKED" and not c.get("Comments"):
                lint.add("ERROR", path, ln, f"{cid}: a blocked case needs the reason in Comments")
    with open(path, encoding="utf-8") as fh:
        check_secrets(lint, *env, path, fh.read().split("\n"))


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bugs", action="append", default=[], help="bugs folder or one bug file (repeatable)")
    ap.add_argument("--report", action="append", default=[])
    ap.add_argument("--testcase", action="append", default=[])
    ap.add_argument("--env", default=os.path.join("mobile-automation", ".env"))
    ap.add_argument("--terms", default=DEFAULT_TERMS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    terms = load_terms(a.terms)
    env = load_env_secrets(a.env)
    lint = Lint()
    checked = []
    bug_files = []
    for b in a.bugs:
        if os.path.isdir(b):
            bug_files += sorted(glob.glob(os.path.join(b, "BUG-*", "BUG-*.md")))
        elif os.path.isfile(b):
            bug_files.append(b)
    titles = {}
    for p in bug_files:
        lint_bug(lint, terms, env, p, titles)
        checked.append(p)
    for p in a.report:
        lint_report(lint, terms, env, p)
        checked.append(p)
    for p in a.testcase:
        lint_testcase(lint, terms, env, p)
        checked.append(p)
    if a.json:
        print(json.dumps({"errors": lint.errors, "warnings": len(lint.items) - lint.errors, "checked": checked,
                          "items": lint.items}, indent=2, ensure_ascii=False))
    else:
        for i in lint.items:
            print(f"{i['file']}:{i['line']}: [{i['level']}] {i['msg']}")
        print(f"\n{len(checked)} file(s), {lint.errors} error(s), {len(lint.items) - lint.errors} warning(s) - "
              f"{'lint passed' if not lint.errors else 'lint FAILED'}")
    sys.exit(1 if lint.errors else 0)


if __name__ == "__main__":
    main()
