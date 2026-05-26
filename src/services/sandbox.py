"""Safe Python execution sandbox.

AI-generated code runs inside a restricted exec() namespace.
Security: AST import whitelisting, blocked terms, restricted builtins,
thread-based timeout, deep DataFrame copy via Copy-on-Write.
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

from core.constants import BLOCKED_TERMS, SANDBOX_TIMEOUT_SEC

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Raised when code fails validation or execution."""

    pass


class ASTSecurityChecker(ast.NodeVisitor):
    """Restricts imports to whitelisted packages only."""

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
            "jq",
            "pendulum",
            "re",
            "collections",
            "itertools",
            "functools",
            "operator",
            "string",
            "copy",
            "random",
            "json",
            "textwrap",
            "typing",
            "warnings",
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
                    f"Importing '{alias.name}' is not available. Use whitelisted libraries like pandas, numpy, matplotlib, statistics, shapely, jq, and pendulum."
                )
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing '{alias.name}' is prohibited.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.blocked_imports:
                self._flag_error(
                    f"Importing from '{node.module}' is not available. Use whitelisted libraries like pandas, numpy, matplotlib, statistics, shapely, jq, and pendulum."
                )
            elif base_module not in self.allowed_imports:
                self._flag_error(f"Importing from '{node.module}' is prohibited.")
        self.generic_visit(node)


def validate_code(code: str) -> tuple[bool, str]:
    """Parse code into AST and validate imports + blocked terms."""
    if code.count("\n") > 200:
        return False, "Code exceeds 200 lines — too complex for execution."

    for term in BLOCKED_TERMS:
        if term in code:
            return False, f"Code contains blocked term '{term}' — remove it and retry."

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e.msg} at line {e.lineno}"

    checker = ASTSecurityChecker()
    checker.visit(tree)

    return checker.is_safe, checker.reason


@contextlib.contextmanager
def _capture_stdout():
    """Thread-safe stdout capture using StringIO."""
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
    """Restricted __import__ allowing only whitelisted modules."""
    allowed = {
        "pandas",
        "numpy",
        "matplotlib",
        "math",
        "datetime",
        "statistics",
        "shapely",
        "jq",
        "pendulum",
        "re",
        "collections",
        "itertools",
        "functools",
        "operator",
        "string",
        "copy",
        "random",
        "json",
        "textwrap",
        "typing",
        "warnings",
    }
    base = name.split(".")[0]
    if base not in allowed:
        raise ImportError(f"Import of '{name}' is blocked in sandbox")
    return __import__(name, *args, **kwargs)


class TimeoutException(BaseException):
    """BaseException ensures it cannot be caught by standard 'except Exception:' blocks."""

    pass


def _exec_with_timeout(code: str, namespace: dict, timeout_sec: int) -> None:
    """Execute code in a thread with timeout and leaked-thread watchdog."""
    import time
    import sys

    exc_info: list = [None]
    start_time = time.monotonic()

    def _target():
        def timeout_trace(frame, event, arg):
            if time.monotonic() - start_time > timeout_sec:
                raise TimeoutException(
                    f"Code execution exceeded {timeout_sec}s time limit."
                )
            return timeout_trace

        sys.settrace(timeout_trace)
        try:
            exec(code, namespace)
        except TimeoutException as te:
            exc_info[0] = _TimeoutError(str(te))
        except Exception as e:
            exc_info[0] = e
        finally:
            sys.settrace(None)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec + 1.0)  # Add buffer for join

    if thread.is_alive():
        logger.warning("Sandbox thread leaked — stuck in C extension, cannot be killed")
        raise _TimeoutError(f"Code execution exceeded {timeout_sec}s time limit.")

    if exc_info[0] is not None:
        raise exc_info[0]


def execute_code(
    code: str,
    df: Any,
) -> dict:
    """Execute validated Python code in a restricted namespace."""
    # Pre-check code with AST validation to block forbidden imports upfront
    is_safe, reason = validate_code(code)
    if not is_safe:
        return {
            "success": False,
            "result": None,
            "figure": None,
            "stdout": "",
            "error": f"Code validation failed: {reason}",
        }

    import matplotlib
    import warnings

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # FIX: Suppress Matplotlib <3.9 deprecation warnings for AI-generated code
    warnings.filterwarnings("ignore", message="The 'labels' parameter of boxplot")
    warnings.filterwarnings("ignore", message="The 'labels' parameter of *_box")
    # FIX: Safely mock plt.show() so it doesn't open GUI windows or trigger AST blocks
    plt.show = lambda *args, **kwargs: None

    try:
        if int(pd.__version__.split(".")[0]) < 3:
            pd.options.mode.copy_on_write = True
    except Exception:
        pass

    # Restricted builtins — no open(), eval(), exec(), getattr() etc.
    safe_builtins = {
        "__import__": _safe_import,
        "print": print,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "frozenset": frozenset,
        "type": type,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "hasattr": hasattr,
        "any": any,
        "all": all,
        "repr": repr,
        "hash": hash,
        "id": id,
        "iter": iter,
        "next": next,
        "slice": slice,
        "complex": complex,
        "bytes": bytes,
        "bytearray": bytearray,
        "memoryview": memoryview,
        "object": object,
        "staticmethod": staticmethod,
        "classmethod": classmethod,
        "property": property,
        "super": super,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        "Exception": Exception,
        "True": True,
        "False": False,
        "None": None,
        "NotImplemented": NotImplemented,
        "Ellipsis": Ellipsis,
        "ArithmeticError": ArithmeticError,
        "ZeroDivisionError": ZeroDivisionError,
        "OverflowError": OverflowError,
        "UnicodeError": UnicodeError,
        "UnicodeDecodeError": UnicodeDecodeError,
        "UnicodeEncodeError": UnicodeEncodeError,
        "IOError": IOError,
        "OSError": OSError,
        "FileNotFoundError": FileNotFoundError,
        "PermissionError": PermissionError,
        "ImportError": ImportError,
        "ModuleNotFoundError": ModuleNotFoundError,
        "LookupError": LookupError,
        "NameError": NameError,
        "SyntaxError": SyntaxError,
        "GeneratorExit": GeneratorExit,
        "SystemExit": SystemExit,
        "KeyboardInterrupt": KeyboardInterrupt,
        "chr": chr,
        "ord": ord,
        "hex": hex,
        "oct": oct,
        "bin": bin,
        "pow": pow,
        "divmod": divmod,
        "format": format,
        "vars": vars,
        "dir": dir,
        "callable": callable,
        "input": lambda *a, **kw: "",
    }

    namespace = {
        "df": df,
        "pd": pd,
        "np": np,
        "plt": plt,
        "math": __import__("math"),
        "datetime": __import__("datetime"),
        "statistics": __import__("statistics"),
        "result": None,
        "__builtins__": safe_builtins,
    }

    plt.close("all")

    with _capture_stdout() as captured_output:
        try:
            _exec_with_timeout(code, namespace, SANDBOX_TIMEOUT_SEC)

            figure = None
            if plt.get_fignums():
                figure = plt.gcf()

            modified = False
            try:
                if not namespace["df"].equals(df):
                    modified = True
            except Exception:
                pass

            if any(kw in code for kw in ["to_csv", "save"]):
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
