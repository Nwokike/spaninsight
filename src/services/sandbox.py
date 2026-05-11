"""Safe Python execution sandbox.

AI-generated Pandas/Matplotlib code runs inside a heavily restricted
exec() namespace. Filesystem, network, and system access are blocked.
"""

from __future__ import annotations

import io
import logging
import signal
import sys
import traceback
from typing import Any

from core.constants import BLOCKED_TERMS, SANDBOX_TIMEOUT_SEC

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Raised when code fails validation or execution."""

    pass


def validate_code(code: str) -> tuple[bool, str]:
    """Scan code against blocked terms.

    Returns (is_safe, reason). If is_safe is False, reason explains why.
    """
    code_lower = code.lower()

    for term in BLOCKED_TERMS:
        if term.lower() in code_lower:
            return False, f"Blocked operation detected: '{term}'"

    # Check for excessive line count (possible infinite output)
    if code.count("\n") > 200:
        return False, "Code exceeds 200 lines — too complex for mobile execution."

    return True, ""


def execute_code(
    code: str,
    df: Any,
) -> dict:
    """Execute validated Python code in a restricted namespace.

    Args:
        code: Python source code (expected to use `df`, `pd`, `np`, `plt`).
        df: The pandas DataFrame to operate on.

    Returns:
        dict with keys:
            - "success": bool
            - "result": Any (the value of `result` variable if set in code)
            - "figure": matplotlib Figure or None
            - "stdout": captured print output
            - "error": error message or None
    """
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # Validate first
    is_safe, reason = validate_code(code)
    if not is_safe:
        return {
            "success": False,
            "result": None,
            "figure": None,
            "stdout": "",
            "error": f"Security: {reason}",
        }

    # Build restricted namespace
    namespace = {
        "df": df.copy(),  # Protect original data
        "pd": pd,
        "np": np,
        "plt": plt,
        "result": None,
        # Built-in safe functions
        "len": len,
        "range": range,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "sorted": sorted,
        "round": round,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "zip": zip,
        "enumerate": enumerate,
        "print": print,
        "True": True,
        "False": False,
        "None": None,
    }

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    # Close any existing figures to prevent memory leaks
    plt.close("all")

    try:
        # Timeout protection (Unix only — on Windows/Android we skip)
        if hasattr(signal, "SIGALRM"):
            def _timeout_handler(signum, frame):
                raise TimeoutError("Code execution exceeded time limit.")

            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(SANDBOX_TIMEOUT_SEC)

        exec(code, {"__builtins__": {}}, namespace)

        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)  # Cancel timeout

        # Check if a matplotlib figure was created
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

    except TimeoutError:
        return {
            "success": False,
            "result": None,
            "figure": None,
            "stdout": captured_output.getvalue(),
            "error": f"Execution timed out after {SANDBOX_TIMEOUT_SEC} seconds.",
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
        # Sanitize traceback — remove file paths
        sanitized = "\n".join(
            line for line in tb.split("\n")
            if "File" not in line or "<string>" in line
        )
        return {
            "success": False,
            "result": None,
            "figure": None,
            "stdout": captured_output.getvalue(),
            "error": f"{type(e).__name__}: {e}\n{sanitized}".strip(),
        }
    finally:
        sys.stdout = old_stdout
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
