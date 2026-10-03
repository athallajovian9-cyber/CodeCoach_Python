"""Silent failures: code that runs, throws nothing, and does the wrong thing.

This is the hard half. The error translator catches what Python complains about;
this catches what it does not.

```
score = 0
scor = score + 10     # typo
print(score)          # 0. No exception. Nothing to google.
```

A kid cannot search for this, and a parent cannot see it. The only way to find
it is to read the code as a machine would.

The design constraint that matters most is FALSE POSITIVES. A tool that cries
wolf on correct code gets ignored within a day, and then it helps nobody. So
every check here is deliberately narrow, and there is a test suite of CORRECT
programs that must produce zero findings.

Static only: no execution, no imports, no side effects. `ast.parse` and nothing
else, so this is safe to run on anything and cannot hang.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
class Finding:
    kind: str          # stable identifier, for tests
    line: int
    name: str
    title: str
    plain: str
    parent_says: str
    fix_hint: str
    search: str = ""


def _is_throwaway(name: str) -> bool:
    """Names a programmer deliberately ignores.

    A leading underscore is the universal convention for "I know, I do not need
    it", and flagging those is the fastest way to make a tool annoying.
    """
    return name.startswith("_")


class _Usage(ast.NodeVisitor):
    """Collect every name that is STORED and every name that is LOADED.

    Deliberately not scope-aware for the headline check. A name read anywhere in
    the file counts as used, including from a nested function - being generous
    here means fewer false positives, and a typo'd variable is never read
    anywhere at all, so the check still catches the case it exists for.
    """

    def __init__(self):
        self.stores: dict[str, list[ast.AST]] = {}
        self.loads: set[str] = set()
        self.calls: set[str] = set()
        self.defs: dict[str, ast.AST] = {}

    def _store(self, name: str, node: ast.AST):
        self.stores.setdefault(name, []).append(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self._store(node.id, node)
        else:
            self.loads.add(node.id)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg):
        # A parameter is "stored" by the call, not by the code.
        self._store(node.arg, node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # A nested def is both a load of its own name (for recursion) and a def.
        self.defs[node.name] = node
        self._store(node.name, node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defs[node.name] = node
        self._store(node.name, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            self.calls.add(f.id)
        elif isinstance(f, ast.Attribute):
            self.calls.add(f.attr)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for a in node.names:
            self._store((a.asname or a.name).split(".")[0], node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for a in node.names:
            self._store(a.asname or a.name, node)
        self.generic_visit(node)


class _LoopCheck(ast.NodeVisitor):
    """Loops whose body cannot run at all."""

    def __init__(self):
        self.findings: list[Finding] = []

    def _empty_iterable(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "range":
                args = node.args
                if len(args) == 1 and isinstance(args[0], ast.Constant) and args[0].value == 0:
                    return True
                if (len(args) == 2 and all(isinstance(a, ast.Constant) for a in args)
                        and args[0].value == args[1].value):
                    return True
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and not node.elts:
            return True
        return False

    def visit_For(self, node: ast.For):
        if self._empty_iterable(node.iter):
            self.findings.append(Finding(
                kind="loop_never_runs",
                line=node.lineno,
                name="",
                title="This loop can never run",
                plain=("The loop is told to go through a list or a range that is empty, "
                       "so the lines inside it never happen even once."),
                parent_says="How many times is that loop supposed to go round? Is that number ever more than zero?",
                fix_hint="If it should repeat, check the number. range(0) repeats nothing.",
            ))
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        t = node.test
        if isinstance(t, ast.Constant) and not t.value:
            self.findings.append(Finding(
                kind="loop_never_runs",
                line=node.lineno,
                name="",
                title="This loop can never run",
                plain="The condition is False to begin with, so the inside never happens.",
                parent_says="What has to be true for this loop to start? Is it true at the start?",
                fix_hint="Set the condition so it is True when the loop should begin.",
            ))
        self.generic_visit(node)


class _ConstantCondition(ast.NodeVisitor):
    """`if True:` / `if False:` - one branch is dead on arrival."""

    def __init__(self):
        self.findings: list[Finding] = []

    def visit_If(self, node: ast.If):
        t = node.test
        if isinstance(t, ast.Constant) and isinstance(t.value, bool):
            self.findings.append(Finding(
                kind="constant_condition",
                line=node.lineno,
                name="",
                title=f"This 'if' is always {'true' if t.value else 'false'}",
                plain=("The condition is a fixed value, so one of the two branches "
                       "never runs. Usually a leftover from testing, or a comparison "
                       "that was replaced by a literal."),
                parent_says="Was that meant to be a test, like comparing two things, rather than just True or False?",
                fix_hint=("If a branch should be reachable, the condition needs to be a real "
                          "comparison. If not, delete the dead branch so it stops misleading."),
            ))
        self.generic_visit(node)


def _findings(source: str) -> list[Finding]:
    """All checks over one parsed module."""
    tree = ast.parse(source)
    usage = _Usage()
    usage.visit(tree)

    out: list[Finding] = []

    # --- assigned and never read -------------------------------------------------
    # The headline check. This is the typo case: a new name is created, the real
    # one is never updated, and nothing complains.
    for name, nodes in usage.stores.items():
        if _is_throwaway(name):
            continue
        if name in usage.loads:
            continue
        if name in usage.calls:
            continue
        # A function or class defined at module level is an export, not a mistake.
        node = nodes[0]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        # An import that is unused is a different, milder problem - and flagging
        # every unused import would drown the signal a beginner actually needs.
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        # A parameter that is accepted and not used is extremely common and
        # completely normal, especially in callbacks.
        if isinstance(node, ast.arg):
            continue

        line = getattr(node, "lineno", 0)
        out.append(Finding(
            kind="assigned_never_used",
            line=line,
            name=name,
            title=f"'{name}' is given a value and then never used",
            plain=(f"The line sets '{name}', but nothing later reads it. The program runs "
                   "and says nothing - which usually means the value was meant to go "
                   "somewhere, or the name was spelled differently from the one being read."),
            parent_says=(f"Can they find '{name}' again anywhere below that line? "
                         "Compare the spelling with the name they meant to change."),
            fix_hint=(f"Either '{name}' is a typo for a name used elsewhere, or the value "
                      "needs to be used. Nothing is broken at runtime - this is a silent no-op."),
            search="python variable assigned but never used",
        ))

    # --- uncalled functions, but only in an obvious script -------------------
    # In a module, an uncalled function is normal. In a single-file script with no
    # imports and no __main__ guard, it is almost always "I wrote it and forgot to
    # call it".
    looks_like_script = not any(
        isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)
    )
    guarded = "__name__" in usage.loads
    if looks_like_script and not guarded:
        for name, node in usage.defs.items():
            if _is_throwaway(name) or name in usage.calls:
                continue
            if name in usage.loads:
                continue
            out.append(Finding(
                kind="function_never_called",
                line=getattr(node, "lineno", 0),
                name=name,
                title=f"'{name}' is written but never called",
                plain=(f"The function '{name}' is defined and then nothing ever runs it. "
                       "It will not do anything until something calls it."),
                parent_says=f"Is '{name}' supposed to be used somewhere? Where does the program call it?",
                fix_hint=f"Call it: {name}()  - and check the spelling matches exactly.",
                search="python function defined but never called",
            ))

    loops = _LoopCheck()
    loops.visit(tree)
    out.extend(loops.findings)

    conds = _ConstantCondition()
    conds.visit(tree)
    out.extend(conds.findings)

    out.sort(key=lambda f: (f.line, f.kind))
    return out


def analyse(source: str) -> list[Finding]:
    """Find silent failures in a program.

    Returns [] for a program with nothing wrong, and [] for one that does not
    parse - syntax errors belong to the error translator, and reporting both at
    once is noise.
    """
    try:
        return _findings(source)
    except SyntaxError:
        return []


def analyse_file(path) -> list[Finding]:
    from pathlib import Path
    return analyse(Path(path).read_text(encoding="utf-8", errors="replace"))
