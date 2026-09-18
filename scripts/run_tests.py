"""One-command automated test suite runner for GridWise."""

import os
import sys
import unittest
from pathlib import Path

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure LLM_PROVIDER is fake for deterministic tests
os.environ["LLM_PROVIDER"] = "fake"


def run_suite():
    print("\n========================================================")
    print("   Running Complete GridWise Hackathon Automated Tests")
    print("========================================================\n")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT_DIR / "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n========================================================")
    print(f" Tests run: {result.testsRun}")
    print(f" Errors: {len(result.errors)}")
    print(f" Failures: {len(result.failures)}")
    success = result.wasSuccessful()
    print(f" Final Status: {'PASSED' if success else 'FAILED'}")
    print("========================================================\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_suite())
