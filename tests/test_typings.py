"""Tests using mypy."""

import os
import subprocess
import unittest
from unittest import TestCase


class MyPyTest(TestCase):
    """Class for testing modules with mypy."""

    def test_run_mypy_module(self) -> None:
        """Run mypy on all module sources."""
        result: int = subprocess.call(["uv", "run", "mypy", "."], env=os.environ)
        self.assertEqual(result, 0, "Expect 0 type errors when running mypy")


if __name__ == "__main__":
    unittest.main()
