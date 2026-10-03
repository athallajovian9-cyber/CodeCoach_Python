"""Tests for the error translator.

Every case here writes a genuinely broken program, RUNS IT, and feeds the real
traceback to the translator. Nothing is a hand-written error string - a
translator tested against what I think Python says is a translator tested
against nothing.

    python run_tests.py
"""
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import errors as E

WORK = Path(tempfile.gettempdir()) / "codecoach_tests"


def run_broken(source: str, stdin: str = "") -> str:
    """Run a broken program and return the traceback it actually produced."""
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "broken.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    p = subprocess.run([sys.executable, str(path)], input=stdin,
                       capture_output=True, text=True, timeout=20)
    return (p.stderr or "") + (p.stdout or "")


def explain_source(source: str, stdin: str = "") -> E.Explanation:
    out = run_broken(source, stdin)
    expl = E.explain(out)
    if expl is None:
        raise AssertionError(f"translator returned None for real output:\n{out}")
    return expl


class TestRealTracebacks(unittest.TestCase):
    """Each of these produces a real CPython traceback."""

    def test_name_error_from_a_typo(self):
        e = explain_source("""
            score = 0
            print(scor)
        """)
        self.assertEqual(e.exc, "NameError")
        self.assertIn("scor", e.plain)
        self.assertIn("spelled", e.parent_says.lower())

    def test_indentation_error(self):
        e = explain_source("""
            for i in range(3):
            print(i)
        """)
        self.assertEqual(e.exc, "IndentationError")
        # The title is deliberately "A block is empty", not "IndentationError" -
        # plain language beats naming the mechanism. So assert the CONCEPT is
        # explained, not that a keyword from the exception name appears.
        self.assertIn("indent", (e.plain + e.concept).lower())
        self.assertIn("pushed in", e.parent_says.lower())

    def test_unexpected_indent(self):
        e = explain_source("""
            x = 1
                y = 2
        """)
        self.assertEqual(e.exc, "IndentationError")
        self.assertIn("indent", e.title.lower())

    def test_concat_str_and_int(self):
        e = explain_source("""
            name = "Zed"
            print("Hello " + name + 5)
        """)
        self.assertEqual(e.exc, "TypeError")
        self.assertIn("number", e.title.lower())
        self.assertIn("f-string", e.hint)

    def test_unsupported_operand(self):
        e = explain_source("""
            print("5" + 5)
        """)
        self.assertEqual(e.exc, "TypeError")
        self.assertIn("5", (e.plain + e.parent_says))

    def test_zero_division(self):
        e = explain_source("""
            a = 10
            b = 0
            print(a / b)
        """)
        self.assertEqual(e.exc, "ZeroDivisionError")
        self.assertIn("zero", e.title.lower())

    def test_index_out_of_range(self):
        e = explain_source("""
            items = [1, 2, 3]
            print(items[5])
        """)
        self.assertEqual(e.exc, "IndexError")
        self.assertIn("0", e.plain, "must mention that counting starts at zero")

    def test_key_error(self):
        e = explain_source("""
            d = {"a": 1}
            print(d["b"])
        """)
        self.assertEqual(e.exc, "KeyError")

    def test_attribute_error_from_a_typo(self):
        e = explain_source("""
            name = "Zed"
            print(name.lenght())
        """)
        self.assertEqual(e.exc, "AttributeError")
        self.assertIn("lenght", e.plain)

    def test_int_of_a_word(self):
        e = explain_source("""
            x = int("ten")
        """)
        self.assertEqual(e.exc, "ValueError")
        self.assertIn("number", e.title.lower())

    def test_int_of_a_blank_input(self):
        e = explain_source("""
            x = int(input("How many? "))
        """, stdin="\n")
        self.assertEqual(e.exc, "ValueError")
        self.assertIn("input", e.hint.lower())

    def test_import_of_a_missing_library(self):
        e = explain_source("""
            import definitely_not_a_real_module_xyz
        """)
        self.assertEqual(e.exc, "ModuleNotFoundError")
        self.assertIn("pip install", e.hint)

    def test_recursion(self):
        e = explain_source("""
            def go():
                return go()
            go()
        """)
        self.assertEqual(e.exc, "RecursionError")
        self.assertIn("stop", e.parent_says.lower())

    def test_too_many_arguments(self):
        e = explain_source("""
            def f(a):
                return a
            f(1, 2, 3)
        """)
        self.assertEqual(e.exc, "TypeError")
        self.assertIn("number", e.title.lower())

    def test_missing_argument(self):
        e = explain_source("""
            def f(a, b):
                return a
            f(1)
        """)
        self.assertEqual(e.exc, "TypeError")
        self.assertIn("missing", e.title.lower())

    def test_file_not_found(self):
        e = explain_source("""
            open("no_such_file_xyz.txt")
        """)
        self.assertEqual(e.exc, "FileNotFoundError")

    def test_syntax_error(self):
        e = explain_source("""
            x = = 5
        """)
        self.assertEqual(e.exc, "SyntaxError")

    def test_unclosed_bracket(self):
        e = explain_source("""
            x = (1, 2
        """)
        self.assertEqual(e.exc, "SyntaxError")

    def test_not_iterable(self):
        e = explain_source("""
            for i in 5:
                print(i)
        """)
        self.assertEqual(e.exc, "TypeError")
        self.assertIn("loop", e.title.lower())

    def test_not_subscriptable(self):
        e = explain_source("""
            x = 5
            print(x[0])
        """)
        self.assertEqual(e.exc, "TypeError")


