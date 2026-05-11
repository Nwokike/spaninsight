"""File import service — CSV/Excel loading with validation.

Handles the complete pipeline from file selection to pandas DataFrame,
enforcing the 15MB size limit to prevent Android OOM crashes.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from core.constants import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB

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
        raise FileValidationError("Could not read file. It may have been moved or deleted.")

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

    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".csv":
            # Try UTF-8 first, fall back to latin-1 for Excel-exported CSVs
            try:
                df = pd.read_csv(file_path, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding="latin-1")
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, engine="openpyxl")
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

    Includes everything pandas can tell us: shape, dtypes, head, tail,
    describe, nunique, null counts, and top values.
    Truncates long strings and limits column counts to keep payload safe.
    """
    # 1. Shape and basics
    summary = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
    }

    # 2. Column-level mapping (Dtypes + Nulls + Unique)
    cols = []
    # Limit to first 25 columns to avoid massive payloads for wide datasets
    target_cols = df.columns[:25]
    for col in target_cols:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "nulls": int(df[col].isnull().sum()),
            "unique": int(df[col].nunique()),
        }
        # Add basic stats for numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            d = df[col].describe()
            col_info["stats"] = {
                "mean": round(float(d.get("mean", 0)), 2),
                "min": float(d.get("min", 0)),
                "max": float(d.get("max", 0)),
            }
        else:
            # Top values for categorical
            top = df[col].value_counts().head(3)
            col_info["top_values"] = {str(k)[:50]: int(v) for k, v in top.items()}
        cols.append(col_info)
    summary["columns"] = cols

    # 3. Head and tail (Truncated strings)
    def _safe_df_dict(sub_df):
        # Truncate any cell that is a string and > 100 chars
        sub_df = sub_df.copy()
        for col in sub_df.columns:
            if sub_df[col].dtype == "object":
                sub_df[col] = sub_df[col].apply(lambda x: str(x)[:100] + "..." if len(str(x)) > 100 else x)
        return sub_df.to_dict(orient="records")

    try:
        summary["head_5_rows"] = _safe_df_dict(df.head(5))
        summary["tail_3_rows"] = _safe_df_dict(df.tail(3))
    except Exception:
        summary["head_5_rows"] = "unavailable"

    # 4. Describe overall (if not too wide)
    if len(df.columns) <= 15:
        try:
            desc = df.describe(include="all").to_dict()
            # Handled NaN by str() if needed
            summary["pandas_describe"] = desc
        except Exception:
            pass

    return summary


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")
