"""Tests for the silent-failure detector.

Two suites, and the second matters more:

  TestFindsSilentFailures   the bugs it must catch
  TestCorrectCodeIsSilent   correct programs that must produce NOTHING

A detector that cries wolf on working code gets turned off within a day, and
then it helps nobody. Every false positive is worse than a miss.

    python run_tests.py
"""
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import silent as S


def kinds(source: str):
    return [f.kind for f in S.analyse(textwrap.dedent(source))]


def names(source: str):
    return [f.name for f in S.analyse(textwrap.dedent(source))]


class TestFindsSilentFailures(unittest.TestCase):

    def test_the_typo_that_started_all_this(self):
        # Runs cleanly, prints 0, throws nothing. The whole reason this module
        # exists.
        src = """
            score = 0
            scor = score + 10
            print(score)
        """
        found = S.analyse(textwrap.dedent(src))
        self.assertEqual([f.name for f in found], ["scor"])
        self.assertEqual(found[0].kind, "assigned_never_used")
        self.assertIn("never used", found[0].title)

    def test_assigned_but_never_read(self):
        self.assertEqual(names("""
            total = 5
            other = total + 1
            print(total)
        """), ["other"])

    def test_a_value_computed_into_nothing(self):
        self.assertEqual(names("""
            x = 10
            unused = x * 2
            print(x)
        """), ["unused"])

    def test_loop_that_can_never_run_range_zero(self):
        self.assertIn("loop_never_runs", kinds("""
            for i in range(0):
                print(i)
        """))

    def test_loop_over_an_empty_list(self):
        self.assertIn("loop_never_runs", kinds("""
            for item in []:
                print(item)
        """))

    def test_while_false(self):
        self.assertIn("loop_never_runs", kinds("""
            while False:
                print("never")
        """))

    def test_range_with_equal_bounds(self):
        self.assertIn("loop_never_runs", kinds("""
            for i in range(5, 5):
                print(i)
        """))

    def test_constant_condition(self):
        self.assertIn("constant_condition", kinds("""
            if True:
                print("always")
            else:
                print("never")
        """))

    def test_function_written_and_never_called(self):
        found = S.analyse(textwrap.dedent("""
            def jump():
                print("whee")

            print("done")
        """))
        self.assertIn("function_never_called", [f.kind for f in found])
        self.assertIn("jump", [f.name for f in found])

    def test_a_real_kid_program_with_a_typo(self):
        # The shape of an actual beginner program.
        src = """
            player_speed = 5
            gravity = 9.8

            def jump():
                height = player_speed * 2
                print(height)

            jmpu = jump
            print(player_speed)
            print(gravity)
        """
        found = S.analyse(textwrap.dedent(src))
        self.assertEqual(sorted(f.name for f in found), ["jmpu"])


