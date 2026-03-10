#!/usr/bin/env python3
"""
Validation script for the BR-TaxQA legal document fetching setup.

This script validates the environment, dependencies, and URN construction
before running the main document fetching process.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Test imports
def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        import requests
        print("  ✓ requests")
    except ImportError:
        print("  ✗ requests - Please install with: pip install requests")
        return False

    try:
        import selenium
        print("  ✓ selenium")
    except ImportError:
        print("  ✗ selenium - Please install with: pip install selenium")
        return False

    try:
        from bs4 import BeautifulSoup
        print("  ✓ beautifulsoup4")
    except ImportError:
        print("  ✗ beautifulsoup4 - Please install with: pip install beautifulsoup4")
        return False

    try:
        from docx import Document
        print("  ✓ python-docx")
    except ImportError:
        print("  ✗ python-docx - Please install with: pip install python-docx")
        return False

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("  ✓ webdriver-manager")
    except ImportError:
        print("  ✗ webdriver-manager - Please install with: pip install webdriver-manager")
        return False

    try:
        import tqdm
        print("  ✓ tqdm")
    except ImportError:
        print("  ✗ tqdm - Please install with: pip install tqdm")
        return False

    return True


def test_br_legal_parser():
    """Test that br_legal_parser is available and functional."""
    print("\\nTesting br_legal_parser integration...")

    # Check if directory exists
    br_parser_path = Path("br_legal_parser")
    if not br_parser_path.exists():
        print("  ✗ br_legal_parser directory not found")
        return False

    print(f"  ✓ Found br_legal_parser directory: {br_parser_path.absolute()}")

    # Check if main module exists
    main_module = br_parser_path / "legal_document_fetcher.py"
    if not main_module.exists():
        print("  ✗ legal_document_fetcher.py not found in br_legal_parser")
        return False

    print("  ✓ Found legal_document_fetcher.py")

    # Try to import the module
    try:
        sys.path.append(str(br_parser_path))
        from legal_document_fetcher import LegalDocumentFetcher, FetcherConfig
        print("  ✓ Successfully imported LegalDocumentFetcher")
    except ImportError as e:
        print(f"  ✗ Failed to import LegalDocumentFetcher: {e}")
        return False

    return True


def test_input_file():
    """Test that the input JSON file exists and is valid."""
    print("\\nTesting input file...")

    input_file = "referred_legal_documents_QA_2024_v1.1.json"

    if not Path(input_file).exists():
        print(f"  ✗ Input file not found: {input_file}")
        return False

    print(f"  ✓ Found input file: {input_file}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("  ✗ Input file should contain a list of documents")
            return False

        print(f"  ✓ Valid JSON with {len(data)} documents")

        # Check first document structure
        if len(data) > 0:
            first_doc = data[0]
            if 'filename' in first_doc and 'filedata' in first_doc:
                print("  ✓ Document structure is correct (filename, filedata)")
            else:
                print("  ✗ Document structure invalid - expected 'filename' and 'filedata' fields")
                return False

    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON format: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error reading file: {e}")
        return False

    return True


def test_document_processing():
    """Test the document processing pipeline."""
    print("\\nTesting document processing...")

    try:
        from legal_document_processor import LegalDocumentProcessor
        print("  ✓ Imported LegalDocumentProcessor")
    except ImportError as e:
        print(f"  ✗ Failed to import LegalDocumentProcessor: {e}")
        return False

    try:
        # Initialize processor
        processor = LegalDocumentProcessor('referred_legal_documents_QA_2024_v1.1.json')

        # Process a small sample
        documents = processor.load_documents()
        print(f"  ✓ Loaded {len(documents)} documents")

        # Test law filtering
        sample_docs = documents[:10]  # Just test first 10
        law_count = sum(1 for doc in sample_docs if processor.is_law_document(doc['filename']))
        print(f"  ✓ Found {law_count} law documents in sample of 10")

        # Test URN construction for one law
        for doc in sample_docs:
            if processor.is_law_document(doc['filename']):
                law_info = processor.extract_law_info(doc['filename'], doc['filedata'])
                if law_info:
                    number, date, year = law_info
                    urn = processor.construct_urn(number, date)
                    url = processor.construct_normas_url(urn)
                    print(f"  ✓ Sample URN: {urn}")
                    print(f"  ✓ Sample URL: {url}")
                    break

    except Exception as e:
        print(f"  ✗ Document processing test failed: {e}")
        return False

    return True


def test_urn_samples():
    """Test URN construction with known good examples."""
    print("\\nTesting URN construction with samples...")

    test_cases = [
        {
            'filename': 'Lei n° 10.406, de 10 de janeiro de 2002 - Código Civil.txt',
            'expected_number': '10406',
            'expected_date': '2002-01-10'
        },
        {
            'filename': 'Lei n° 8.112, de 11 de dezembro de 1990.txt',
            'expected_number': '8112',
            'expected_date': '1990-12-11'
        }
    ]

    try:
        from legal_document_processor import LegalDocumentProcessor
        processor = LegalDocumentProcessor('referred_legal_documents_QA_2024_v1.1.json')

        for i, test_case in enumerate(test_cases):
            filename = test_case['filename']
            law_info = processor.extract_law_info(filename, "")

            if not law_info:
                print(f"  ✗ Test case {i+1}: Could not extract law info from '{filename}'")
                continue

            number, date, year = law_info

            if number != test_case['expected_number']:
                print(f"  ✗ Test case {i+1}: Expected number {test_case['expected_number']}, got {number}")
                continue

            if date != test_case['expected_date']:
                print(f"  ✗ Test case {i+1}: Expected date {test_case['expected_date']}, got {date}")
                continue

            urn = processor.construct_urn(number, date)
            expected_urn = f"urn:lex:br:federal:lei:{date};{number}"

            if urn != expected_urn:
                print(f"  ✗ Test case {i+1}: Expected URN {expected_urn}, got {urn}")
                continue

            print(f"  ✓ Test case {i+1}: {filename} -> {urn}")

    except Exception as e:
        print(f"  ✗ URN testing failed: {e}")
        return False

    return True


def check_selenium_setup():
    """Check if Selenium can start a browser."""
    print("\\nTesting Selenium setup...")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        print("  ✓ Selenium imports successful")

        # Try to get ChromeDriver
        try:
            driver_path = ChromeDriverManager().install()
            print(f"  ✓ ChromeDriver available at: {driver_path}")
        except Exception as e:
            print(f"  ✗ ChromeDriver setup failed: {e}")
            return False

        # Try to start browser (headless)
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')

            driver = webdriver.Chrome(options=chrome_options)
            driver.get("https://www.google.com")
            title = driver.title
            driver.quit()

            print(f"  ✓ Selenium browser test successful (page title: '{title[:30]}...')")

        except Exception as e:
            print(f"  ✗ Selenium browser test failed: {e}")
            return False

    except ImportError as e:
        print(f"  ✗ Selenium import failed: {e}")
        return False

    return True


def main():
    """Run all validation tests."""
    print("BR-TaxQA Legal Document Fetcher - Setup Validation")
    print("=" * 55)

    tests = [
        ("Import Dependencies", test_imports),
        ("BR Legal Parser", test_br_legal_parser),
        ("Input File", test_input_file),
        ("Document Processing", test_document_processing),
        ("URN Construction", test_urn_samples),
        ("Selenium Setup", check_selenium_setup)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test '{test_name}' failed with exception: {e}")
            failed += 1

    print("\\n" + "=" * 55)
    print(f"Validation Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\\n🎉 All validation tests passed! The system is ready to use.")
        print("\\nNext steps:")
        print("  1. Run: python legal_document_fetcher_main.py")
        print("  2. Check the output in ./br_taxqa_documents/")
        return 0
    else:
        print("\\n❌ Some validation tests failed. Please fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)