#!/usr/bin/env python3
"""CodeCoach - tell a parent what is wrong with their kid's code, in words.

    python codecoach.py program.py          check one file
    python codecoach.py --folder .          check every .py underneath
    python codecoach.py --watch .           stay open, report on every save
    python codecoach.py --no-run prog.py    static only; never executes anything

The stuck timer lives in codecoach_state.json next to this file, so it survives
between runs. A kid who closes the window and comes back is still stuck, and the
parent still gets told.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import coach as C
import report as RP

HERE = Path(__file__).resolve().parent

# Folders that are never a kid's own code.
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "site-packages",
             "Lib", "Scripts", "build", "dist"}


def find_programs(folder: Path) -> list[Path]:
    out = []
    for p in sorted(folder.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name.startswith("test_") or p.name in ("coach.py", "silent.py", "errors.py",
                                                    "report.py", "codecoach.py"):
            continue
        out.append(p)
    return out


def check_all(folder: Path, run: bool = True) -> tuple[list[tuple[C.Check, C.StuckRecord]], C.Coach]:
    engine = C.Coach(state_dir=HERE)
    now = time.time()
    results = []
    for p in find_programs(folder):
        results.append(engine.examine(p, now=now, run=run))
    engine.save()
    return results, engine


def main() -> int:
    ap = argparse.ArgumentParser(description="CodeCoach - coding help for parents")
    ap.add_argument("target", help="a .py file, or a folder")
    ap.add_argument("--folder", action="store_true", help="treat target as a folder")
    ap.add_argument("--watch", action="store_true", help="report again on every save")
    ap.add_argument("--no-run", action="store_true",
                    help="analyse only; never execute the program")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="seconds between checks while watching (default 1)")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"  no such path: {target}")
        return 2

    engine = C.Coach(state_dir=HERE)

    def one_pass() -> int:
        now = time.time()
        if target.is_dir():
            checks = [engine.examine(p, now=now, run=not args.no_run)
                      for p in find_programs(target)]
            print(RP.summary(checks, now))
            worst = 0
            for check, rec in checks:
                if not check.clean:
                    print(engine.render(check, rec, now))
                    worst = 1
            return worst

        check, rec = engine.examine(target, now=now, run=not args.no_run)
        print(engine.render(check, rec, now))
        return 0 if check.clean else 1

    if args.watch:
        print(f"  watching {target}")
        print("  reports on every save · Ctrl-C to stop")
        # File contents, not mtimes: some editors write the same mtime and the
        # report would never refresh.
        seen: dict[str, float] = {}
        try:
            while True:
                current = {}
                for p in ([target] if target.is_file() else find_programs(target)):
                    try:
                        current[str(p)] = p.stat().st_mtime
                    except OSError:
                        continue
                if current != seen:
                    seen = current
                    one_pass()
                    engine.save()
                time.sleep(max(0.2, args.interval))
        except KeyboardInterrupt:
            print()
            print("  stopped. The stuck timer is saved, so it continues next time.")
            engine.save()
            return 0

    rc = one_pass()
    engine.save()
    return rc


if __name__ == "__main__":
    sys.exit(main())
