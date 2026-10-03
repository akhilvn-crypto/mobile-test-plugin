"""Jira references in test case and report cells (shared by execute-mobile-test-cases and file-bugs-to-jira; not run directly).

bugs/jira-sync.json (written by file-bugs-to-jira) records which bug went to which Jira issue. Wherever a bug ID is
written for a person to read, a filed bug is shown with its Jira key:

  MD cell     [PROJ-45](https://site/browse/PROJ-45) (BUG-003)
  XLSX cell   PROJ-45 (BUG-003)                      + the cell's hyperlink (one bug)
              PROJ-45 (BUG-003) https://site/browse/PROJ-45   (one line per bug when a cell lists several)
  not filed   BUG-003

Every form still contains the plain bug ID, so `re.findall(r"BUG-\\d+", cell)` keeps finding the bugs.
"""
import json
import os
import re

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
# one bug reference in any of the forms above (longest form first)
REF_RE = re.compile(
    r"\[(?P<k1>[A-Z][A-Z0-9]+-\d+)\]\((?P<u1>[^)\s]+)\)\s*\(\s*(?P<b1>BUG-\d+)\s*\)"
    r"|(?P<k2>[A-Z][A-Z0-9]+-\d+)\s*\(\s*(?P<b2>BUG-\d+)\s*\)(?:[ \t]+(?P<u2>https?://\S+))?"
    r"|(?P<b3>BUG-\d+)")
BUG_RE = re.compile(r"BUG-\d+")


def load_sync(path="bugs/jira-sync.json"):
    """bug ID -> {jiraKey, url, status, ...}; empty when the file does not exist or cannot be read."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, ValueError):
        return {}
    out = {}
    for bid, e in (data.get("bugs") or {}).items():
        if isinstance(e, dict) and KEY_RE.match(str(e.get("jiraKey") or "")) and e.get("url"):
            out[bid] = e
    return out


def bug_ids(text):
    seen = []
    for b in BUG_RE.findall(text or ""):
        if b not in seen:
            seen.append(b)
    return seen


def md_ref(bid, sync):
    e = sync.get(bid)
    return f"[{e['jiraKey']}]({e['url']}) ({bid})" if e else bid


def plain_ref(bid, sync, with_url=False):
    e = sync.get(bid)
    if not e:
        return bid
    return f"{e['jiraKey']} ({bid})" + (f" {e['url']}" if with_url else "")


def render_md(text, sync):
    """Rewrite every bug reference in an MD cell to its current form; other text is kept as it is."""
    def rep(m):
        bid = m.group("b1") or m.group("b2") or m.group("b3")
        return md_ref(bid, sync)
    return REF_RE.sub(rep, text or "")


def render_plain(text, sync):
    """MD cell text -> XLSX (value, hyperlink or None). Links in MD form become plain text."""
    ids = bug_ids(text)
    filed = [b for b in ids if b in sync]
    rest = REF_RE.sub("\0", text or "")  # what is left besides bug references
    only_refs = not re.sub(r"[\0\s,;]", "", rest)
    if only_refs and ids:
        if len(ids) == 1:
            b = ids[0]
            return plain_ref(b, sync), (sync[b]["url"] if b in sync else None)
        if filed:  # a cell holds one link only: list each bug with its URL on its own line
            return "\n".join(plain_ref(b, sync, with_url=True) for b in ids), None
        return ", ".join(ids), None

    def rep(m):
        bid = m.group("b1") or m.group("b2") or m.group("b3")
        return plain_ref(bid, sync)
    value = REF_RE.sub(rep, text or "")
    links = [sync[b]["url"] for b in filed]
    return value, (links[0] if len(set(links)) == 1 else None)


def strip_md_links(text):
    """[label](url) -> label (for plain-text outputs)."""
    return re.sub(r"\[([^\]]+)\]\((?:[^)\s]+)\)", r"\1", text or "")
