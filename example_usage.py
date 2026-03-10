#!/usr/bin/env python3
"""
Example usage of the BR-TaxQA Legal Document Fetcher

This script demonstrates how to use the document processor and fetcher
with various configuration options.
"""

import logging
from legal_document_processor import LegalDocumentProcessor

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("BR-TaxQA Legal Document Fetcher - Example Usage")
    print("=" * 55)

    # Example 1: Basic document processing
    print("\\n1. Basic Document Processing")
    print("-" * 30)

    processor = LegalDocumentProcessor('referred_legal_documents_QA_2024_v1.1.json')
    laws = processor.process_documents()

    # Show statistics
    stats = processor.get_statistics()
    print(f"Total laws found: {stats['total_laws']}")
    print(f"Laws with dates: {stats['laws_with_dates']} ({stats['date_coverage_percent']}%)")
    print(f"Year range: {stats['year_range']}")

    # Example 2: Filter recent laws
    print("\\n2. Filter Recent Laws (2010+)")
    print("-" * 30)

    recent_laws = processor.filter_laws_by_criteria(
        min_year=2010,
        require_date=True
    )
    print(f"Recent laws (2010+): {len(recent_laws)}")

    # Show sample recent laws
    print("\\nSample recent laws:")
    for i, law in enumerate(recent_laws[:5]):
        print(f"  {i+1}. Lei {law.number} ({law.date}) - {law.title[:50]}...")

    # Example 3: Show URN construction
    print("\\n3. URN Construction Examples")
    print("-" * 30)

    for i, law in enumerate(laws[:3]):
        print(f"  {i+1}. {law.filename}")
        print(f"     URN: {law.urn}")
        print(f"     URL: {processor.construct_normas_url(law.urn)}")
        print()

    # Example 4: Export data
    print("4. Export Examples")
    print("-" * 30)

    # Export all laws with dates
    laws_with_dates = processor.filter_laws_by_criteria(require_date=True)
    processor.export_to_json(laws_with_dates, 'example_laws.json')
    processor.export_urls_list(laws_with_dates, 'example_urls.txt')

    print(f"Exported {len(laws_with_dates)} laws with dates to:")
    print(f"  - example_laws.json")
    print(f"  - example_urls.txt")

    # Example 5: Show law categories (by decade)
    print("\\n5. Laws by Decade")
    print("-" * 30)

    decade_counts = {}
    for law in laws_with_dates:
        if law.year:
            decade = (int(law.year) // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + 1

    for decade in sorted(decade_counts.keys()):
        count = decade_counts[decade]
        print(f"  {decade}s: {count} laws")

    print("\\n" + "=" * 55)
    print("Example completed successfully!")
    print("\\nNext steps:")
    print("1. Review the exported files: example_laws.json and example_urls.txt")
    print("2. Run the full fetcher: python legal_document_fetcher_main.py")
    print("3. Check the comprehensive documentation in README.md")


if __name__ == "__main__":
    main()