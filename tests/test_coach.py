"""Tests for the stuck tracker and the parent report.

The stuck logic takes `now` as a parameter, which is the only reason the
25-minute case is testable at all - a function that reads the clock cannot be
tested without waiting.
"""
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import coach as C
import errors as E
import report as RP
import silent as S


def a_check(err=None, silent=None, timed_out=False, output="") -> C.Check:
    return C.Check(path="C:/kid/maze.py", ran=True, output=output,
                   error=err, silent=list(silent or []), timed_out=timed_out)


def an_error() -> E.Explanation:
    return E.Explanation(exc="TypeError", title="Text and a number are being joined",
                         plain="The + sign joins text together.",
                         concept="types", hint="Wrap the number.",
                         parent_says="Which one is a number?",
                         search="TypeError: can only concatenate str")


def a_finding() -> S.Finding:
    return S.Finding(kind="assigned_never_used", line=2, name="scor",
                     title="'scor' is given a value and then never used",
                     plain="The line sets 'scor', but nothing reads it.",
                     parent_says="Can they find 'scor' again?",
                     fix_hint="Fix the spelling.",
                     search="python variable assigned but never used")


class TestSignature(unittest.TestCase):
    """The signature is what makes the stuck timer mean anything."""

    def test_clean_check_has_no_signature(self):
        self.assertEqual(C.signature(a_check()), "")

    def test_same_problem_same_signature(self):
        a = C.signature(a_check(err=an_error()))
        b = C.signature(a_check(err=an_error()))
        self.assertEqual(a, b)

    def test_different_error_is_a_different_signature(self):
        a = C.signature(a_check(err=an_error()))
        other = E.Explanation(exc="NameError", title="A name does not exist yet",
                              plain="", concept="", hint="", parent_says="", search="")
        b = C.signature(a_check(err=other))
        self.assertNotEqual(a, b)

    def test_fixing_it_clears_the_signature(self):
        # A clean check has no signature at all, so the stuck clock resets.
        self.assertEqual(C.signature(a_check()), "")
        # And a check with a problem does have one.
        self.assertNotEqual(C.signature(a_check(silent=[a_finding()])), "")

    def test_moving_the_line_does_not_reset_the_timer(self):
        # This is the important one. A kid editing whitespace to "try something"
        # has not made progress, and if the signature changed on every edit the
        # stuck alarm could never fire.
        f1 = a_finding()
        f2 = S.Finding(kind=f1.kind, line=99, name=f1.name, title=f1.title,
                       plain=f1.plain, parent_says=f1.parent_says,
                       fix_hint=f1.fix_hint, search=f1.search)
        self.assertEqual(C.signature(a_check(silent=[f1])),
                         C.signature(a_check(silent=[f2])))

    def test_a_partial_fix_is_a_change(self):
        # Fixing one of two problems IS progress and should reset the clock.
        one = C.signature(a_check(silent=[a_finding()]))
        two = C.signature(a_check(err=an_error(), silent=[a_finding()]))
        self.assertNotEqual(one, two)

    def test_timeout_has_a_signature(self):
        self.assertNotEqual(C.signature(a_check(timed_out=True)), "")


