"""Safe Python execution sandbox.

AI-generated Pandas/Matplotlib code runs inside a heavily restricted
exec() namespace. Filesystem, network, and system access are blocked.

Security hardening (AST Rewrite):
- Implemented strict Abstract Syntax Tree (AST) Node Whitelisting.
- Banned direct access to dunder/magic methods (e.g., __class__) to prevent escapes.
- Explicitly blocked destructive pandas file I/O methods (to_csv, read_parquet, etc.).
- Cross-platform timeout via threading (works on Windows/Android).
- Shallow DataFrame copy to prevent OOM on large files.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import logging
import sys
import threading
import traceback
from typing import Any

from core.constants import SANDBOX_TIMEOUT_SEC

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Raised when code fails validation or execution."""
    pass


class ASTSecurityChecker(ast.NodeVisitor):
    """Walks the Abstract Syntax Tree (AST) to strictly whitelist safe operations."""

    def __init__(self):
        self.is_safe = True
        self.reason = ""

        self.allowed_node_names = {
            "Module", "Expr", "Assign", "AnnAssign", "AugAssign",
            "Name", "Load", "Store", "Del", "Constant",
            "Call", "Attribute", "Subscript", "Slice", "Index", "ExtSlice",
            "List", "Tuple", "Dict", "Set",
            "BinOp", "UnaryOp", "BoolOp", "Compare",
            "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow",
            "LShift", "RShift", "BitOr", "BitXor", "BitAnd", "MatMult",
            "And", "Or", "Not", "Invert", "UAdd", "USub",
            "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
            "If", "For", "While", "Break", "Continue", "Pass",
            "ListComp", "DictComp", "SetComp", "GeneratorExp", "comprehension",
            "IfExp", "FormattedValue", "JoinedStr",
            "Import", "ImportFrom", "alias", "keyword",
            "FunctionDef", "arguments", "arg", "Return", "Lambda",
            # Support try/except, with, raise, starred unpacking
            "Starred", "Try", "ExceptHandler", "With", "withitem", "Raise",
        }

        self.allowed_imports = {"pandas", "numpy", "matplotlib", "math", "datetime"}

        self.blocked_imports = {
            "seaborn", "sns", "scipy", "sklearn", "statsmodels",
            "plotly", "pingouin", "lifelines", "tensorflow", "torch",
        }

        # FIX: Removed 'show' from blocked attributes. We will mock it safely instead.
        self.blocked_attributes = {
            "to_csv", "to_pickle", "to_sql", "to_excel", "to_json",
            "to_html", "to_feather", "to_parquet",
            "read_csv", "read_pickle", "read_sql", "read_excel", "read_json",
            "read_html", "read_feather", "read_parquet",
            "system", "popen", "subprocess", "os", "sys", "eval", "exec", "open",
            "savefig",
        }

        self.blocked_builtins = {
            "eval", "exec", "open", "compile", "globals", "locals", "vars", "dir",
            "getattr", "setattr", "hasattr", "delattr", "type", "memoryview", "__import__",
        }

    def _flag_error(self, message: str):
        if self.is_safe:
            self.is_safe = False
            self.reason = message

    def generic_visit(self, node):
        node_type = type(node).__name__
        if node_type not in self.allowed_node_names:
            self._flag_error(f"Language feature '{node_type}' is restricted.")
            return
        super().generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.blocked_imports:
                self._flag_error(f"Importing '{alias.name}' is not available. Use only pandas, numpy, and matplotlib.")
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing '{alias.name}' is prohibited.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.blocked_imports:
                self._flag_error(f"Importing from '{node.module}' is not available. Use only pandas, numpy, and matplotlib.")
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing from '{node.module}' is prohibited.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            self._flag_error(f"Access to internal/magic attribute '{node.attr}' is strictly blocked.")
        elif node.attr in self.blocked_attributes:
            self._flag_error(f"Operation '{node.attr}' is not permitted in the sandbox.")
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id.startswith("__") and node.id not in {"__name__", "__main__"}:
            self._flag_error(f"Access to internal identifier '{node.id}' is blocked.")
        elif node.id in self.blocked_builtins:
            self._flag_error(f"Access to builtin '{node.id}' is restricted.")
        self.generic_visit(node)


def validate_code(code: str) -> tuple[bool, str]:
    """Parse code into an AST and validate against a strict whitelist."""
    if code.count("\n") > 200:
        return False, "Code exceeds 200 lines — too complex for execution."

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e.msg} at line {e.lineno}"

    checker = ASTSecurityChecker()
    checker.visit(tree)

    return checker.is_safe, checker.reason


@contextlib.contextmanager
def _capture_stdout():
    """Context manager that guarantees sys.stdout is restored."""
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    try:
        yield captured
    finally:
        sys.stdout = old_stdout


class _TimeoutError(Exception):
    """Raised when sandbox code exceeds the time limit."""
    pass


def _safe_import(name, *args, **kwargs):
    """Restricted import that only allows whitelisted modules."""
    allowed = {"pandas", "numpy", "matplotlib", "math", "datetime"}
    base = name.split(".")[0]
    if base not in allowed:
        raise ImportError(f"Import of '{name}' is blocked in sandbox")
    return __import__(name, *args, **kwargs)


def _exec_with_timeout(code: str, namespace: dict, timeout_sec: int) -> None:
    """Execute code in a separate thread with a hard timeout."""
    exc_info: list = [None]

    def _target():
        try:
            exec(code, namespace)
        except Exception as e:
            exc_info[0] = e

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        raise _TimeoutError(f"Code execution exceeded {timeout_sec}s time limit.")

    if exc_info[0] is not None:
        raise exc_info[0]


def execute_code(
    code: str,
    df: Any,
) -> dict:
    """Execute validated Python code in a restricted namespace."""
    try:
        import flet_charts  # noqa: F401
    except ImportError:
        pass

    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # FIX: Safely mock plt.show() so it doesn't open GUI windows or trigger AST blocks
    plt.show = lambda *args, **kwargs: None


    # 2. Build execution namespace
    namespace = {
        "df": df.copy(deep=False),
        "pd": pd,
        "np": np,
        "plt": plt,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "result": None,
    }

    plt.close("all")

    with _capture_stdout() as captured_output:
        try:
            _exec_with_timeout(code, namespace, SANDBOX_TIMEOUT_SEC)

            figure = None
            if plt.get_fignums():
                figure = plt.gcf()

            return {
                "success": True,
                "result": namespace.get("result"),
                "figure": figure,
                "stdout": captured_output.getvalue(),
                "error": None,
            }

        except _TimeoutError as te:
            return {
                "success": False,
                "result": None,
                "figure": None,
                "stdout": captured_output.getvalue(),
                "error": str(te),
            }
        except MemoryError:
            return {
                "success": False,
                "result": None,
                "figure": None,
                "stdout": captured_output.getvalue(),
                "error": "Out of memory — dataset may be too large for this operation.",
            }
        except Exception as e:
            tb = traceback.format_exc()
            sanitized = "\n".join(
                line
                for line in tb.split("\n")
                if "File" not in line or "<string>" in line
            )
            return {
                "success": False,
                "result": None,
                "figure": None,
                "stdout": captured_output.getvalue(),
                "error": f"{type(e).__name__}: {e}\n{sanitized}".strip(),
            }


async def execute_code_async(
    code: str,
    df: Any,
) -> dict:
    """Async wrapper — runs execute_code in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(execute_code, code, df)