#!/usr/bin/env python3
"""
Test runner for BRTaxQADocumentFetcher refactoring.

Runs all tests and provides a summary of results.
"""

import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_tests():
    """Run all test files and summarize results."""
    test_files = [
        'test_br_tax_qa_fetcher.py',
        'test_edge_cases.py'
    ]

    logger.info("Starting comprehensive test suite for BRTaxQADocumentFetcher refactoring")

    total_passed = 0
    total_failed = 0
    failed_tests = []

    for test_file in test_files:
        logger.info(f"Running tests in {test_file}...")

        try:
            # Run pytest with verbose output
            result = subprocess.run([
                sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short'
            ], capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info(f"✅ {test_file}: All tests passed")
                # Count passed tests (rough estimate from output)
                passed_count = result.stdout.count(' PASSED')
                total_passed += passed_count
            else:
                logger.error(f"❌ {test_file}: Some tests failed")
                failed_tests.append(test_file)
                # Count failed tests
                failed_count = result.stdout.count(' FAILED')
                passed_count = result.stdout.count(' PASSED')
                total_passed += passed_count
                total_failed += failed_count

                # Print failure details
                print(f"\nFailure details for {test_file}:")
                print(result.stdout)
                if result.stderr:
                    print("STDERR:")
                    print(result.stderr)

        except subprocess.TimeoutExpired:
            logger.error(f"❌ {test_file}: Test execution timed out")
            failed_tests.append(test_file)
        except Exception as e:
            logger.error(f"❌ {test_file}: Error running tests: {e}")
            failed_tests.append(test_file)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total tests passed: {total_passed}")
    print(f"Total tests failed: {total_failed}")

    if failed_tests:
        print(f"Failed test files: {', '.join(failed_tests)}")
        return 1
    else:
        print("🎉 All tests passed successfully!")
        return 0


def run_simple_validation():
    """Run a simple validation to check basic functionality."""
    logger.info("Running simple validation tests...")

    try:
        # Import and test basic functionality
        from legal_document_processor import LegalDocumentProcessor, LawDocument
        from legal_document_fetcher_main import BRTaxQADocumentFetcher

        # Test 1: Basic initialization
        logger.info("Test 1: Basic initialization")
        fetcher = BRTaxQADocumentFetcher()
        assert fetcher.output_dir == Path('./fetched_documents')
        logger.info("✅ Basic initialization works")

        # Test 2: Laws list initialization
        logger.info("Test 2: Laws list initialization")
        test_laws = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content")
        ]
        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        assert fetcher.pre_processed_laws == test_laws
        logger.info("✅ Laws list initialization works")

        # Test 3: Input validation
        logger.info("Test 3: Input validation")
        try:
            BRTaxQADocumentFetcher(laws=test_laws, input_file="test.json")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "exactly one input method" in str(e)
            logger.info("✅ Input validation works")

        # Test 4: Manual filtering
        logger.info("Test 4: Manual filtering")
        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        filtered = fetcher._apply_manual_filters(test_laws, require_date=True)
        assert len(filtered) == 1
        logger.info("✅ Manual filtering works")

        logger.info("🎉 Simple validation completed successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Simple validation failed: {e}")
        return False


if __name__ == "__main__":
    from pathlib import Path

    print("BRTaxQADocumentFetcher Refactoring Test Suite")
    print("=" * 50)

    # First run simple validation
    if not run_simple_validation():
        print("Simple validation failed. Skipping full test suite.")
        sys.exit(1)

    print("\n" + "=" * 50)

    # Run full test suite
    exit_code = run_tests()
    sys.exit(exit_code)