class TestStuckTracker(unittest.TestCase):

    T0 = 1_000_000.0

    def test_first_sighting_starts_the_clock(self):
        rec = C.update_record(None, "abc", self.T0)
        self.assertEqual(rec.first_seen, self.T0)
        self.assertEqual(rec.checks, 1)

    def test_repeat_keeps_the_original_start(self):
        rec = C.update_record(None, "abc", self.T0)
        rec = C.update_record(rec, "abc", self.T0 + 300)
        rec = C.update_record(rec, "abc", self.T0 + 600)
        self.assertEqual(rec.first_seen, self.T0, "the clock must not restart")
        self.assertEqual(rec.checks, 3)

    def test_a_new_problem_restarts_the_clock(self):
        rec = C.update_record(None, "abc", self.T0)
        rec = C.update_record(rec, "different", self.T0 + 600)
        self.assertEqual(rec.first_seen, self.T0 + 600)
        self.assertEqual(rec.checks, 1)

    def test_fixing_it_clears_the_record(self):
        rec = C.update_record(None, "abc", self.T0)
        rec = C.update_record(rec, "", self.T0 + 60)
        self.assertEqual(rec.signature, "")
        self.assertEqual(C.stuck_for(rec, self.T0 + 9999), 0.0)

    def test_not_stuck_before_the_threshold(self):
        rec = C.update_record(None, "abc", self.T0)
        self.assertFalse(C.is_stuck(rec, self.T0 + 60))
        self.assertFalse(C.is_stuck(rec, self.T0 + C.STUCK_AFTER - 1))

    def test_stuck_at_the_threshold(self):
        rec = C.update_record(None, "abc", self.T0)
        self.assertTrue(C.is_stuck(rec, self.T0 + C.STUCK_AFTER))
        self.assertTrue(C.is_stuck(rec, self.T0 + C.STUCK_AFTER + 3600))

    def test_elapsed_is_reported(self):
        rec = C.update_record(None, "abc", self.T0)
        self.assertAlmostEqual(C.stuck_for(rec, self.T0 + 1500), 1500.0)

    def test_a_clean_record_is_never_stuck(self):
        self.assertFalse(C.is_stuck(C.StuckRecord(), self.T0 + 99999))


class TestHumanDuration(unittest.TestCase):

    def test_seconds(self):
        self.assertEqual(C.human_duration(0), "0 seconds")
        self.assertEqual(C.human_duration(1), "1 second")
        self.assertEqual(C.human_duration(45), "45 seconds")

    def test_minutes(self):
        self.assertEqual(C.human_duration(60), "1 minute")
        self.assertEqual(C.human_duration(1500), "25 minutes")

    def test_hours(self):
        self.assertEqual(C.human_duration(3600), "1 hour")
        self.assertEqual(C.human_duration(3900), "1h 5m")

    def test_negative_is_clamped(self):
        self.assertEqual(C.human_duration(-5), "0 seconds")


class TestReport(unittest.TestCase):

    NOW = 1_000_000.0

    def test_clean_program_says_so(self):
        out = RP.render(a_check(output="score is 10\n"), C.StuckRecord(), self.NOW)
        self.assertIn("NOTHING WRONG", out)
        self.assertIn("score is 10", out)

    def test_clean_program_has_no_stuck_signal(self):
        rec = C.update_record(None, "abc", self.NOW)
        out = RP.render(a_check(), rec, self.NOW + 9999)
        self.assertNotIn("STUCK", out)

    def test_error_is_explained_with_something_to_say(self):
        out = RP.render(a_check(err=an_error()), C.StuckRecord(), self.NOW)
        self.assertIn("ONE ERROR TO FIX", out)
        self.assertIn("WHAT YOU COULD SAY", out)
        self.assertIn("Which one is a number?", out)
        self.assertIn("IF THEY WANT TO SEARCH", out)

    def test_silent_finding_is_called_silent(self):
        out = RP.render(a_check(silent=[a_finding()]), C.StuckRecord(), self.NOW)
        self.assertIn("SILENT", out)
        self.assertIn("scor", out)
        self.assertIn("Line 2", out)

    def test_the_raw_error_is_shown_for_a_programmer(self):
        out = RP.render(a_check(err=an_error()), C.StuckRecord(), self.NOW)
        self.assertIn("TypeError: can only concatenate str", out)

    def test_stuck_appears_above_the_detail(self):
        # A parent who reads one line must read the right one.
        rec = C.update_record(None, "abc", self.NOW)
        out = RP.render(a_check(err=an_error()), rec, self.NOW + 25 * 60)
        self.assertIn("STUCK FOR 25 MINUTES", out)
        self.assertLess(out.index("STUCK"), out.index("WHAT YOU COULD SAY"),
                        "the stuck signal must come before the explanation")

    def test_stuck_says_it_is_not_laziness(self):
        rec = C.update_record(None, "abc", self.NOW)
        out = RP.render(a_check(err=an_error()), rec, self.NOW + 25 * 60)
        self.assertIn("not 'not trying'", out)

    def test_short_delay_is_not_alarming(self):
        rec = C.update_record(None, "abc", self.NOW)
        out = RP.render(a_check(err=an_error()), rec, self.NOW + 120)
        self.assertIn("leave them to it", out)
        self.assertNotIn("STUCK FOR", out)

    def test_timeout_has_its_own_explanation(self):
        out = RP.render(a_check(timed_out=True), C.StuckRecord(), self.NOW)
        self.assertIn("PROGRAM NEVER STOPS", out)
        self.assertIn("loop", out.lower())

    def test_everything_wrong_at_once_is_all_reported(self):
        out = RP.render(a_check(err=an_error(), silent=[a_finding()]),
                        C.StuckRecord(), self.NOW)
        self.assertIn("TypeError", out)
        self.assertIn("scor", out)

    def test_no_line_exceeds_a_phone_screen(self):
        out = RP.render(a_check(err=an_error(), silent=[a_finding()]),
                        C.StuckRecord(), self.NOW)
        for line in out.splitlines():
            self.assertLessEqual(len(line), 72, f"too wide: {line!r}")

    def test_summary_counts_files(self):
        checks = [
            (a_check(), C.StuckRecord()),
            (a_check(err=an_error()), C.StuckRecord()),
        ]
        out = RP.summary(checks, self.NOW)
        self.assertIn("2 file(s)", out)
        self.assertIn("1 clean", out)

    def test_summary_flags_a_stuck_file(self):
        rec = C.update_record(None, "abc", self.NOW)
        out = RP.summary([(a_check(err=an_error()), rec)], self.NOW + 25 * 60)
        self.assertIn("STUCK 25 minutes", out)


