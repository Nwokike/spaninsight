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
    """Generate a comprehensive summary for the AI.

    Includes everything pandas can tell us: shape, dtypes, head, tail,
    describe, nunique, null counts, memory usage, and top values.
    The AI should NEVER have to guess — this is definitive.
    """
    import io

    # Basic shape
    summary = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "column_names": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
    }

    # Head and tail (as dicts for JSON serialization)
    try:
        summary["head_5_rows"] = df.head(5).to_dict(orient="records")
    except Exception:
        summary["head_5_rows"] = str(df.head(5))

    try:
        summary["tail_3_rows"] = df.tail(3).to_dict(orient="records")
    except Exception:
        summary["tail_3_rows"] = str(df.tail(3))

    # Describe (numeric stats)
    try:
        desc = df.describe(include="all")
        # Convert to dict, handling NaN
        summary["describe"] = {}
        for col in desc.columns:
            summary["describe"][col] = {
                stat: (round(float(val), 4) if pd.notna(val) and isinstance(val, (int, float)) else str(val))
                for stat, val in desc[col].items()
                if pd.notna(val)
            }
    except Exception:
        summary["describe"] = "unavailable"

    # Null counts and percentages
    null_counts = df.isnull().sum()
    summary["null_info"] = {
        col: {
            "count": int(null_counts[col]),
            "percent": round(null_counts[col] / len(df) * 100, 1),
        }
        for col in df.columns
        if null_counts[col] > 0
    }

    # Unique value counts
    summary["unique_counts"] = {col: int(df[col].nunique()) for col in df.columns}

    # Per-column detail
    columns_detail = []
    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "nulls": int(df[col].isnull().sum()),
            "unique": int(df[col].nunique()),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            d = df[col].describe()
            col_info["stats"] = {
                "mean": round(float(d.get("mean", 0)), 2),
                "std": round(float(d.get("std", 0)), 2),
                "min": float(d.get("min", 0)),
                "25%": float(d.get("25%", 0)),
                "50%": float(d.get("50%", 0)),
                "75%": float(d.get("75%", 0)),
                "max": float(d.get("max", 0)),
            }
        else:
            top = df[col].value_counts().head(5)
            col_info["top_values"] = {str(k): int(v) for k, v in top.items()}
        columns_detail.append(col_info)

    summary["columns"] = columns_detail
    return summary


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")