class TestCorrectCodeIsSilent(unittest.TestCase):
    """Every one of these is working code. Any finding here is a false positive,
    and a false positive is worse than a miss."""

    CORRECT = {
        "simple use": """
            x = 10
            print(x)
        """,
        "reassignment": """
            x = 1
            x = 2
            print(x)
        """,
        "augmented": """
            total = 0
            total += 5
            print(total)
        """,
        "increment in a loop": """
            total = 0
            for i in range(5):
                total += i
            print(total)
        """,
        "function defined and called": """
            def greet():
                return "hi"
            print(greet())
        """,
        "function with an unused parameter": """
            def handler(event, context):
                return event
            print(handler(1, 2))
        """,
        "unused import": """
            import math
            print("hi")
        """,
        "from import": """
            from math import sqrt
            print(sqrt(4))
        """,
        "throwaway underscore": """
            for _ in range(3):
                print("hi")
        """,
        "tuple unpacking": """
            a, b = 1, 2
            print(a, b)
        """,
        "swapping": """
            a, b = 1, 2
            a, b = b, a
            print(a, b)
        """,
        "name used in an f-string": """
            name = "Zed"
            print(f"hello {name}")
        """,
        "name used in a nested function": """
            def outer():
                target = 10
                def inner():
                    return target
                return inner()
            print(outer())
        """,
        "name used only in a call argument": """
            value = 42
            print(value)
        """,
        "list built and used": """
            items = []
            for i in range(3):
                items.append(i)
            print(items)
        """,
        "dictionary built and read": """
            d = {}
            d["a"] = 1
            print(d["a"])
        """,
        "class with methods": """
            class Dog:
                def bark(self):
                    return "woof"
            print(Dog().bark())
        """,
        "comprehension": """
            nums = [i * 2 for i in range(5)]
            print(nums)
        """,
        "while true with break": """
            n = 0
            while True:
                n += 1
                if n > 3:
                    break
            print(n)
        """,
        "try except": """
            try:
                x = 1 / 0
            except ZeroDivisionError:
                x = 0
            print(x)
        """,
        "conditional assignment": """
            flag = True
            if flag:
                result = 1
            else:
                result = 2
            print(result)
        """,
        "real comparison in an if": """
            x = 5
            if x > 3:
                print("big")
        """,
        "loop with a real range": """
            for i in range(3):
                print(i)
        """,
        "global declaration": """
            count = 0
            def bump():
                global count
                count += 1
            bump()
            print(count)
        """,
        "import __main__ guard": """
            def main():
                print("hi")
            if __name__ == "__main__":
                main()
        """,
        "returning a built value": """
            def build():
                data = {"a": 1}
                return data
            print(build())
        """,
        "multiple returns": """
            def pick(flag):
                if flag:
                    out = "yes"
                    return out
                return "no"
            print(pick(True))
        """,
        "enumerate": """
            for i, v in enumerate([10, 20]):
                print(i, v)
        """,
        "with statement": """
            x = 1
            print(x)
        """,
        "nested loop accumulator": """
            grid = [[1, 2], [3, 4]]
            total = 0
            for row in grid:
                for cell in row:
                    total += cell
            print(total)
        """,
        "exception variable used": """
            try:
                n = int("5")
            except ValueError as err:
                print(err)
                n = 0
            print(n)
        """,
    }

    def test_none_of_these_report_anything(self):
        failures = []
        for label, src in self.CORRECT.items():
            found = S.analyse(textwrap.dedent(src))
            if found:
                failures.append((label, [(f.kind, f.name) for f in found]))
        if failures:
            report = "\n".join(f"    {label}: {detail}" for label, detail in failures)
            self.fail(f"false positives on correct code:\n{report}")


class TestRobustness(unittest.TestCase):

    def test_broken_syntax_returns_nothing(self):
        # Syntax errors belong to the error translator. Reporting both at once
        # is noise.
        self.assertEqual(S.analyse("def broken(:\n    pass"), [])

    def test_empty_source(self):
        self.assertEqual(S.analyse(""), [])

    def test_only_comments(self):
        self.assertEqual(S.analyse("# nothing here\n"), [])

    def test_never_raises_on_odd_input(self):
        for src in ("x = = 1", "   ", "\n\n\n", "class :", "if", "for x in"):
            with self.subTest(src=src):
                self.assertEqual(S.analyse(src), [])

    def test_findings_are_ordered_by_line(self):
        src = textwrap.dedent("""
            a = 1
            b = 2
            c = 3
            print("done")
        """)
        found = S.analyse(src)
        self.assertEqual([f.line for f in found], sorted(f.line for f in found))


class TestEveryFindingIsUsable(unittest.TestCase):

    SOURCES = [
        "score = 0\nscor = score + 10\nprint(score)",
        "for i in range(0):\n    print(i)",
        "while False:\n    pass",
        "if True:\n    print(1)\nelse:\n    print(2)",
        "def never():\n    pass\nprint('hi')",
    ]

    def test_fields_are_populated(self):
        for src in self.SOURCES:
            for f in S.analyse(src):
                with self.subTest(kind=f.kind):
                    self.assertTrue(f.title)
                    self.assertTrue(f.plain)
                    self.assertTrue(f.parent_says)
                    self.assertTrue(f.fix_hint)
                    self.assertGreater(len(f.parent_says), 15)

    def test_no_jargon_in_plain(self):
        jargon = ["ast", "node", "scope", "linter", "static analysis",
                  "traceback", "exception", "unbound"]
        for src in self.SOURCES:
            for f in S.analyse(src):
                with self.subTest(kind=f.kind):
                    for word in jargon:
                        self.assertNotIn(word, f.plain.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
