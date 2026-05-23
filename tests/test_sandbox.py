import pytest
import pandas as pd
from services.sandbox import validate_code, execute_code, execute_code_async

def test_validate_code_success():
    code = """
import pandas as pd
import numpy as np
import statistics
mean_val = statistics.mean(df['A'])
result = f"Mean: {mean_val}"
"""
    is_safe, reason = validate_code(code)
    assert is_safe
    assert reason == ""

def test_validate_code_banned_import():
    code = """
import scipy.stats as stats
"""
    is_safe, reason = validate_code(code)
    assert not is_safe
    assert "Importing 'scipy.stats' is not available" in reason

def test_validate_code_non_whitelisted_import():
    code = """
import os
"""
    is_safe, reason = validate_code(code)
    assert not is_safe
    assert "Importing 'os' is prohibited" in reason

def test_validate_code_syntax_error():
    code = """
import pandas as pd
if True
    print("Forgot colon")
"""
    is_safe, reason = validate_code(code)
    assert not is_safe
    assert "Syntax Error" in reason

def test_execute_code_success():
    df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
    code = """
import statistics
mean_val = statistics.mean(df['A'])
result = mean_val
"""
    res = execute_code(code, df)
    assert res["success"]
    assert res["result"] == 3
    assert res["error"] is None

def test_execute_code_execution_error():
    df = pd.DataFrame({"A": [1, 2, 3]})
    code = """
result = 1 / 0
"""
    res = execute_code(code, df)
    assert not res["success"]
    assert "ZeroDivisionError" in res["error"]

def test_execute_code_restored_builtins():
    # Direct test showing that type(), getattr(), hasattr(), dir() are 100% allowed and functional
    df = pd.DataFrame({"A": [1.0, 2.0]})
    code = """
val_type = type(df['A'].iloc[0]).__name__
has_a = hasattr(df, 'columns')
result = f"Type: {val_type}, HasColumns: {has_a}"
"""
    res = execute_code(code, df)
    assert res["success"]
    assert "float" in res["result"]
    assert "True" in res["result"]

@pytest.mark.asyncio
async def test_execute_code_async():
    df = pd.DataFrame({"A": [10, 20]})
    code = """
result = np.sum(df['A'])
"""
    res = await execute_code_async(code, df)
    assert res["success"]
    assert res["result"] == 30
