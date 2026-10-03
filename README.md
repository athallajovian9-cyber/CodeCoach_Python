# CodeCoach

Tells a parent what is wrong with their kid's code, in words a non-programmer can
read — including the bugs Python never mentions.

```
RUN_CodeCoach.bat              watch a folder, report on every save
python codecoach.py prog.py    check one file
python codecoach.py --folder . check everything underneath
```

Offline. No account, no subscription, no sign-up. Nothing leaves the machine.

## The problem this exists for

```
score = 0
scor = score + 10     # typo
print(score)          # prints 0. No error. Nothing.
```

That is the worst bug a beginner faces and it is **invisible**. Python is happy.
There is no traceback to search, nothing to paste into Google. The kid stares at
it, the parent asks what's wrong, and the answer is "I don't know."

Most beginner tools show either jargon or nothing. This shows what to say.

## What a parent gets

```
  maze.py
  ----------------------------------------------------------------
  ONE THING TO FIX
  It runs, but something below is not doing anything.

  STUCK FOR 26 MINUTES
  This is not 'not trying'. Same problem, 15 checks in a row.
  This is the moment to walk over and ask a question.

  SILENT - no error, it just does nothing

  Line 2: 'scor' is given a value and then never used
    The line sets 'scor', but nothing later reads it. The program
    runs and says nothing - which usually means the value was
    meant to go somewhere, or the name was spelled differently
    from the one being read.

  WHAT YOU COULD SAY
    "Can they find 'scor' again anywhere below that line?
    Compare the spelling with the name they meant to change."

  IF THEY WANT TO SEARCH
    python variable assigned but never used
```

And in the folder view:

```
  3 file(s)  ·  1 clean  ·  1 stuck
================================================================
    crash.py                     1 to fix
    good.py                      ok
    maze.py                      STUCK 26 minutes
```

## Two things it knows, and why both matter

**Silent failures.** Code that runs, throws nothing, and does the wrong thing.
Found by reading the code as a machine would — no execution needed.

**Errors, translated.** When Python does complain, the message is turned into
plain language with the one sentence a parent can say out loud. Jargon is banned
from that field: the tests assert that *concatenate*, *operand*, *subscriptable*,
*iterable* and *traceback* never appear in it, because a parent reading "can only
concatenate str" is the exact failure this tool exists to fix.

## The STUCK signal, which is the parent-facing point

A kid at a computer not making progress looks **identical** to a kid not trying.
A parent who cannot tell those apart defaults to "get off the computer", which is
the wrong call about half the time.

So CodeCoach times it. Same problem, fifteen minutes, and it says so — *"this is
not 'not trying', this is the moment to walk over and ask a question"* — and it
gives the question.

The timer is keyed on **what** is wrong, not on line numbers, so editing
whitespace to "try something" does not read as progress. Fixing one of two
problems does, and resets the clock. The state survives closing the window.

## The search line

When a kid does want to look it up, the raw error is the wrong thing to paste. A
whole traceback finds worse results than the one canonical line, and a beginner
does not know which line that is.

So the query is cleaned: file paths removed, line numbers removed, and **the
kid's own variable names replaced with `NAME`** — nobody has posted about `scor`,
so searching it returns nothing, which is the moment a kid concludes Google is
useless.

It also drops the `Did you mean: 'score'?` hint CPython 3.12+ adds. Helpful on
screen, worthless in a search box.

## Options

```
python codecoach.py prog.py            check one file, run it, explain
python codecoach.py --folder .         every .py underneath
python codecoach.py --watch --folder . stay open, refresh on every save
python codecoach.py --no-run prog.py   analyse only; NEVER executes anything
```

`--no-run` is the safe mode. It reads the file and never runs it, so it is safe
on code that would loop forever or delete something.

## Tests

```
python run_tests.py
```

**88 tests, exit code 0 only when everything passes.**

Two things about how they are written:

**Every error case runs a genuinely broken program.** The test writes the broken
code, executes it, and feeds the translator the real traceback CPython produced.
Nothing is tested against a string typed from memory.

**There is a suite of 32 correct programs that must produce zero findings** —
unused imports, unused parameters, `_` throwaways, tuple unpacking, f-strings,
comprehensions, `while True: break`, `global`, `__main__` guards. A detector that
cries wolf on working code gets switched off within a day, and then it helps
nobody. **False positives are treated as worse than misses**, and that guard is
proven to fail when removed.

## What it cannot do

- **Nothing about other languages.** Python only. GDScript, Lua, JavaScript would
  each need their own analysis, which is real work rather than a flag.
- **No runtime silent failures.** The detector is static, so it cannot see a
  `while` loop whose condition is a variable that never changes — that needs
  tracing the program as it runs. It catches the static class, which is most of
  the typo family, and says so rather than implying completeness.
- **It does not lock anything.** No parental controls, no process blocking, no
  screen-time enforcement. It reports. A tool that takes the computer away
  teaches a kid to defeat the tool; a tool that makes a parent useful teaches a
  kid to ask.

## Licence

MIT.
