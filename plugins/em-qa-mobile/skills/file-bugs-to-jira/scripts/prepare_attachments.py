#!/usr/bin/env python3
"""Get a bug's evidence ready for upload to Jira (mobile bugs; plan section 8.3).

  python prepare_attachments.py --bug BUG-007 [--limit <bytes>] [--retest] [--out-dir "<scratchpad>/att"]

- Files: screenshots/, recordings/ (MP4) and logs/ of the bug folder (with --retest: the bug's retest/ folder).
- --limit: the site's upload limit (`jira_rest.py limit` -> upload_limit_bytes). Without it nothing is shrunk.
- A recording larger than the limit is shrunk with ffmpeg when it is installed (lower resolution, then lower frame
  rate) into --out-dir; the original stays where it is. When it still does not fit, or ffmpeg is not installed, the
  recording is NOT uploaded: it is listed under `not_uploaded` with its local path, and `note` holds the sentence for
  the Jira description ("The screen recording … is kept at …"), so nothing is ever dropped silently.
- Other files larger than the limit are listed under `not_uploaded` the same way.
- Log excerpts are checked for secrets with lint_human_text (a log with a secret is not uploaded and is reported).

Prints {"bug", "upload": [paths], "shrunk": [{from, to, size_before, size_after}], "not_uploaded": [{file, size,
reason}], "note": "<sentence or empty>", "ffmpeg": bool}.
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import BUGS_DIR, bug_dirs, dump, norm_bug_id, rel, utf8_stdio  # noqa: E402
import lint_human_text  # noqa: E402

MEDIA = (".png", ".jpg", ".jpeg", ".mp4", ".webm", ".mov", ".txt", ".log")
PASSES = [("scale='min(720,iw)':-2", "20", "30"), ("scale='min(540,iw)':-2", "12", "34"),
          ("scale='min(360,iw)':-2", "8", "38")]


def human(n):
    return f"{n / (1024 * 1024):.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def shrink(src, out_dir, limit):
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    for i, (scale, fps, crf) in enumerate(PASSES, 1):
        dst = os.path.join(out_dir, f"{base}_small{i}.mp4")
        cmd = [ff, "-y", "-loglevel", "error", "-i", src, "-vf", scale, "-r", fps, "-c:v", "libx264", "-preset",
               "veryfast", "-crf", crf, "-an", "-movflags", "+faststart", dst]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=900)
        except (subprocess.SubprocessError, OSError):
            continue
        if os.path.exists(dst) and os.path.getsize(dst) <= limit:
            return dst
    return None


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bug", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--retest", action="store_true")
    ap.add_argument("--out-dir", default=os.path.join(os.environ.get("TEMP", "/tmp"), "jira-attachments"))
    ap.add_argument("--bugs-dir", default=BUGS_DIR)
    a = ap.parse_args()
    bid = norm_bug_id(a.bug)
    md = bug_dirs(a.bugs_dir).get(bid)
    if not md:
        dump({"ok": False, "error": f"{a.bug} not found in {a.bugs_dir}/"}, code=2)
    folder = os.path.dirname(md)
    subs = ["retest"] if a.retest else ["screenshots", "recordings", "logs"]
    files = []
    for sub in subs:
        d = os.path.join(folder, sub)
        if os.path.isdir(d):
            files += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(MEDIA)]
    out = {"ok": True, "bug": bid, "upload": [], "shrunk": [], "not_uploaded": [], "note": "",
           "ffmpeg": bool(shutil.which("ffmpeg")), "limit_bytes": a.limit}
    notes = []
    for f in files:
        size = os.path.getsize(f)
        if f.lower().endswith((".txt", ".log")):
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            ex = lint_human_text.exec_lint
            lint = ex.Lint()
            ex.check_secrets(lint, *ex.load_env_secrets(os.path.join("mobile-automation", ".env")), f, text.split("\n"))
            if lint.errors:
                out["not_uploaded"].append({"file": rel(f), "size": size,
                                            "reason": "the log still contains a secret; scrub it and run again"})
                continue
        if a.limit and size > a.limit:
            if f.lower().endswith((".mp4", ".mov", ".webm")):
                small = shrink(f, a.out_dir, a.limit)
                if small:
                    out["shrunk"].append({"from": rel(f), "to": small, "size_before": size,
                                          "size_after": os.path.getsize(small)})
                    out["upload"].append(small)
                    continue
                why = ("larger than the Jira upload limit and ffmpeg is not installed" if not out["ffmpeg"]
                       else "larger than the Jira upload limit even after shrinking")
                out["not_uploaded"].append({"file": rel(f), "size": size, "reason": why})
                notes.append(f"The screen recording {os.path.basename(f)} ({human(size)}) is too large to attach; "
                             f"it is kept at {rel(f)}.")
                continue
            out["not_uploaded"].append({"file": rel(f), "size": size, "reason": "larger than the Jira upload limit"})
            notes.append(f"{os.path.basename(f)} ({human(size)}) is too large to attach; it is kept at {rel(f)}.")
            continue
        out["upload"].append(f)
    out["note"] = " ".join(notes)
    dump(out)


if __name__ == "__main__":
    main()
