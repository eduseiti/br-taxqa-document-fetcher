#!/usr/bin/env python3
"""
Example demonstrating the new flexible input modes for BRTaxQADocumentFetcher.

This simulates what would typically be done in a Jupyter notebook.
"""

import tempfile
import os
from legal_document_processor import LegalDocumentProcessor, LawDocument
from legal_document_fetcher_main import BRTaxQADocumentFetcher


def example_1_using_pre_processed_laws():
    """Example 1: Using a pre-processed list of laws (most common notebook scenario)."""
    print("=== Example 1: Using Pre-processed Laws ===")

    # Simulate laws that were already processed in notebook cells
    laws_from_notebook = [
        LawDocument(
            filename="lei_8069.txt",
            number="8069",
            date="1990-07-13",
            year="1990",
            title="Lei nº 8.069 - Estatuto da Criança e do Adolescente",
            urn="urn:lex:br:federal:lei:1990-07-13;8069",
            original_content="Lei que dispõe sobre o ECA..."
        ),
        LawDocument(
            filename="lei_10406.txt",
            number="10406",
            date="2002-01-10",
            year="2002",
            title="Lei nº 10.406 - Código Civil",
            urn="urn:lex:br:federal:lei:2002-01-10;10406",
            original_content="Institui o Código Civil..."
        ),
    ]

    # Create fetcher with pre-processed laws - NO redundant processing!
    fetcher = BRTaxQADocumentFetcher(laws=laws_from_notebook)

    # Apply filters if needed
    recent_laws = fetcher.process_legal_documents(min_year=2000)

    print(f"Original laws: {len(laws_from_notebook)}")
    print(f"After filtering (≥2000): {len(recent_laws)}")
    for law in recent_laws:
        print(f"  - {law.title}")

    return fetcher


def example_2_using_processor_instance():
    """Example 2: Using an existing LegalDocumentProcessor instance."""
    print("\n=== Example 2: Using Processor Instance ===")

    # Create mock data file for demonstration
    mock_data = [
        {
            "filename": "Lei nº 12.527, de 18 de novembro de 2011.txt",
            "filedata": "Lei de acesso à informação..."
        },
        {
            "filename": "Lei nº 13.709, de 14 de agosto de 2018.txt",
            "filedata": "Lei Geral de Proteção de Dados..."
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        import json
        json.dump(mock_data, f)
        temp_file = f.name

    try:
        # Step 1: Process documents in notebook (already done)
        processor = LegalDocumentProcessor(temp_file)
        laws = processor.process_documents()

        print(f"Processed {len(laws)} laws in notebook")

        # Step 2: Create fetcher with existing processor - NO redundant processing!
        fetcher = BRTaxQADocumentFetcher(processor_instance=processor)

        # Apply filters using processor's capabilities
        recent_laws = fetcher.process_legal_documents(min_year=2010)

        print(f"After filtering (≥2010): {len(recent_laws)}")
        for law in recent_laws:
            print(f"  - Lei {law.number} ({law.year})")

        return fetcher

    finally:
        os.unlink(temp_file)


def example_3_using_urls_file():
    """Example 3: Using a file with pre-generated URLs."""
    print("\n=== Example 3: Using URLs File ===")

    # Create URLs file (could be generated from previous analysis)
    urls_content = """https://normas.leg.br/?urn=urn:lex:br:federal:lei:1988-10-05;7716
https://normas.leg.br/?urn=urn:lex:br:federal:lei:1996-12-20;9394
https://normas.leg.br/?urn=urn:lex:br:federal:lei:2006-03-07;11340
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(urls_content)
        urls_file = f.name

    try:
        # Create fetcher with URLs file
        fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)

        # Process URLs and apply filters
        laws = fetcher.process_legal_documents(min_year=1990)

        print(f"Loaded {len(laws)} laws from URLs file")
        print(f"After filtering (≥1990): {len(laws)}")
        for law in laws:
            print(f"  - Lei {law.number} ({law.year})")

        return fetcher

    finally:
        os.unlink(urls_file)


def example_4_backward_compatibility():
    """Example 4: Demonstrating backward compatibility."""
    print("\n=== Example 4: Backward Compatibility ===")

    # This is how the original code worked - still works!
    try:
        fetcher = BRTaxQADocumentFetcher(
            input_file='referred_legal_documents_QA_2024_v1.1.json',
            output_dir='./test_output'
        )
        print("✅ Original constructor pattern still works")
        return fetcher
    except FileNotFoundError:
        print("ℹ️  Original input file not found (expected in this example)")
        return None


def compare_performance():
    """Compare the efficiency of different input modes."""
    print("\n=== Performance Comparison ===")

    # Simulate large dataset processing time
    laws = [
        LawDocument(f"lei_{i}.txt", str(i), f"202{i%4}-01-01", f"202{i%4}",
                   f"Lei {i}", f"urn:lex:br:federal:lei:202{i%4}-01-01;{i}", f"content_{i}")
        for i in range(100)
    ]

    print(f"Testing with {len(laws)} laws...")

    # Method 1: Pre-processed laws (most efficient)
    import time
    start = time.time()
    fetcher1 = BRTaxQADocumentFetcher(laws=laws)
    result1 = fetcher1.process_legal_documents(min_year=2021)
    time1 = time.time() - start

    # Method 2: URLs file (efficient)
    urls_content = '\n'.join([f"https://normas.leg.br/?urn={law.urn}" for law in laws])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(urls_content)
        urls_file = f.name

    try:
        start = time.time()
        fetcher2 = BRTaxQADocumentFetcher(urls_file=urls_file)
        result2 = fetcher2.process_legal_documents(min_year=2021)
        time2 = time.time() - start

        print(f"Pre-processed laws: {time1:.4f}s → {len(result1)} results")
        print(f"URLs file:         {time2:.4f}s → {len(result2)} results")
        print(f"Speedup: {time2/time1:.1f}x faster with pre-processed laws")

    finally:
        os.unlink(urls_file)


def main():
    """Run all examples."""
    print("BRTaxQADocumentFetcher - New Flexible Input Modes")
    print("=" * 60)

    # Run examples
    example_1_using_pre_processed_laws()
    example_2_using_processor_instance()
    example_3_using_urls_file()
    example_4_backward_compatibility()
    compare_performance()

    print("\n" + "=" * 60)
    print("✅ All examples completed successfully!")
    print("\nKey Benefits:")
    print("- No redundant processing when laws are already available")
    print("- Flexible input modes for different workflows")
    print("- Full backward compatibility")
    print("- Efficient filtering and validation")
    print("- Perfect for Jupyter notebook workflows")


if __name__ == "__main__":
    main()