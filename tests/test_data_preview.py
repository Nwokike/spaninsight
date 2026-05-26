"""Tests for data_preview component."""

import numpy as np
import pandas as pd
from components.data_preview import _format_cell, build_data_preview


class TestFormatCell:
    def test_float_integer_display(self):
        assert _format_cell(3.0) == "3"

    def test_float_decimal_display(self):
        assert _format_cell(3.14) == "3.14"

    def test_nan_display(self):
        assert _format_cell(float("nan")) == "—"

    def test_none_display(self):
        assert _format_cell(None) == "—"

    def test_long_string_truncated(self):
        s = "A" * 50
        result = _format_cell(s)
        assert len(result) == 41  # 40 chars + ellipsis
        assert result.endswith("…")

    def test_short_string_not_truncated(self):
        assert _format_cell("hello") == "hello"

    def test_list_display(self):
        assert _format_cell([1, 2, 3]) == "1, 2, 3"

    def test_empty_list_display(self):
        assert _format_cell([]) == "—"

    def test_numpy_scalar_0d(self):
        val = np.float64(3.14)
        result = _format_cell(val)
        assert result == "3.14"

    def test_numpy_array(self):
        val = np.array([1, 2, 3])
        result = _format_cell(val)
        assert "1" in result and "2" in result

    def test_empty_numpy_array(self):
        val = np.array([])
        assert _format_cell(val) == "—"


class TestBuildDataPreview:
    def test_builds_with_small_df(self):
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        col = build_data_preview(df)
        assert col is not None

    def test_builds_with_empty_df(self):
        df = pd.DataFrame()
        col = build_data_preview(df)
        assert col is not None
