"""
Run all tests with coverage report
"""
import pytest
import sys
import os


def main():
    """Run pytest with coverage"""
    print("=" * 70)
    print("RUNNING ALL TESTS - STAGE 7")
    print("=" * 70)

    # Run pytest with arguments
    args = [
        "-v",
        "--cov=app",
        "--cov-report=term",
        "--cov-report=html:coverage_report",
        "tests/"
    ]

    # Add any command line arguments
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])

    # Run tests
    result = pytest.main(args)

    print("\n" + "=" * 70)
    if result == 0:
        print("✅ ALL TESTS PASSED!")
        print("\nCoverage report generated in: coverage_report/")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)

    return result


if __name__ == "__main__":
    sys.exit(main())