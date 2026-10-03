#!/usr/bin/env python3
"""Wording and secret check for any text going to Jira (summary, description, environment, comments).

  python lint_human_text.py --payload "<scratchpad>/BUG-003.payload.json"    # output of bug_to_jira.py
  python lint_human_text.py --text-file "<scratchpad>/comment.md"            # e.g. a retest comment
  python lint_human_text.py --text "Retested on …"

Same banned-terms list as execute-mobile-test-cases (../execute-mobile-test-cases/assets/banned-terms.txt, shared by
web and mobile) and the
same secret patterns (.env values for PASSWORD/TOKEN/KEY variables, password=…, Bearer, JWT). Jira keys and links
are allowed. Text in double quotes is exempt (exact app messages and console text are quoted). Unfilled
{{placeholders}} and <angle-bracket> template slots are errors. Exit 1 on any error.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import EXEC_SCRIPTS, load_json, utf8_stdio  # noqa: E402

_spec = importlib.util.spec_from_file_location("exec_lint", os.path.join(EXEC_SCRIPTS, "lint_human_text.py"))
exec_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exec_lint)

PLACEHOLDER_RX = re.compile(r"\{\{\w+\}\}|<(?:environment|version|date|steps?|result|TC-…|BUG-…)[^>]*>", re.I)


def check_texts(items, env_path=os.path.join("mobile-automation", ".env")):
    """items: [(where, text)] -> {"errors": n, "warnings": n, "items": [...]}"""
    terms = exec_lint.load_terms(exec_lint.DEFAULT_TERMS)
    env = exec_lint.load_env_secrets(env_path)
    lint = exec_lint.Lint()
    for where, text in items:
        lines = str(text or "").split("\n")
        for i, line in enumerate(lines, 1):
            exec_lint.check_terms(lint, terms, where, i, exec_lint.strip_quoted(line))
            if PLACEHOLDER_RX.search(line):
                lint.add("ERROR", where, i, "unfilled placeholder")
        exec_lint.check_secrets(lint, *env, where, lines)
    return {"errors": lint.errors, "warnings": len(lint.items) - lint.errors, "items": lint.items}


def payload_texts(p):
    items = [("summary", p.get("summary", "")), ("description", p.get("description", ""))]
    env = (p.get("additional_fields") or {}).get("environment")
    if isinstance(env, dict):
        items.append(("environment", json.dumps(env, ensure_ascii=False)))
    return items


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--payload", action="append", default=[])
    ap.add_argument("--text-file", action="append", default=[])
    ap.add_argument("--text", action="append", default=[])
    ap.add_argument("--env", default=os.path.join("mobile-automation", ".env"))
    a = ap.parse_args()
    items = []
    for p in a.payload:
        items += [(f"{os.path.basename(p)}:{w}", t) for w, t in payload_texts(load_json(p, {}) or {})]
    for p in a.text_file:
        with open(p, encoding="utf-8") as f:
            items.append((os.path.basename(p), f.read()))
    for i, t in enumerate(a.text, 1):
        items.append((f"text{i}", t))
    res = check_texts(items, a.env)
    for i in res["items"]:
        print(f"{i['file']}:{i['line']}: [{i['level']}] {i['msg']}")
    print(f"{len(items)} text(s), {res['errors']} error(s), {res['warnings']} warning(s) - "
          f"{'lint passed' if not res['errors'] else 'lint FAILED'}")
    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
