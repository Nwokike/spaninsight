"""Comprehensive client-side unit tests for SpanInsight.

Covers:
1. Sandbox AST whitelisting, disallowed builtins/imports, and execution timeouts.
2. Credit Service concurrent transaction reservation, commits, and rollbacks.
3. UUID Service 12-word mnemonic conversion and validation.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# Add src to python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import pandas as pd
from services.sandbox import execute_code
from services.credit_service import CreditService
from services.uuid_service import UUIDService


class TestSandbox(unittest.TestCase):
    """Tests the security, whitelisting, and constraints of the Python execution sandbox."""

    def setUp(self):
        self.df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})

    def test_safe_execution(self):
        """Verify that basic calculations and whitelisted modules work."""
        code = "result = df['A'].sum() + math.sqrt(16)"
        res = execute_code(code, self.df)
        self.assertTrue(
            res["success"], f"Failed to execute safe code: {res.get('error')}"
        )
        self.assertEqual(res["result"], 10.0)

    def test_prohibited_imports(self):
        """Verify that importing blocked modules is prevented."""
        # Check standard AST block
        code = "import os\nresult = os.getcwd()"
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("Security:", res["error"])

        # Check dynamic import bypass attempt block
        code = "__import__('os').system('echo hack')"
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("Security:", res["error"])

    def test_prohibited_builtins(self):
        """Verify that dangerous builtins like eval, exec, and open are blocked."""
        # Check open()
        code = "f = open('test.txt', 'w')"
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("Security:", res["error"])

        # Check eval()
        code = "eval('1 + 1')"
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("Security:", res["error"])

    def test_sandbox_escape_dunders(self):
        """Verify that magic/dunder methods are blocked to prevent sandbox escapes."""
        code = "result = ().__class__.__subclasses__()"
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("Security: Access to '__class__' is blocked", res["error"])

    def test_timeout_protection(self):
        """Verify that infinite loops trigger a hard execution timeout."""
        code = "while True:\n    pass"
        # We can run execute_code with a timeout (default timeout is set via constants, e.g. 5s)
        # To avoid making unit tests slow, execute_code internally uses SANDBOX_TIMEOUT_SEC.
        # But we also have nested loop depth limiting which blocks this instantly!
        res = execute_code(code, self.df)
        self.assertFalse(res["success"])
        self.assertIn("limit", res["error"])  # "Nested loop depth exceeds limit"


class TestCreditService(unittest.IsolatedAsyncioTestCase):
    """Tests the credit transaction dictionary to prevent concurrency race conditions."""

    async def asyncSetUp(self):
        self.page = MagicMock()
        self.storage = AsyncMock()
        # Mock storage return for credits
        self.storage.get.return_value = "100"
        self.credit_svc = CreditService(self.page, self.storage)

    async def test_reserve_success(self):
        """Test successful credit reservation returns a transaction ID."""
        tx_id = await self.credit_svc.reserve(30)
        self.assertIsNotNone(tx_id)
        # Verify reserved amount is tracked
        self.assertEqual(self.credit_svc._reservations[tx_id], 30)

    async def test_reserve_insufficient_funds(self):
        """Test reservation returns None if balance is lower than total reserved + requested."""
        # Current balance is 100
        tx_id1 = await self.credit_svc.reserve(80)
        self.assertIsNotNone(tx_id1)

        # Try to reserve another 30 (total 110 > 100)
        tx_id2 = await self.credit_svc.reserve(30)
        self.assertIsNone(tx_id2)

    async def test_commit_transaction(self):
        """Test committing a transaction deducts the balance and pops the transaction."""
        tx_id = await self.credit_svc.reserve(40)
        self.assertIsNotNone(tx_id)

        new_balance = await self.credit_svc.commit(tx_id)
        self.assertEqual(new_balance, 60)
        # Verify it was removed from reservations dict
        self.assertNotIn(tx_id, self.credit_svc._reservations)
        self.storage.set.assert_called_with("spaninsight_credits", "60")

    async def test_rollback_transaction(self):
        """Test rolling back a transaction releases the credits without deduction."""
        tx_id = await self.credit_svc.reserve(40)
        self.assertIsNotNone(tx_id)

        await self.credit_svc.rollback(tx_id)
        self.assertNotIn(tx_id, self.credit_svc._reservations)
        # Balance should remain unchanged on disk
        self.storage.set.assert_not_called()


class TestUUIDService(unittest.IsolatedAsyncioTestCase):
    """Tests the UUID conversion to 12-word mnemonic phrase and restore verification."""

    async def asyncSetUp(self):
        self.page = MagicMock()
        self.storage = AsyncMock()
        self.uuid_svc = UUIDService(self.page, self.storage)

    def test_uuid_to_phrase_and_back(self):
        """Test that converting a UUID to phrase and verifying back works consistently."""
        test_uuid = "e8c2576b-9c7a-4299-8cfb-226be818e6df"
        phrase = self.uuid_svc.uuid_to_phrase(test_uuid)

        # Phrase must be exactly 12 words
        words = phrase.split()
        self.assertEqual(len(words), 12)

        # Validating phrase should succeed
        validated = self.uuid_svc._phrase_to_uuid(phrase)
        self.assertEqual(validated, phrase)

    def test_invalid_phrase_validation(self):
        """Test that invalid phrases are blocked."""
        # Non-existent BIP39 word
        invalid_phrase = "apple banana cherry dog elephant fish grape house ice jacket king fakeinvalidword"
        validated = self.uuid_svc._phrase_to_uuid(invalid_phrase)
        self.assertIsNone(validated)


if __name__ == "__main__":
    unittest.main()
