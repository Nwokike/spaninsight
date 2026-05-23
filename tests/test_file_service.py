import pytest
import pandas as pd
import tempfile
import os
import orjson
from services.file_service import validate_file, load_dataframe, get_data_summary, df_to_csv_bytes, FileValidationError

def test_validate_file_invalid_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"some content")
        temp_name = f.name

    try:
        with pytest.raises(FileValidationError) as excinfo:
            validate_file(temp_name)
        assert "Unsupported file type" in str(excinfo.value)
    finally:
        os.remove(temp_name)

def test_validate_file_empty():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        temp_name = f.name

    try:
        with pytest.raises(FileValidationError) as excinfo:
            validate_file(temp_name)
        assert "empty" in str(excinfo.value).lower()
    finally:
        os.remove(temp_name)

def test_load_dataframe_csv_success():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
        f.write("A,B\n1,2\n3,4")
        temp_name = f.name

    try:
        df = load_dataframe(temp_name)
        assert len(df) == 2
        assert list(df.columns) == ["A", "B"]
    finally:
        os.remove(temp_name)

def test_load_dataframe_json_success():
    data = [{"X": 10, "Y": 20}, {"X": 30, "Y": 40}]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as f:
        f.write(orjson.dumps(data))
        temp_name = f.name

    try:
        df = load_dataframe(temp_name)
        assert len(df) == 2
        assert list(df.columns) == ["X", "Y"]
    finally:
        os.remove(temp_name)

def test_get_data_summary():
    df = pd.DataFrame({
        "Num": [1.5, 2.5, 3.5, None],
        "Cat": ["apple", "banana", "apple", "cherry"]
    })
    
    summary = get_data_summary(df)
    assert summary["shape"] == {"rows": 4, "columns": 2}
    assert summary["columns"]["Num"] == "float64"
    assert summary["columns"]["Cat"] in {"object", "str"}
    assert summary["nulls"] == {"Num": 1, "Cat": 0}
    assert "Num" in summary["describe"]
    assert len(summary["head"]) == 4

def test_df_to_csv_bytes():
    df = pd.DataFrame({"A": [1, 2]})
    res = df_to_csv_bytes(df)
    assert isinstance(res, bytes)
    assert b"A\n1\n2\n" in res or b"A\r\n1\r\n2\r\n" in res
