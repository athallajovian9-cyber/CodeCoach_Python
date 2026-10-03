"""Turn a Python traceback into something a parent can use.

The design point: this is written for a NON-PROGRAMMER reading it over a kid's
shoulder. Every field exists to answer one of three questions:

    what happened?      -> title, plain
    what should I say?  -> parent_says
    where do I look?    -> hint, search

`search` matters more than it looks. A kid who pastes a whole traceback into
Google gets worse results than one who pastes the one canonical line, and they
do not know which line that is. Filtering the message down to its searchable
form - stripping file paths, line numbers and their own variable names - is the
difference between "google it" working and not.

Nothing here is guessed. Every pattern is derived from real CPython output; the
tests feed it real tracebacks produced by running real broken programs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Explanation:
    exc: str                    # the exception class, e.g. "TypeError"
    title: str                  # plain-language name of the problem
    plain: str                  # what it means, no jargon
    concept: str                # the idea to learn, one phrase
    hint: str                   # where to look and what to change
    parent_says: str            # one sentence an adult can say out loud
    search: str                 # a query that actually finds the answer
    expert: str = ""            # the raw line, for when a programmer is around
    notes: list[str] = field(default_factory=list)


# The last line of a traceback is always "ExceptionType: message".
_EXC_LINE = re.compile(r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning))\s*:?\s*(?P<msg>.*)$", re.M)

# Things that make a search query worse, not better.
_TMP_PATH = re.compile(r"[A-Za-z]:\\[^\s\"']*|\/[^\s\"']*")
_LINE_NO = re.compile(r"\bline \d+\b")
# A quote around the kid's own identifier, e.g. name 'scor' is not defined.
_OWN_NAME = re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)'")


# CPython 3.12+ appends "Did you mean: 'x'?" as a convenience. It is helpful on
# screen and useless in a search engine - nobody has posted about the exact
# typo - and it makes the query longer without making it findable. Dropped.
_DID_YOU_MEAN = re.compile(r"\.?\s*Did you mean:?.*$", re.I | re.S)


def _clean_for_search(exc: str, message: str, keep_quoted: bool) -> str:
    """Reduce an error to the form that finds answers.

    `keep_quoted` is True when the quoted value is part of the message's meaning
    ("can only concatenate str (not "int")") and False when it is just the kid's
    own identifier - `name 'scor' is not defined` searches far better as
    `NameError: name NAME is not defined`, because nobody has posted about `scor`.
    """
    m = _DID_YOU_MEAN.sub("", message)
    m = _TMP_PATH.sub("", m)
    m = _LINE_NO.sub("line N", m)
    if not keep_quoted:
        m = _OWN_NAME.sub("NAME", m)
    m = re.sub(r"\s+", " ", m).strip()
    # A trailing colon or period is the tail of the message, not part of it.
    m = m.strip("'\" \t:.")
    return f"{exc}: {m}" if m else exc


class Translator:
    """Pattern table. Order matters: first match wins."""

    def __init__(self):
        self.rules = [
            (r"NameError.*name '(?P<n>[^']+)' is not defined", self._name_error),
            (r"NameError.*free variable '(?P<n>[^']+)'", self._scope_error),
            (r"UnboundLocalError", self._unbound),
            (r"IndentationError.*expected an indented block", self._indent),
            (r"IndentationError.*unexpected indent", self._unexpected_indent),
            (r"TabError", self._tabs),
            (r"TypeError.*can only concatenate str", self._concat_str),
            (r"TypeError.*unsupported operand type\(s\) for \+=?: '(?P<a>[^']+)' and '(?P<b>[^']+)'", self._operand),
            (r"TypeError.*takes \d+ positional argument", self._arg_count),
            (r"TypeError.*missing \d+ required positional argument", self._arg_missing),
            (r"TypeError.*not callable", self._not_callable),
            (r"TypeError.*is not subscriptable|not subscriptable", self._not_subscriptable),
            (r"TypeError.*is not iterable", self._not_iterable),
            (r"ZeroDivisionError", self._divide),
            (r"IndexError.*list index out of range", self._index),
            (r"KeyError", self._key),
            (r"AttributeError.*has no attribute '(?P<n>[^']+)'", self._attribute),
            (r"AttributeError", self._attribute_generic),
            (r"ValueError.*invalid literal for int", self._int_parse),
            (r"ValueError.*could not convert string to float", self._float_parse),
            (r"RecursionError", self._recursion),
            (r"ModuleNotFoundError.*named '(?P<n>[^']+)'", self._module),
            (r"FileNotFoundError", self._file_missing),
            (r"SyntaxError.*invalid syntax", self._syntax),
            (r"SyntaxError.*was never closed|unexpected EOF", self._unclosed),
            (r"SyntaxError", self._syntax_generic),
            (r"KeyboardInterrupt", self._interrupt),
            (r"MemoryError", self._memory),
        ]

    # ------------------------------------------------------------ entry point

    def explain(self, text: str) -> Explanation | None:
        """Explain a traceback. None if there is no exception in it at all
        (which is the silent-failure case, handled elsewhere)."""
        if not text or not text.strip():
            return None

        exc, msg = "", ""
        for m in _EXC_LINE.finditer(text):
            exc, msg = m.group("type"), m.group("msg")
        if not exc:
            return None

        haystack = f"{exc}: {msg}"
        for pattern, builder in self.rules:
            m = re.search(pattern, haystack)
            if m:
                out = builder(exc, msg, m.groupdict())
                out.expert = f"{exc}: {msg}".strip()
                return out

        return Explanation(
            exc=exc,
            title="Something went wrong",
            plain=f"Python stopped with a {exc}.",
            concept="reading an error message",
            hint="The last line of the message names the problem. Read it bottom-up.",
            parent_says=f"Read the last line out loud - what does '{exc}' sound like it means?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    # ------------------------------------------------------------- builders

    def _name_error(self, exc, msg, g):
        n = g.get("n", "that name")
        return Explanation(
            exc=exc,
            title="A name does not exist yet",
            plain=(f"The code uses the name '{n}', but nothing has been given that name. "
                   "Usually a spelling mistake, or a variable used before it is created."),
            concept="variables are created by assigning to them",
            hint=f"Search the file for '{n}'. Check the spelling matches where it is set. "
                 "Python is case-sensitive: Score and score are different names.",
            parent_says=f"Is '{n}' spelled exactly the same everywhere it appears?",
            search=_clean_for_search(exc, msg, keep_quoted=False),
            notes=["This is the most common beginner error, and almost always a typo."],
        )

    def _scope_error(self, exc, msg, g):
        n = g.get("n", "that name")
        return Explanation(
            exc=exc,
            title="A function is reaching outside itself",
            plain=f"The code inside a function tries to use '{n}', which lives outside it.",
            concept="functions have their own private space",
            hint=f"Either pass '{n}' in as an argument, or read it without trying to change it.",
            parent_says="Does that function get handed the value, or is it reaching for it?",
            search=_clean_for_search(exc, msg, keep_quoted=False),
        )

    def _unbound(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A variable is used before it is set",
            plain=("The name exists somewhere in the function, but this path through the "
                   "code reaches it before it has been given a value."),
            concept="code runs in order, top to bottom",
            hint="Move the assignment above the line that reads it, or set a starting value first.",
            parent_says="Does the value get set before the line that uses it, on every path?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _indent(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A block is empty",
            plain=("Something like a 'for' or 'if' was written, but the lines that belong "
                   "to it are not indented underneath it."),
            concept="indentation is how Python knows what belongs inside",
            hint="The line after a 'for', 'if', 'while', 'def' or 'else' that ends in a colon "
                 "must be indented - usually four spaces.",
            parent_says="Should the next line be pushed in underneath that one?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _unexpected_indent(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A line is indented too far",
            plain="A line is pushed in further than the lines around it, with nothing to belong to.",
            concept="indentation is how Python knows what belongs inside",
            hint="Line the offending statement up with the ones above it.",
            parent_says="Does that line belong inside the block, or next to it?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _tabs(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Spaces and tabs are mixed",
            plain="Some lines use tab characters and others use spaces. They look the same but are not.",
            concept="one indentation style, used everywhere",
            hint="Convert the whole file to spaces. Most editors have a 'convert indentation' option.",
            parent_says="Did this file get indented with tabs in one place and spaces in another?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _concat_str(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Text and a number are being joined",
            plain=("The + sign joins text together. It cannot join text to a number, "
                   "because Python will not guess whether you meant 5 or '5'."),
            concept="values have types: text and numbers are different things",
            hint="Wrap the number: str(score), or use an f-string: f\"Score {score}\".",
            parent_says="Which of those two things is a number, and which is text?",
            search="TypeError: can only concatenate str (not \"int\") to str",
            notes=["f-strings are the modern fix and worth learning instead of str()."],
        )

    def _operand(self, exc, msg, g):
        a, b = g.get("a", "one type"), g.get("b", "another")
        return Explanation(
            exc=exc,
            title=f"Arithmetic between {a} and {b}",
            plain=(f"The maths symbol is being used on a {a} and a {b}. Python will not "
                   "mix them without being told which one you meant."),
            concept="values have types: text and numbers are different things",
            hint=f"Convert one side so both match - int(x) or float(x) for numbers, str(x) for text.",
            parent_says=f"Which one is a {a} and which is a {b}? What should both be?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _arg_count(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A function was given the wrong number of things",
            plain="The function was called with a different number of values than it accepts.",
            concept="functions declare what they need",
            hint="Count the values between the brackets at the call, and again at the 'def' line.",
            parent_says="How many things does it ask for, and how many is it being given?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _arg_missing(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A function is missing a value it needs",
            plain="The function expects a value that was not supplied when it was called.",
            concept="functions declare what they need",
            hint="Compare the call with the 'def' line - one of its parameters has nothing passed in.",
            parent_says="What does the definition say it needs, and was all of that handed over?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _not_callable(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Something is used like a function but is not one",
            plain="It is written with brackets after it, as if it were a function, but it holds a value.",
            concept="calling versus referring",
            hint="Check whether that name holds a function. Writing it without brackets reads it; "
                 "with brackets runs it.",
            parent_says="Is that a function, or a value that was given the same name?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _not_subscriptable(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Square brackets used on something that holds one value",
            plain="Only lists, text and dictionaries can be indexed with [ ]. This is a single value.",
            concept="which things can hold many values",
            hint="If it should be a list, it was probably assigned a single item instead of a list.",
            parent_says="Should that be a list? What was assigned to it?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _not_iterable(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Looping over something that is not a list",
            plain="A 'for' loop was given a single value. It can only go through a collection.",
            concept="which things can be looped over",
            hint="If it is a single number, use range(): for i in range(n).",
            parent_says="Is that a collection, or one single thing?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _divide(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Dividing by zero",
            plain="The number on the bottom of the division was zero. That has no answer.",
            concept="zero is a special case in arithmetic",
            hint="Guard it: if divisor != 0: before dividing.",
            parent_says="Can that number ever be zero? What should happen if it is?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _index(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Reaching past the end of a list",
            plain=("The position asked for is further along than the list is long. "
                   "Counting starts at 0, so a 3-item list has positions 0, 1 and 2."),
            concept="lists are indexed from zero",
            hint="Print len(the_list) next to the index being asked for. The index must be smaller.",
            parent_says="How long is the list, and which position is being asked for? "
                        "Remember the first one is 0.",
            search=_clean_for_search(exc, msg, keep_quoted=True),
            notes=["Off-by-one is the classic. len(list)-1 is the last valid position."],
        )

    def _key(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A dictionary has no such key",
            plain="The dictionary was asked for a name it does not contain.",
            concept="dictionaries are looked up by key, and missing keys are an error",
            hint="Use .get(key, default) to read without failing, or check 'if key in d' first.",
            parent_says="Is that spelling exactly the key that was stored?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _attribute(self, exc, msg, g):
        n = g.get("n", "that attribute")
        return Explanation(
            exc=exc,
            title=f"An object has nothing called '{n}'",
            plain=f"The dot asks an object for '{n}', and it does not have it.",
            concept="objects carry their own set of abilities",
            hint=f"Check the spelling of '{n}', and that the object is the type you think it is.",
            parent_says=f"Is '{n}' spelled right, and is that the kind of thing that has it?",
            search=_clean_for_search(exc, msg, keep_quoted=False),
        )

    def _attribute_generic(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Asking an object for something it does not have",
            plain="The dot after a value asks it for a named ability it does not have.",
            concept="objects carry their own set of abilities",
            hint="Print the value and its type() on the line before.",
            parent_says="What kind of thing is that, and does that kind have this ability?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _int_parse(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Trying to turn something into a number that is not one",
            plain="int() was given text that does not look like a whole number.",
            concept="converting between text and numbers",
            hint="This is very often input(): a person typing 'ten' or pressing Enter is not a number. "
                 "Guard it, or use a loop that asks again.",
            parent_says="What did the person type in? What if they typed a word, or nothing?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
            notes=["With input(), always assume the user types something unexpected."],
        )

    def _float_parse(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Trying to turn text into a decimal number",
            plain="float() was given text that does not look like a number.",
            concept="converting between text and numbers",
            hint="Check what was typed. An empty string or a stray space is the usual cause.",
            parent_says="What exactly was typed in? Could it have been empty?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _recursion(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A function keeps calling itself forever",
            plain="The function calls itself and never reaches a case that stops it.",
            concept="recursion needs a stopping condition",
            hint="Find the 'if' that should end the recursion and check it is actually reached.",
            parent_says="What is supposed to make it stop? Does that ever happen?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _module(self, exc, msg, g):
        n = g.get("n", "that module")
        return Explanation(
            exc=exc,
            title=f"The '{n}' library is not installed",
            plain=f"The code imports '{n}', which is not available on this computer.",
            concept="libraries are separate things, installed on top of the language",
            hint=f"Install it with:  pip install {n}",
            parent_says="Is that an add-on that still needs installing?",
            search=f"ModuleNotFoundError: No module named '{n}' pip install",
        )

    def _file_missing(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A file could not be found",
            plain="The code tried to open a file that is not where it looked.",
            concept="programs look for files relative to where they are run",
            hint="Check the filename and the folder. The working directory matters.",
            parent_says="Is the file in the same folder the program was started from?",
            # keep_quoted=False: the quoted value is the kid's own filename, and
            # nobody has posted about it. `[Errno 2] No such file or directory`
            # is the part that finds the answer.
            search=_clean_for_search(exc, msg, keep_quoted=False),
        )

    def _syntax(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Python cannot read this line at all",
            plain=("Something is not written the way Python expects. The reported line is where "
                   "it gave up, which is often one line after the actual mistake."),
            concept="syntax: the exact shape the language requires",
            hint="Look at the reported line AND the one before it. Check brackets, quotes and colons.",
            parent_says="Is there a bracket or a quote left open on that line or the one before?",
            search="SyntaxError: invalid syntax",
            notes=["The caret points at where Python noticed, not always where the mistake is."],
        )

    def _unclosed(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="A bracket or quote was never closed",
            plain="Something opened with ( or [ or a quote mark, and never closed.",
            concept="brackets and quotes come in pairs",
            hint="Count the opening and closing brackets on that line - they should match.",
            parent_says="Is there a closing bracket for every opening one on that line?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _syntax_generic(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Python cannot read this line",
            plain="The line is not written in a shape Python accepts.",
            concept="syntax: the exact shape the language requires",
            hint="Read the line out loud. Often a word is misspelled or a symbol is missing.",
            parent_says="Read that line out loud - does anything sound wrong?",
            search=_clean_for_search(exc, msg, keep_quoted=True),
        )

    def _interrupt(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Stopped by hand",
            plain="The program was interrupted, usually with Ctrl-C. Not a bug.",
            concept="",
            hint="Nothing to fix.",
            parent_says="That was just you stopping it.",
            search="KeyboardInterrupt",
        )

    def _memory(self, exc, msg, g):
        return Explanation(
            exc=exc,
            title="Ran out of memory",
            plain="The program tried to hold more in memory than was available.",
            concept="memory is finite",
            hint="Usually an enormous list, a loop that adds forever, or a file loaded whole.",
            parent_says="Is something getting bigger every time round the loop?",
            search="MemoryError",
        )


_DEFAULT = Translator()


def explain(text: str) -> Explanation | None:
    """Explain a traceback in plain language."""
    return _DEFAULT.explain(text)
