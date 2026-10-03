#!/usr/bin/env python3
"""Print the current IST (UTC+05:30) time in the formats the mobile skills need.

  --file   YYYY-MM-DD_HH-MM-SS-IST   (output file names, run folders)
  --cell   dd-mm-yyyy hh:mm:ss IST   (Executed On, captured_ist)
  --date   dd-mm-yyyy                (Version History "Created On")
  (none)   JSON with all three

IST has no daylight saving, so a fixed offset is used (no tzdata needed on Windows).
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def now_ist():
    return datetime.now(IST)


def file_fmt(dt):
    return dt.strftime("%Y-%m-%d_%H-%M-%S") + "-IST"


def cell_fmt(dt):
    return dt.strftime("%d-%m-%Y %H:%M:%S") + " IST"


def date_fmt(dt):
    return dt.strftime("%d-%m-%Y")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--file", action="store_true")
    g.add_argument("--cell", action="store_true")
    g.add_argument("--date", action="store_true")
    a = ap.parse_args()
    dt = now_ist()
    if a.file:
        print(file_fmt(dt))
    elif a.cell:
        print(cell_fmt(dt))
    elif a.date:
        print(date_fmt(dt))
    else:
        json.dump({"file": file_fmt(dt), "cell": cell_fmt(dt), "date": date_fmt(dt)}, sys.stdout)
        print()


if __name__ == "__main__":
    main()
