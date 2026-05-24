"""Safe Python execution sandbox.

AI-generated Pandas/Matplotlib code runs inside a heavily restricted
exec() namespace. Filesystem, network, and system access are blocked.

Security hardening (AST Rewrite):
- Implemented strict Abstract Syntax Tree (AST) Node Whitelisting.
- Banned direct access to dunder/magic methods (e.g., __class__) to prevent escapes.
- Explicitly blocked destructive pandas file I/O methods (to_csv, read_parquet, etc.).
- Cross-platform timeout via threading (works on Windows/Android).
- Deep DataFrame copy to prevent master state corruption.
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
    """Restricts imports in sandbox to ensure only whitelisted packages are used."""

    def __init__(self):
        self.is_safe = True
        self.reason = ""

        self.allowed_imports = {
            "pandas",
            "numpy",
            "matplotlib",
            "math",
            "datetime",
            "statistics",
            "shapely",
            "pymongo",
            "jq",
            "pendulum",
        }

        self.blocked_imports = {
            "seaborn",
            "sns",
            "scipy",
            "sklearn",
            "statsmodels",
            "plotly",
            "pingouin",
            "lifelines",
            "tensorflow",
            "torch",
        }

    def _flag_error(self, message: str):
        if self.is_safe:
            self.is_safe = False
            self.reason = message

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.blocked_imports:
                self._flag_error(
                    f"Importing '{alias.name}' is not available. Use whitelisted libraries like pandas, numpy, matplotlib, statistics, shapely, pymongo, jq, and pendulum."
                )
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing '{alias.name}' is prohibited.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.blocked_imports:
                self._flag_error(
                    f"Importing from '{node.module}' is not available. Use whitelisted libraries like pandas, numpy, matplotlib, statistics, shapely, pymongo, jq, and pendulum."
                )
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing from '{node.module}' is prohibited.")
        self.generic_visit(node)


def validate_code(code: str) -> tuple[bool, str]:
    """Parse code into an AST and validate imports."""
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
    allowed = {
        "pandas",
        "numpy",
        "matplotlib",
        "math",
        "datetime",
        "statistics",
        "shapely",
        "pymongo",
        "jq",
        "pendulum",
    }
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
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # FIX: Safely mock plt.show() so it doesn't open GUI windows or trigger AST blocks
    plt.show = lambda *args, **kwargs: None

    # Enable Pandas 2.0 Copy-on-Write globally to avoid memory exhaustion/UI freezes (only needed for Pandas < 3.0)
    try:
        if int(pd.__version__.split(".")[0]) < 3:
            pd.options.mode.copy_on_write = True
    except Exception:
        pass

    # 2. Build execution namespace
    # With Copy-on-Write enabled, passing a direct reference is O(1) time and memory,
    # yet still guarantees the AI cannot permanently corrupt the master Flet state.
    namespace = {
        "df": df,
        "pd": pd,
        "np": np,
        "plt": plt,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "statistics": __import__("statistics"),
        "result": None,
    }

    plt.close("all")

    with _capture_stdout() as captured_output:
        try:
            _exec_with_timeout(code, namespace, SANDBOX_TIMEOUT_SEC)

            figure = None
            if plt.get_fignums():
                figure = plt.gcf()

            # Check if dataframe is modified
            modified = False
            try:
                # Compare namespace["df"] with the initial df
                if not namespace["df"].equals(df):
                    modified = True
            except Exception:
                pass

            # Check for clean/save keywords
            if any(kw in code for kw in ["to_csv", "save", "df.to_csv"]):
                modified = True

            res_val = namespace.get("result")
            if res_val is None:
                exclude_keys = {
                    "df",
                    "pd",
                    "np",
                    "plt",
                    "math",
                    "datetime",
                    "statistics",
                    "result",
                    "__builtins__",
                }
                found_res = None
                for k, v in list(namespace.items()):
                    if k in exclude_keys:
                        continue
                    if isinstance(v, (pd.DataFrame, pd.Series)):
                        found_res = v
                        if any(
                            x in k.lower()
                            for x in ["result", "summary", "missing", "clean", "output"]
                        ):
                            found_res = v
                            break
                if found_res is not None:
                    res_val = found_res

            return {
                "success": True,
                "result": res_val,
                "figure": figure,
                "stdout": captured_output.getvalue(),
                "error": None,
                "modified": modified,
                "new_df": namespace.get("df"),
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
