#!/usr/bin/env python3
"""
Simple test runner for hivemind-mcp.
Run all tests: python run_tests.py
Run specific test: python run_tests.py test_models
"""

import sys
import subprocess

def main():
    """Run pytest with nice formatting."""

    # Default to running all tests
    test_path = "tests/"

    # If argument provided, run specific test
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if not test_name.startswith("test_"):
            test_name = f"test_{test_name}"
        test_path = f"tests/{test_name}.py"

    # Run pytest
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",  # Verbose
        "--tb=short",  # Short traceback
        "--color=yes"  # Colored output
    ]

    print(f"Running tests: {test_path}")
    print("-" * 60)

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