class TestCoachEndToEnd(unittest.TestCase):
    """Real files, real execution."""

    def setUp(self):
        import tempfile
        self.dir = Path(tempfile.gettempdir()) / "codecoach_e2e"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state = Path(tempfile.gettempdir()) / "codecoach_e2e_state"
        self.state.mkdir(parents=True, exist_ok=True)

    def _write(self, name, src):
        p = self.dir / name
        p.write_text(textwrap.dedent(src), encoding="utf-8")
        return p

    def test_a_correct_program_is_clean(self):
        p = self._write("good.py", """
            score = 0
            for i in range(5):
                score += i
            print("score is", score)
        """)
        check, rec = C.Coach(state_dir=self.state).examine(p)
        self.assertTrue(check.clean)
        self.assertEqual(rec.signature, "")

    def test_the_silent_typo_is_caught_end_to_end(self):
        p = self._write("typo.py", """
            score = 0
            scor = score + 10
            print("score is", score)
        """)
        check, rec = C.Coach(state_dir=self.state).examine(p)
        self.assertFalse(check.clean)
        self.assertGreater(len(check.silent), 0)
        self.assertEqual(check.silent[0].name, "scor")
        self.assertTrue(rec.signature)

    def test_a_crash_is_caught_end_to_end(self):
        p = self._write("crash.py", 'print("a" + 1)\n')
        check, _ = C.Coach(state_dir=self.state).examine(p)
        self.assertIsNotNone(check.error)
        self.assertEqual(check.error.exc, "TypeError")

    def test_an_infinite_loop_is_caught_as_a_timeout(self):
        p = self._write("spin.py", "while True:\n    pass\n")
        check, _ = C.Coach(state_dir=self.state).examine(p)
        self.assertTrue(check.timed_out)
        self.assertFalse(check.clean)

    def test_no_run_never_executes_anything(self):
        # --no-run must be safe on code that would delete files.
        p = self._write("danger.py", "while True:\n    pass\n")
        check, _ = C.Coach(state_dir=self.state).examine(p, run=False)
        self.assertFalse(check.timed_out)
        self.assertIsNone(check.error)

    def test_the_stuck_clock_survives_a_restart(self):
        p = self._write("stuck.py", "score = 0\nscor = score + 1\nprint(score)\n")
        t0 = 1_000_000.0

        c1 = C.Coach(state_dir=self.state)
        c1.examine(p, now=t0)
        c1.save()

        c2 = C.Coach(state_dir=self.state)
        check, rec = c2.examine(p, now=t0 + 30 * 60)
        self.assertEqual(rec.first_seen, t0, "the clock must survive a restart")
        self.assertTrue(C.is_stuck(rec, t0 + 30 * 60))


if __name__ == "__main__":
    unittest.main(verbosity=2)
