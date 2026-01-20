#!/usr/bin/env python3
"""
Test Runner Script for TradeSense AI

Provides convenient commands to run different types of tests with various options.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"❌ {description} failed with exit code {result.returncode}")
            return False
        else:
            print(f"✅ {description} completed successfully")
            return True

    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False


def main():
    """Main test runner function."""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py <command>")
        print("\nAvailable commands:")
        print("  unit           - Run unit tests only")
        print("  integration    - Run integration tests only")
        print("  all            - Run all tests")
        print("  coverage       - Run tests with coverage report")
        print("  fast           - Run fast tests only (skip slow tests)")
        print("  api            - Run API endpoint tests only")
        print("  performance    - Run performance tests")
        print("  security       - Run security tests")
        print("  lint           - Run linting checks")
        print("  type-check     - Run type checking")
        print("  ci             - Run CI pipeline (lint + tests + coverage)")
        return 1

    command = sys.argv[1]

    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent)

    if command == 'unit':
        success = run_command([
            'pytest', 'tests/unit/',
            '-v', '--tb=short', '-x'
        ], "Unit Tests")

    elif command == 'integration':
        success = run_command([
            'pytest', 'tests/integration/',
            '-v', '--tb=short', '-x'
        ], "Integration Tests")

    elif command == 'all':
        success = run_command([
            'pytest', 'tests/',
            '-v', '--tb=short'
        ], "All Tests")

    elif command == 'coverage':
        success = run_command([
            'pytest', 'tests/',
            '--cov=app',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-fail-under=80',
            '-v', '--tb=short'
        ], "Tests with Coverage")

    elif command == 'fast':
        success = run_command([
            'pytest', 'tests/',
            '-m', 'not slow',
            '-v', '--tb=short'
        ], "Fast Tests Only")

    elif command == 'api':
        success = run_command([
            'pytest', 'tests/',
            '-m', 'api',
            '-v', '--tb=short'
        ], "API Tests")

    elif command == 'performance':
        success = run_command([
            'pytest', 'tests/',
            '-m', 'performance',
            '-v', '--tb=short', '-s'
        ], "Performance Tests")

    elif command == 'security':
        success = run_command([
            'pytest', 'tests/',
            '-m', 'security',
            '-v', '--tb=short'
        ], "Security Tests")

    elif command == 'lint':
        success = run_command([
            'flake8', 'app/', 'tests/',
            '--max-line-length=120',
            '--ignore=E203,W503'
        ], "Linting (flake8)")

        if success:
            success = run_command([
                'black', '--check', '--diff', 'app/', 'tests/'
            ], "Code Formatting (black)")

    elif command == 'type-check':
        success = run_command([
            'mypy', 'app/',
            '--ignore-missing-imports',
            '--strict-optional',
            '--warn-return-any',
            '--warn-unused-ignores'
        ], "Type Checking (mypy)")

    elif command == 'ci':
        print("🚀 Running CI Pipeline...")

        # Step 1: Linting
        if not run_command([
            'flake8', 'app/', 'tests/',
            '--max-line-length=120',
            '--ignore=E203,W503'
        ], "Linting"):
            return 1

        # Step 2: Type checking
        if not run_command([
            'mypy', 'app/',
            '--ignore-missing-imports'
        ], "Type Checking"):
            return 1

        # Step 3: Unit tests
        if not run_command([
            'pytest', 'tests/unit/',
            '-v', '--tb=short', '-x'
        ], "Unit Tests"):
            return 1

        # Step 4: Integration tests
        if not run_command([
            'pytest', 'tests/integration/',
            '-v', '--tb=short', '-x'
        ], "Integration Tests"):
            return 1

        # Step 5: Coverage report
        success = run_command([
            'pytest', 'tests/',
            '--cov=app',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-fail-under=80'
        ], "Coverage Report")

        if success:
            print("\n🎉 CI Pipeline completed successfully!")
            print("📊 Coverage report available at: htmlcov/index.html")

    else:
        print(f"Unknown command: {command}")
        print("Run 'python run_tests.py' without arguments to see available commands.")
        return 1

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())