#!/usr/bin/env python3
"""
Legal Document Processor for BR-TaxQA Dataset

This module processes the referred legal documents from the BR-TaxQA dataset,
filters law documents, and constructs proper LexML URNs for fetching from normas.leg.br.
"""

import json
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LawDocument:
    """Represents a law document with extracted metadata."""
    filename: str
    number: str
    date: Optional[str]
    year: Optional[str]
    title: str
    urn: str
    original_content: str


class LegalDocumentProcessor:
    """Processes legal documents and constructs URNs for fetching."""

    def __init__(self, input_file: str):
        """
        Initialize the processor.

        Args:
            input_file: Path to the referred_legal_documents JSON file
        """
        self.input_file = Path(input_file)
        self.logger = logging.getLogger(__name__)
        self.laws: List[LawDocument] = []

        # Portuguese month name mapping
        self.months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }

    def load_documents(self) -> List[Dict]:
        """Load documents from the JSON file."""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                documents = json.load(f)
            self.logger.info(f"Loaded {len(documents)} documents from {self.input_file}")
            return documents
        except Exception as e:
            self.logger.error(f"Failed to load documents: {e}")
            raise

    def is_law_document(self, filename: str) -> bool:
        """
        Determine if a document is a law based on its filename.

        Args:
            filename: The document filename

        Returns:
            True if the document is a law
        """
        filename_lower = filename.lower()

        # Must contain 'lei' but exclude other document types
        if 'lei' not in filename_lower:
            return False

        # Exclude other document types that might contain 'lei'
        exclusions = ['decreto', 'portaria', 'medida', 'instrução', 'resolução']
        if any(exclusion in filename_lower for exclusion in exclusions):
            return False

        return True

    def extract_law_info(self, filename: str, content: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """
        Extract law number and date from filename and content.

        Args:
            filename: The document filename
            content: The document content

        Returns:
            Tuple of (law_number, date, year) or None if extraction fails
        """
        # Pattern 1: Lei n° 10.406, de 10 de janeiro de 2002
        pattern1 = r'Lei n[°º]\s*([0-9.]+),\s*de\s*(\d{1,2})\s*de\s*(\w+)\s*de\s*(\d{4})'
        match1 = re.search(pattern1, filename, re.IGNORECASE)

        if match1:
            number = match1.group(1).replace('.', '')
            day = match1.group(2).zfill(2)
            month_name = match1.group(3).lower()
            year = match1.group(4)

            month = self.months.get(month_name, '01')
            date = f'{year}-{month}-{day}'

            return number, date, year

        # Pattern 2: Lei nº 1.301 (try to find date in content)
        pattern2 = r'Lei n[°º]\s*([0-9.]+)'
        match2 = re.search(pattern2, filename, re.IGNORECASE)

        if match2:
            number = match2.group(1).replace('.', '')

            # Try to extract date from content (first 1000 chars)
            content_date_pattern = r'(\d{1,2})\s*de\s*(\w+)\s*de\s*(\d{4})'
            content_match = re.search(content_date_pattern, content[:1000], re.IGNORECASE)

            if content_match:
                day = content_match.group(1).zfill(2)
                month_name = content_match.group(2).lower()
                year = content_match.group(3)

                month = self.months.get(month_name, '01')
                date = f'{year}-{month}-{day}'

                return number, date, year
            else:
                # No date found, return just the number
                return number, None, None

        return None

    def construct_urn(self, number: str, date: Optional[str]) -> str:
        """
        Construct a LexML URN for the law.

        Args:
            number: Law number (without dots)
            date: Law date in YYYY-MM-DD format (optional)

        Returns:
            Complete URN string for normas.leg.br
        """
        if date:
            # Standard format: urn:lex:br:federal:lei:YYYY-MM-DD;NUMBER
            urn = f"urn:lex:br:federal:lei:{date};{number}"
        else:
            # Fallback: try with a generic date (laws without clear dates)
            # We'll use 1900-01-01 as a placeholder for manual review
            urn = f"urn:lex:br:federal:lei:1900-01-01;{number}"
            self.logger.warning(f"No date found for Lei {number}, using placeholder date")

        return urn

    def construct_normas_url(self, urn: str) -> str:
        """
        Construct the complete normas.leg.br URL from a URN.

        Args:
            urn: LexML URN

        Returns:
            Complete URL for normas.leg.br
        """
        return f"https://normas.leg.br/?urn={urn}"

    def extract_title(self, filename: str, content: str) -> str:
        """
        Extract a clean title for the law.

        Args:
            filename: Document filename
            content: Document content

        Returns:
            Extracted title
        """
        # Remove file extension
        title = filename.replace('.txt', '')

        # Try to find a better title in the content (first 200 chars)
        title_patterns = [
            r'Lei n[°º]\s*[0-9.]+[^\\n]*',
            r'(Lei [^\\n]{20,100})',
        ]

        for pattern in title_patterns:
            match = re.search(pattern, content[:200], re.IGNORECASE)
            if match:
                potential_title = match.group().strip()
                if len(potential_title) > len(title) and len(potential_title) < 200:
                    title = potential_title
                break

        return title.strip()

    def process_documents(self) -> List[LawDocument]:
        """
        Process all documents and extract law information.

        Returns:
            List of processed law documents
        """
        documents = self.load_documents()
        self.laws = []

        processed_count = 0
        law_count = 0

        for doc in documents:
            processed_count += 1
            filename = doc['filename']
            content = doc['filedata']

            if not self.is_law_document(filename):
                continue

            law_info = self.extract_law_info(filename, content)
            if not law_info:
                self.logger.warning(f"Could not extract law info from: {filename}")
                continue

            number, date, year = law_info
            urn = self.construct_urn(number, date)
            title = self.extract_title(filename, content)

            law_doc = LawDocument(
                filename=filename,
                number=number,
                date=date,
                year=year,
                title=title,
                urn=urn,
                original_content=content
            )

            self.laws.append(law_doc)
            law_count += 1

        self.logger.info(f"Processed {processed_count} documents, extracted {law_count} laws")
        return self.laws

    def filter_laws_by_criteria(self,
                               min_year: Optional[int] = None,
                               max_year: Optional[int] = None,
                               require_date: bool = False) -> List[LawDocument]:
        """
        Filter laws by various criteria.

        Args:
            min_year: Minimum year (inclusive)
            max_year: Maximum year (inclusive)
            require_date: If True, only return laws with valid dates

        Returns:
            Filtered list of law documents
        """
        filtered_laws = self.laws

        if require_date:
            filtered_laws = [law for law in filtered_laws if law.date]

        if min_year:
            filtered_laws = [law for law in filtered_laws
                           if law.year and int(law.year) >= min_year]

        if max_year:
            filtered_laws = [law for law in filtered_laws
                           if law.year and int(law.year) <= max_year]

        self.logger.info(f"Filtered to {len(filtered_laws)} laws from {len(self.laws)} total")
        return filtered_laws

    def get_urns_list(self, laws: Optional[List[LawDocument]] = None) -> List[str]:
        """
        Get list of URNs for the laws.

        Args:
            laws: Optional list of laws to process (defaults to all processed laws)

        Returns:
            List of URN strings
        """
        if laws is None:
            laws = self.laws

        return [law.urn for law in laws]

    def get_urls_list(self, laws: Optional[List[LawDocument]] = None) -> List[str]:
        """
        Get list of normas.leg.br URLs for the laws.

        Args:
            laws: Optional list of laws to process (defaults to all processed laws)

        Returns:
            List of complete URLs
        """
        if laws is None:
            laws = self.laws

        return [self.construct_normas_url(law.urn) for law in laws]

    def export_to_json(self, laws: List[LawDocument], output_file: str):
        """
        Export processed laws to JSON file.

        Args:
            laws: List of law documents to export
            output_file: Output file path
        """
        output_data = []
        for law in laws:
            output_data.append({
                'filename': law.filename,
                'number': law.number,
                'date': law.date,
                'year': law.year,
                'title': law.title,
                'urn': law.urn,
                'url': self.construct_normas_url(law.urn)
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Exported {len(laws)} laws to {output_file}")

    def export_urls_list(self, laws: List[LawDocument], output_file: str):
        """
        Export URLs to a text file (one per line).

        Args:
            laws: List of law documents to export
            output_file: Output file path
        """
        urls = self.get_urls_list(laws)

        with open(output_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\\n')

        self.logger.info(f"Exported {len(urls)} URLs to {output_file}")

    def get_statistics(self) -> Dict:
        """
        Get processing statistics.

        Returns:
            Dictionary with various statistics
        """
        if not self.laws:
            return {}

        total_laws = len(self.laws)
        with_dates = sum(1 for law in self.laws if law.date)
        without_dates = total_laws - with_dates

        # Year distribution
        years = [int(law.year) for law in self.laws if law.year]
        min_year = min(years) if years else None
        max_year = max(years) if years else None

        return {
            'total_laws': total_laws,
            'laws_with_dates': with_dates,
            'laws_without_dates': without_dates,
            'date_coverage_percent': round(with_dates / total_laws * 100, 2) if total_laws > 0 else 0,
            'year_range': f'{min_year}-{max_year}' if min_year and max_year else 'N/A',
            'earliest_year': min_year,
            'latest_year': max_year
        }


def main():
    """Main function for testing the processor."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Initialize processor
    processor = LegalDocumentProcessor('referred_legal_documents_QA_2024_v1.1.json')

    # Process documents
    laws = processor.process_documents()

    # Get statistics
    stats = processor.get_statistics()
    print("\\nProcessing Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Filter laws with valid dates (for better URN construction)
    laws_with_dates = processor.filter_laws_by_criteria(require_date=True)

    # Show sample results
    print(f"\\nFirst 10 laws with dates:")
    for i, law in enumerate(laws_with_dates[:10]):
        print(f"  {i+1:2}. Lei {law.number.rjust(6)} ({law.date}) - {law.title[:60]}...")

    # Export results
    processor.export_to_json(laws_with_dates, 'processed_laws_with_dates.json')
    processor.export_urls_list(laws_with_dates, 'law_urls_with_dates.txt')

    print(f"\\nExported {len(laws_with_dates)} laws with dates to files.")


if __name__ == "__main__":
    main()