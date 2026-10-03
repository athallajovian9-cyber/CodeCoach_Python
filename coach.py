"""CodeCoach: check a kid's program and say what is wrong, in plain language.

Two things it reports, and the first is the one that matters:

  SILENT   the program runs, throws nothing, and does the wrong thing
  ERROR    Python complained, and the message was jargon

Plus the thing a parent actually needs and cannot get any other way:

  STUCK    the same problem has been there for N minutes, so this is not
           "not trying", it is "stuck", and now is the moment to walk over

That distinction is the whole parent-facing point. A kid at a computer not
making progress looks identical to a kid not trying, and a parent who cannot
tell them apart defaults to "get off the computer" - which is the wrong call
about half the time.

The stuck logic is pure and time is injected, because a function that reads the
clock cannot be tested for the 25-minute case without waiting 25 minutes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import errors as E
import silent as S

# How long the SAME problem must persist before it counts as stuck rather than
# just being the current line of thinking. Below this, walking over interrupts
# someone who is about to solve it.
STUCK_AFTER = 15 * 60

# A program that never finishes is a bug with no traceback at all.
RUN_TIMEOUT = 5.0


@dataclass
class Check:
    """Everything one pass over one program learned."""
    path: str
    ran: bool
    output: str
    error: E.Explanation | None
    silent: list[S.Finding] = field(default_factory=list)
    timed_out: bool = False

    @property
    def clean(self) -> bool:
        return not self.error and not self.silent and not self.timed_out


# ------------------------------------------------------------- stuck tracking
# Pure. `now` is a parameter so the cases can be tested without waiting.

@dataclass
class StuckRecord:
    signature: str = ""
    first_seen: float = 0.0
    last_seen: float = 0.0
    checks: int = 0


def signature(check: Check) -> str:
    """A stable id for "the same problem".

    Based on WHAT is wrong, not on line numbers or the values involved, so that
    editing a line - which is what trying looks like - does not read as progress
    when the same mistake is still there. If the signature changed every time a
    kid moved a brace, the stuck timer would reset constantly and never fire.
    """
    parts: list[str] = []
    if check.error:
        parts.append("err:" + check.error.exc + ":" + check.error.title)
    for f in check.silent:
        parts.append("silent:" + f.kind + ":" + f.name)
    if check.timed_out:
        parts.append("timeout")
    if not parts:
        return ""
    return hashlib.sha256("|".join(sorted(parts)).encode("utf-8")).hexdigest()[:16]


def update_record(prev: StuckRecord | None, sig: str, now: float) -> StuckRecord:
    """Advance the tracker. A different problem starts the clock again."""
    if not sig:
        return StuckRecord()
    if prev is None or prev.signature != sig:
        return StuckRecord(signature=sig, first_seen=now, last_seen=now, checks=1)
    return StuckRecord(signature=sig, first_seen=prev.first_seen,
                       last_seen=now, checks=prev.checks + 1)


def stuck_for(rec: StuckRecord, now: float) -> float:
    """Seconds this problem has been present. 0 if there is no problem."""
    if not rec.signature or rec.first_seen <= 0:
        return 0.0
    return max(0.0, now - rec.first_seen)


def is_stuck(rec: StuckRecord, now: float, threshold: float = STUCK_AFTER) -> bool:
    return stuck_for(rec, now) >= threshold


def human_duration(seconds: float) -> str:
    s = int(max(0, seconds))
    if s < 60:
        return f"{s} second{'s' if s != 1 else ''}"
    m = s // 60
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''}"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if m else f"{h} hour{'s' if h != 1 else ''}"


# ------------------------------------------------------------------- running

def run_program(path: Path, timeout: float = RUN_TIMEOUT) -> tuple[bool, str, str, bool]:
    """Run it. Returns (ran, stdout, stderr, timed_out).

    A timeout is reported as a result rather than raised, because a program that
    never ends is one of the most common things a kid writes and it has no
    traceback to explain it.
    """
    try:
        p = subprocess.run([sys.executable, str(path)], capture_output=True,
                           text=True, timeout=timeout, input="")
        return True, p.stdout or "", p.stderr or "", False
    except subprocess.TimeoutExpired:
        return False, "", "", True
    except OSError as exc:
        return False, "", str(exc), False


def check_file(path: str | Path, run: bool = True) -> Check:
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Check(str(p), False, "", E.Explanation(
            exc="FileNotFoundError", title="That file could not be opened",
            plain=str(exc), concept="", hint="", parent_says="Is the path right?",
            search=""))

    silent_findings = S.analyse(source)

    if not run:
        return Check(str(p), False, "", None, silent_findings)

    ran, out, err, timed_out = run_program(p)
    return Check(
        path=str(p),
        ran=ran,
        output=out,
        error=E.explain(err) if err.strip() else None,
        silent=silent_findings,
        timed_out=timed_out,
    )


# ------------------------------------------------------------ the coach loop

class Coach:
    """Watches a folder, reports on change, and remembers how long a problem
    has been there."""

    def __init__(self, state_dir: str | Path | None = None):
        import report as RP                      # local import: avoids a cycle
        self._report = RP
        self.state_path = Path(state_dir or ".") / "codecoach_state.json"
        self.records: dict[str, StuckRecord] = self._load()
        self.last: dict[str, Check] = {}

    def _load(self) -> dict[str, StuckRecord]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        out: dict[str, StuckRecord] = {}
        for key, val in (raw.get("files") or {}).items():
            try:
                out[key] = StuckRecord(**val)
            except TypeError:
                continue
        return out

    def save(self) -> None:
        payload = {"version": 1,
                   "files": {k: asdict(v) for k, v in self.records.items()}}
        try:
            self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def examine(self, path: str | Path, now: float | None = None,
                run: bool = True) -> tuple[Check, StuckRecord]:
        t = time.time() if now is None else now
        check = check_file(path, run=run)
        sig = signature(check)
        rec = update_record(self.records.get(str(path)), sig, t)
        if sig:
            self.records[str(path)] = rec
        else:
            self.records.pop(str(path), None)
        self.last[str(path)] = check
        return check, rec

    def render(self, check: Check, rec: StuckRecord, now: float | None = None) -> str:
        t = time.time() if now is None else now
        return self._report.render(check, rec, t)
