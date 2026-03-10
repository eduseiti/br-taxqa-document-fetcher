#!/usr/bin/env python3
"""
Legal Document Fetcher for BR-TaxQA Dataset

This module combines the legal document processor with the br_legal_parser
to fetch Brazilian law documents from normas.leg.br and save them as DOCX files.
"""

import sys
import os
import logging
import json
import time
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import asdict

# Add br_legal_parser to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'br_legal_parser'))

try:
    from legal_document_fetcher import LegalDocumentFetcher, FetcherConfig
except ImportError:
    print("Error: Could not import legal_document_fetcher from br_legal_parser")
    print("Please ensure the br_legal_parser repository is cloned in the current directory")
    sys.exit(1)

from legal_document_processor import LegalDocumentProcessor, LawDocument


class BRTaxQADocumentFetcher:
    """Main class that orchestrates the complete document fetching process."""

    def __init__(self,
                 input_file: str = 'referred_legal_documents_QA_2024_v1.1.json',
                 output_dir: str = './fetched_documents',
                 batch_size: int = 10,
                 delay_between_batches: float = 5.0):
        """
        Initialize the fetcher.

        Args:
            input_file: Path to the referred legal documents JSON file
            output_dir: Directory to save fetched DOCX files
            batch_size: Number of documents to process before taking a break
            delay_between_batches: Delay in seconds between batches (for rate limiting)
        """
        self.input_file = input_file
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches

        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.processor = LegalDocumentProcessor(input_file)
        self.br_legal_fetcher = None
        self.laws: List[LawDocument] = []
        self.fetch_results = []

    def setup_br_legal_fetcher(self,
                              request_timeout: int = 30,
                              retry_attempts: int = 3,
                              delay_between_requests: float = 2.0) -> None:
        """
        Setup the br_legal_parser fetcher with appropriate configuration.

        Args:
            request_timeout: HTTP timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            delay_between_requests: Delay between individual requests
        """
        # Create output directories
        documents_dir = self.output_dir / 'documents'
        logs_dir = self.output_dir / 'logs'
        metadata_dir = self.output_dir / 'metadata'

        for dir_path in [documents_dir, logs_dir, metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Configure the br_legal_parser fetcher
        config = FetcherConfig(
            output_dir=str(documents_dir),
            request_timeout=request_timeout,
            retry_attempts=retry_attempts,
            delay_between_requests=delay_between_requests,
            create_output_dir=True,
            use_selenium=True,
            selenium_wait_time=20
        )

        self.br_legal_fetcher = LegalDocumentFetcher(config)
        self.logger.info(f"Initialized br_legal_parser fetcher with output dir: {documents_dir}")

    def process_legal_documents(self,
                               require_date: bool = True,
                               min_year: Optional[int] = None,
                               max_year: Optional[int] = None) -> List[LawDocument]:
        """
        Process the input JSON and extract law documents.

        Args:
            require_date: Only include laws with valid dates
            min_year: Minimum year filter (optional)
            max_year: Maximum year filter (optional)

        Returns:
            List of processed law documents
        """
        self.logger.info("Processing legal documents from input file...")

        # Process all documents
        self.laws = self.processor.process_documents()

        # Apply filters
        filtered_laws = self.processor.filter_laws_by_criteria(
            min_year=min_year,
            max_year=max_year,
            require_date=require_date
        )

        # Log statistics
        stats = self.processor.get_statistics()
        self.logger.info(f"Processing statistics: {stats}")

        return filtered_laws

    def validate_urns(self, laws: List[LawDocument]) -> Dict:
        """
        Validate URN construction and detect potential issues.

        Args:
            laws: List of law documents to validate

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'total_laws': len(laws),
            'valid_urns': 0,
            'invalid_urns': 0,
            'placeholder_dates': 0,
            'validation_errors': []
        }

        for law in laws:
            try:
                # Basic URN format validation
                if law.urn.startswith('urn:lex:br:federal:lei:'):
                    validation_results['valid_urns'] += 1

                    # Check for placeholder dates
                    if '1900-01-01' in law.urn:
                        validation_results['placeholder_dates'] += 1
                        validation_results['validation_errors'].append(
                            f"Lei {law.number}: Using placeholder date (no date found)"
                        )
                else:
                    validation_results['invalid_urns'] += 1
                    validation_results['validation_errors'].append(
                        f"Lei {law.number}: Invalid URN format: {law.urn}"
                    )
            except Exception as e:
                validation_results['invalid_urns'] += 1
                validation_results['validation_errors'].append(
                    f"Lei {law.number}: Validation error: {str(e)}"
                )

        # Calculate success rate
        if validation_results['total_laws'] > 0:
            validation_results['success_rate'] = round(
                validation_results['valid_urns'] / validation_results['total_laws'] * 100, 2
            )
        else:
            validation_results['success_rate'] = 0

        self.logger.info(f"URN validation: {validation_results['valid_urns']}/{validation_results['total_laws']} "
                        f"valid ({validation_results['success_rate']}%)")

        return validation_results

    def fetch_documents_in_batches(self, laws: List[LawDocument]) -> List:
        """
        Fetch documents using the br_legal_parser in batches.

        Args:
            laws: List of law documents to fetch

        Returns:
            List of fetch results
        """
        if not self.br_legal_fetcher:
            raise ValueError("br_legal_fetcher not initialized. Call setup_br_legal_fetcher() first.")

        self.logger.info(f"Starting batch fetching of {len(laws)} documents...")

        all_results = []
        total_batches = (len(laws) + self.batch_size - 1) // self.batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(laws))
            batch_laws = laws[start_idx:end_idx]

            self.logger.info(f"Processing batch {batch_num + 1}/{total_batches} "
                           f"({len(batch_laws)} documents)...")

            # Convert laws to URLs for br_legal_parser
            batch_urls = [self.processor.construct_normas_url(law.urn) for law in batch_laws]

            try:
                # Process the batch using br_legal_parser
                batch_results = self.br_legal_fetcher.process_url_list(
                    batch_urls,
                    show_progress=True
                )
                all_results.extend(batch_results)

                # Log batch statistics
                successful = sum(1 for result in batch_results if result.success)
                self.logger.info(f"Batch {batch_num + 1} completed: {successful}/{len(batch_results)} successful")

            except Exception as e:
                self.logger.error(f"Batch {batch_num + 1} failed: {str(e)}")
                # Continue with next batch

            # Rate limiting: delay between batches
            if batch_num < total_batches - 1:  # Don't delay after the last batch
                self.logger.info(f"Waiting {self.delay_between_batches} seconds before next batch...")
                time.sleep(self.delay_between_batches)

        self.fetch_results = all_results
        return all_results

    def generate_reports(self, laws: List[LawDocument], fetch_results: List) -> Dict:
        """
        Generate comprehensive reports on the fetching process.

        Args:
            laws: Original list of law documents
            fetch_results: Results from br_legal_parser

        Returns:
            Dictionary containing various report data
        """
        report = {
            'summary': {
                'total_laws_processed': len(laws),
                'total_fetch_attempts': len(fetch_results),
                'successful_fetches': sum(1 for result in fetch_results if result.success),
                'failed_fetches': sum(1 for result in fetch_results if not result.success),
                'success_rate': 0
            },
            'timing': {
                'total_fetch_time': sum(result.fetch_time for result in fetch_results),
                'average_fetch_time': 0
            },
            'failures': [],
            'year_statistics': {},
            'file_statistics': {}
        }

        # Calculate success rate
        if len(fetch_results) > 0:
            report['summary']['success_rate'] = round(
                report['summary']['successful_fetches'] / len(fetch_results) * 100, 2
            )

        # Calculate average fetch time
        if len(fetch_results) > 0:
            report['timing']['average_fetch_time'] = round(
                report['timing']['total_fetch_time'] / len(fetch_results), 2
            )

        # Collect failure details
        for result in fetch_results:
            if not result.success:
                report['failures'].append({
                    'url': result.url,
                    'law_number': result.law_number,
                    'error': result.error_message
                })

        # Year-based statistics
        year_stats = {}
        for law in laws:
            if law.year:
                year = law.year
                if year not in year_stats:
                    year_stats[year] = {'total': 0, 'successful': 0}
                year_stats[year]['total'] += 1

        # Match successful fetches to years
        for result in fetch_results:
            if result.success and result.law_number:
                # Find corresponding law
                matching_law = next((law for law in laws if law.number == result.law_number), None)
                if matching_law and matching_law.year:
                    year_stats[matching_law.year]['successful'] += 1

        report['year_statistics'] = year_stats

        return report

    def save_reports(self, laws: List[LawDocument], fetch_results: List, validation_results: Dict):
        """
        Save various reports and metadata to files.

        Args:
            laws: List of law documents
            fetch_results: Fetch results from br_legal_parser
            validation_results: URN validation results
        """
        metadata_dir = self.output_dir / 'metadata'

        # Generate comprehensive report
        report = self.generate_reports(laws, fetch_results)

        # Save main report
        with open(metadata_dir / 'fetch_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Save validation results
        with open(metadata_dir / 'validation_report.json', 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, ensure_ascii=False, indent=2)

        # Save processed laws metadata
        laws_data = [asdict(law) for law in laws]
        with open(metadata_dir / 'processed_laws.json', 'w', encoding='utf-8') as f:
            json.dump(laws_data, f, ensure_ascii=False, indent=2)

        # Save fetch results for analysis
        if self.br_legal_fetcher:
            self.br_legal_fetcher.export_results_to_csv(str(metadata_dir / 'fetch_results.csv'))

        # Save failed URLs for retry
        failed_urls = [result.url for result in fetch_results if not result.success]
        if failed_urls:
            with open(metadata_dir / 'failed_urls.txt', 'w', encoding='utf-8') as f:
                for url in failed_urls:
                    f.write(url + '\\n')

        self.logger.info(f"Reports saved to {metadata_dir}")

    def run_complete_process(self,
                           require_date: bool = True,
                           min_year: Optional[int] = None,
                           max_year: Optional[int] = None,
                           max_documents: Optional[int] = None) -> Dict:
        """
        Run the complete document fetching process.

        Args:
            require_date: Only process laws with valid dates
            min_year: Filter laws from this year onwards
            max_year: Filter laws up to this year
            max_documents: Limit number of documents to process (for testing)

        Returns:
            Dictionary with process results
        """
        start_time = time.time()

        try:
            # Step 1: Setup fetcher
            self.setup_br_legal_fetcher()

            # Step 2: Process legal documents
            laws = self.process_legal_documents(
                require_date=require_date,
                min_year=min_year,
                max_year=max_year
            )

            # Limit documents for testing
            if max_documents and len(laws) > max_documents:
                laws = laws[:max_documents]
                self.logger.info(f"Limited to first {max_documents} documents for testing")

            # Step 3: Validate URNs
            validation_results = self.validate_urns(laws)

            # Step 4: Fetch documents
            if validation_results['valid_urns'] > 0:
                fetch_results = self.fetch_documents_in_batches(laws)
            else:
                self.logger.error("No valid URNs found, skipping document fetching")
                fetch_results = []

            # Step 5: Generate and save reports
            self.save_reports(laws, fetch_results, validation_results)

            # Step 6: Cleanup
            if self.br_legal_fetcher:
                self.br_legal_fetcher.cleanup()

            end_time = time.time()
            total_time = end_time - start_time

            # Final summary
            final_results = {
                'total_runtime_seconds': round(total_time, 2),
                'laws_processed': len(laws),
                'documents_fetched': len([r for r in fetch_results if r.success]),
                'success_rate': validation_results.get('success_rate', 0),
                'output_directory': str(self.output_dir)
            }

            self.logger.info(f"Process completed in {total_time:.2f} seconds")
            self.logger.info(f"Final results: {final_results}")

            return final_results

        except Exception as e:
            self.logger.error(f"Process failed: {str(e)}")
            if self.br_legal_fetcher:
                self.br_legal_fetcher.cleanup()
            raise


def main():
    """Main function for command-line usage."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('legal_document_fetcher.log')
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting BR-TaxQA legal document fetching process")

    try:
        # Initialize fetcher
        fetcher = BRTaxQADocumentFetcher(
            input_file='referred_legal_documents_QA_2024_v1.1.json',
            output_dir='./br_taxqa_documents',
            batch_size=5,  # Small batches to be respectful
            delay_between_batches=10.0  # 10 second delays between batches
        )

        # Run process with filters for testing (last 20 years, max 20 documents)
        results = fetcher.run_complete_process(
            require_date=True,
            min_year=2000,  # Focus on recent laws
            max_documents=20  # Limit for testing
        )

        logger.info("Process completed successfully!")
        print("\\nProcess Results:")
        for key, value in results.items():
            print(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Process failed: {str(e)}")
        print(f"Error: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)