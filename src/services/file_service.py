"""File import service — CSV/Excel loading with validation.

Handles the complete pipeline from file selection to pandas DataFrame,
enforcing the 100MB size limit to keep Android stable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Raised when a file fails validation checks."""

    pass


def validate_file(file_path: str) -> None:
    """Validate file extension and size. Raises FileValidationError on failure."""
    path = Path(file_path)

    # Check extension
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type: '{ext}'. "
            f"Please use CSV or Excel files ({', '.join(ALLOWED_EXTENSIONS)})."
        )

    # Check size
    try:
        size = os.path.getsize(file_path)
    except OSError:
        raise FileValidationError(
            "Could not read file. It may have been moved or deleted."
        )

    if size > MAX_FILE_SIZE_BYTES:
        size_mb = size / (1024 * 1024)
        raise FileValidationError(
            f"File is too large ({size_mb:.1f} MB). "
            f"Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
        )

    if size == 0:
        raise FileValidationError("File is empty. Please select a file with data.")


def load_dataframe(file_path: str) -> pd.DataFrame:
    """Load a CSV or Excel file into a pandas DataFrame.

    Raises FileValidationError on any loading failure.
    """
    validate_file(file_path)

    import pandas as pd

    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".csv":
            # Try UTF-8 first, fall back to latin-1 for Excel-exported CSVs
            try:
                df = pd.read_csv(file_path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding="latin-1")
        elif ext == ".json":
            # try reading JSON line-delimited (default)
            try:
                df = pd.read_json(file_path, lines=True)
            except ValueError:
                # fallback: try reading as normal JSON array
                df = pd.read_json(file_path)
        elif ext == ".xlsx":
            # PERFORMANCE FIX: Swap openpyxl for python_calamine (10x faster)
            import python_calamine  # noqa: F401

            df = pd.read_excel(file_path, engine="calamine")
        else:
            raise FileValidationError(f"Unsupported format: {ext}")

    except FileValidationError:
        raise
    except Exception as e:
        raise FileValidationError(f"Failed to read file: {e}")

    if df.empty:
        raise FileValidationError("File loaded but contains no data rows.")

    if len(df.columns) == 0:
        raise FileValidationError("File loaded but contains no columns.")

    logger.info(
        "Loaded %s: %d rows × %d columns",
        path.name,
        len(df),
        len(df.columns),
    )
    return df


def get_data_summary(df: pd.DataFrame) -> dict:
    """Generate a comprehensive but token-efficient summary for the AI.

    Safely truncates categorical summaries to prevent UI locking on massive UUID/Text columns.
    """

    # PERFORMANCE FIX: Prevent thread freezing on describe(include="all")
    try:
        num_desc = df.select_dtypes(include="number").describe().round(2).to_dict()
        # Cap categorical summarization to first 10 text cols to prevent thread blocking
        cat_desc = (
            df.select_dtypes(exclude="number")
            .iloc[:, :10]
            .describe()
            .fillna("")
            .to_dict()
        )
        safe_describe = {**num_desc, **cat_desc}
    except Exception:
        safe_describe = {}

    summary = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "columns": {str(c): str(df[c].dtype) for c in df.columns[:30]},
        "nulls": {str(c): int(df[c].isnull().sum()) for c in df.columns[:30]},
        "describe": safe_describe,
        "head": [],
        "tail": [],
    }

    # Safe head + tail — truncate long strings
    def _safe_rows(sub_df):
        obj_cols = [c for c in sub_df.columns if sub_df[c].dtype == "object"]
        if obj_cols:
            sub_df = sub_df.copy()
            for col in obj_cols:
                sub_df[col] = sub_df[col].apply(
                    lambda x: (
                        str(x)[:100] + "..."
                        if isinstance(x, str) and len(x) > 100
                        else x
                    )
                )
        return sub_df.to_dict(orient="records")

    try:
        summary["head"] = _safe_rows(df.head(20))
        summary["tail"] = _safe_rows(df.tail(20))
    except Exception:
        summary["head"] = "unavailable"

    return summary


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")