class TestEveryExplanationIsUsable(unittest.TestCase):
    """A field that is missing or jargon makes the whole thing useless to the
    parent it was written for."""

    SOURCES = [
        "print(nope)",
        "for i in range(2):\nprint(i)",
        'print("a" + 1)',
        "print(1/0)",
        "print([1][9])",
        "print({}['k'])",
        'print("s".nope())',
        'int("x")',
        "import nope_xyz",
        "def f():\n    return f()\nf()",
        "x = = 1",
        "for i in 5:\n    pass",
        "open('nope_xyz.txt')",
    ]

    def test_every_field_is_present_and_readable(self):
        seen = set()
        for src in self.SOURCES:
            e = explain_source(src)
            seen.add(e.exc)
            with self.subTest(exc=e.exc):
                self.assertTrue(e.title, "title must not be empty")
                self.assertTrue(e.plain, "plain must not be empty")
                self.assertTrue(e.parent_says, "parent_says must not be empty")
                self.assertTrue(e.search, "search must not be empty")
                # The sentence a parent says must be a sentence.
                self.assertGreater(len(e.parent_says), 15)
                self.assertTrue(e.parent_says[0].isupper() or e.parent_says[0] == '"')

    def test_no_jargon_in_the_plain_field(self):
        # These words are exactly what a non-programmer cannot read. If one
        # appears in `plain`, the translation has failed at its only job.
        jargon = ["traceback", "exception", "concatenate", "subscriptable",
                  "operand", "positional", "iterable", "NoneType", "unbound"]
        for src in self.SOURCES:
            e = explain_source(src)
            with self.subTest(exc=e.exc):
                low = e.plain.lower()
                for word in jargon:
                    self.assertNotIn(word, low,
                                     f"'{word}' is jargon and must not be in plain")

    def test_search_never_contains_a_file_path_or_line_number(self):
        for src in self.SOURCES:
            e = explain_source(src)
            with self.subTest(exc=e.exc):
                self.assertNotIn("\\", e.search, "a Windows path in a search query")
                self.assertNotIn("/", e.search, "a path in a search query")
                self.assertNotIn("line 1", e.search)

    def test_search_does_not_leak_the_kids_own_variable_names(self):
        # Nobody has posted about 'scor'. Searching the kid's own typo returns
        # nothing, which is the exact moment they conclude google is useless.
        e = explain_source("score = 0\nprint(scor)")
        self.assertNotIn("scor", e.search)
        self.assertIn("NameError", e.search)

    def test_search_keeps_meaningful_quoted_types(self):
        # ...but when the quoted word IS the meaning, dropping it destroys the
        # query. `can only concatenate str` finds the answer; `can only
        # concatenate` does not.
        e = explain_source('print("a" + 1)')
        self.assertIn("str", e.search)


class TestNoException(unittest.TestCase):

    def test_empty_output_explains_nothing(self):
        self.assertIsNone(E.explain(""))

    def test_whitespace_only(self):
        self.assertIsNone(E.explain("   \n  "))

    def test_a_program_that_prints_normally_is_not_an_error(self):
        # This is the important negative: normal output must not be mistaken
        # for a failure. Silent failures are handled by a different module.
        out = run_broken('print("all fine")')
        self.assertIsNone(E.explain(out))

    def test_unknown_exception_still_produces_something_usable(self):
        e = E.explain("RuntimeError: something odd happened")
        self.assertIsNotNone(e)
        self.assertTrue(e.parent_says)
        self.assertIn("RuntimeError", e.search)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSearchQueryQuality(unittest.TestCase):
    """The search field is the one that decides whether 'google it' works."""

    def test_drops_the_did_you_mean_help_text(self):
        # CPython 3.12+ adds this. It is helpful on screen and worthless in a
        # search engine - nobody has posted about the kid's exact typo.
        e = explain_source("score = 0\nprint(scor)")
        self.assertNotIn("Did you mean", e.search)
        self.assertNotIn("?", e.search)

    def test_no_trailing_punctuation(self):
        for src in ("print(1/0)", 'int("x")', "print([1][9])"):
            e = explain_source(src)
            with self.subTest(exc=e.exc):
                self.assertFalse(e.search.endswith((":", ".", " ")),
                                 f"untidy query: {e.search!r}")

    def test_queries_are_short_enough_to_actually_search(self):
        for src in ("print(nope)", 'print("a" + 1)', "print(1/0)", 'int("x")'):
            e = explain_source(src)
            with self.subTest(exc=e.exc):
                self.assertLess(len(e.search), 90, f"too long: {e.search!r}")
