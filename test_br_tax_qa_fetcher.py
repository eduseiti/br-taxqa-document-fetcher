#!/usr/bin/env python3
"""
Comprehensive tests for BRTaxQADocumentFetcher with flexible input modes.

Tests cover all new initialization parameters and input validation.
"""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from legal_document_processor import LegalDocumentProcessor, LawDocument
from legal_document_fetcher_main import BRTaxQADocumentFetcher


class TestBRTaxQADocumentFetcherInitialization:
    """Test new initialization parameters and input validation."""

    def test_default_initialization_backward_compatibility(self):
        """Test that default initialization still works for backward compatibility."""
        with patch('legal_document_fetcher_main.LegalDocumentProcessor'):
            fetcher = BRTaxQADocumentFetcher()
            assert fetcher.input_file is None  # No default file
            assert fetcher.pre_processed_laws is None
            assert fetcher.processor_instance is None
            assert fetcher.urls_file is None
            assert fetcher.output_dir == Path('./fetched_documents')

    def test_input_file_initialization(self):
        """Test initialization with input_file parameter."""
        test_file = "test_input.json"
        with patch('legal_document_fetcher_main.LegalDocumentProcessor') as mock_processor:
            fetcher = BRTaxQADocumentFetcher(input_file=test_file)
            assert fetcher.input_file == test_file
            assert fetcher.processor is not None
            mock_processor.assert_called_once_with(test_file)

    def test_laws_list_initialization(self):
        """Test initialization with pre-processed laws list."""
        test_laws = [
            LawDocument(
                filename="test.txt",
                number="12345",
                date="2020-01-01",
                year="2020",
                title="Test Law",
                urn="urn:lex:br:federal:lei:2020-01-01;12345",
                original_content="test content"
            )
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        assert fetcher.pre_processed_laws == test_laws
        assert fetcher.processor is None

    def test_processor_instance_initialization(self):
        """Test initialization with existing processor instance."""
        mock_processor = Mock(spec=LegalDocumentProcessor)
        mock_processor.laws = []

        fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)
        assert fetcher.processor_instance == mock_processor
        assert fetcher.processor == mock_processor

    def test_urls_file_initialization(self):
        """Test initialization with URLs file."""
        urls_file = "test_urls.txt"

        fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
        assert fetcher.urls_file == urls_file
        assert fetcher.processor is None


class TestInputValidation:
    """Test input parameter validation logic."""

    def test_multiple_inputs_raises_error(self):
        """Test that providing multiple input methods raises ValueError."""
        test_laws = [Mock(spec=LawDocument)]

        with pytest.raises(ValueError, match="exactly one input method"):
            BRTaxQADocumentFetcher(
                input_file="test.json",
                laws=test_laws
            )

    def test_invalid_laws_parameter_type(self):
        """Test that invalid laws parameter raises ValueError."""
        with pytest.raises(ValueError, match="list of LawDocument objects"):
            BRTaxQADocumentFetcher(laws="not_a_list")

        with pytest.raises(ValueError, match="list of LawDocument objects"):
            BRTaxQADocumentFetcher(laws=[1, 2, 3])

    def test_invalid_processor_instance_type(self):
        """Test that invalid processor_instance parameter raises ValueError."""
        with pytest.raises(ValueError, match="LegalDocumentProcessor object"):
            BRTaxQADocumentFetcher(processor_instance="not_a_processor")

    def test_invalid_urls_file_parameter_type(self):
        """Test that invalid urls_file parameter raises ValueError."""
        with pytest.raises(ValueError, match="string path"):
            BRTaxQADocumentFetcher(urls_file=123)

    def test_valid_single_input_methods(self):
        """Test that each valid single input method works."""
        # Test input_file
        with patch('legal_document_fetcher_main.LegalDocumentProcessor'):
            fetcher1 = BRTaxQADocumentFetcher(input_file="test.json")
            assert fetcher1.input_file == "test.json"

        # Test laws
        test_laws = [Mock(spec=LawDocument)]
        fetcher2 = BRTaxQADocumentFetcher(laws=test_laws)
        assert fetcher2.pre_processed_laws == test_laws

        # Test processor_instance
        mock_processor = Mock(spec=LegalDocumentProcessor)
        fetcher3 = BRTaxQADocumentFetcher(processor_instance=mock_processor)
        assert fetcher3.processor_instance == mock_processor

        # Test urls_file
        fetcher4 = BRTaxQADocumentFetcher(urls_file="test_urls.txt")
        assert fetcher4.urls_file == "test_urls.txt"


class TestHelperMethods:
    """Test helper methods for different input modes."""

    def test_load_from_urls_file(self):
        """Test loading laws from URLs file."""
        urls_content = """https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;12345
https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-02-15;67890
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(urls_content)
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)

            assert len(laws) == 2
            assert laws[0].number == "12345"
            assert laws[0].date == "2020-01-01"
            assert laws[0].year == "2020"
            assert laws[1].number == "67890"
            assert laws[1].date == "2021-02-15"
            assert laws[1].year == "2021"
        finally:
            os.unlink(urls_file)

    def test_load_from_urls_file_missing_file(self):
        """Test loading from non-existent URLs file."""
        fetcher = BRTaxQADocumentFetcher(urls_file="nonexistent.txt")

        with pytest.raises(FileNotFoundError):
            fetcher._load_from_urls_file("nonexistent.txt")

    def test_load_from_urls_file_invalid_urls(self):
        """Test loading from URLs file with invalid URLs."""
        invalid_urls_content = """invalid_url_without_urn
https://example.com/no_urn_parameter
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(invalid_urls_content)
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)

            # Should return empty list since no valid URLs
            assert len(laws) == 0
        finally:
            os.unlink(urls_file)

    def test_get_laws_from_processor_with_laws(self):
        """Test getting laws from processor with processed laws."""
        mock_processor = Mock(spec=LegalDocumentProcessor)
        test_laws = [Mock(spec=LawDocument)]
        mock_processor.laws = test_laws

        fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)
        laws = fetcher._get_laws_from_processor(mock_processor)

        assert laws == test_laws

    def test_get_laws_from_processor_no_laws(self):
        """Test getting laws from processor with no processed laws."""
        mock_processor = Mock(spec=LegalDocumentProcessor)
        mock_processor.laws = []

        fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)

        with pytest.raises(ValueError, match="no processed laws"):
            fetcher._get_laws_from_processor(mock_processor)

    def test_apply_manual_filters(self):
        """Test manual filtering when processor is not available."""
        test_laws = [
            LawDocument("test1.txt", "123", "2020-01-01", "2020", "Law 1", "urn1", "content1"),
            LawDocument("test2.txt", "456", "2021-01-01", "2021", "Law 2", "urn2", "content2"),
            LawDocument("test3.txt", "789", None, None, "Law 3", "urn3", "content3"),
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)

        # Test require_date filter
        filtered = fetcher._apply_manual_filters(test_laws, require_date=True)
        assert len(filtered) == 2  # Only laws with dates

        # Test year range filter
        filtered = fetcher._apply_manual_filters(test_laws, min_year=2021)
        assert len(filtered) == 1  # Only law from 2021
        assert filtered[0].number == "456"

        # Test combined filters
        filtered = fetcher._apply_manual_filters(test_laws, require_date=True, max_year=2020)
        assert len(filtered) == 1  # Only law from 2020 with date
        assert filtered[0].number == "123"


class TestProcessLegalDocuments:
    """Test the refactored process_legal_documents method."""

    def test_process_with_pre_processed_laws(self):
        """Test processing with pre-processed laws."""
        test_laws = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content")
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)

        with patch.object(fetcher, '_apply_manual_filters', return_value=test_laws) as mock_filter:
            result = fetcher.process_legal_documents()

            assert fetcher.laws == test_laws
            mock_filter.assert_called_once()
            assert result == test_laws

    def test_process_with_urls_file(self):
        """Test processing with URLs file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;12345\n")
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)

            with patch.object(fetcher, '_apply_manual_filters') as mock_filter:
                mock_filter.return_value = []
                result = fetcher.process_legal_documents()

                assert len(fetcher.laws) == 1
                mock_filter.assert_called_once()
        finally:
            os.unlink(urls_file)

    def test_process_with_processor_instance(self):
        """Test processing with processor instance."""
        mock_processor = Mock(spec=LegalDocumentProcessor)
        test_laws = [Mock(spec=LawDocument)]
        mock_processor.laws = test_laws
        mock_processor.filter_laws_by_criteria.return_value = test_laws
        mock_processor.get_statistics.return_value = {}

        fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)
        result = fetcher.process_legal_documents()

        assert result == test_laws
        mock_processor.filter_laws_by_criteria.assert_called_once()

    def test_process_with_input_file(self):
        """Test processing with input file."""
        with patch('legal_document_fetcher_main.LegalDocumentProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_documents.return_value = []
            mock_processor.filter_laws_by_criteria.return_value = []
            mock_processor.get_statistics.return_value = {}
            mock_processor_class.return_value = mock_processor

            fetcher = BRTaxQADocumentFetcher(input_file="test.json")
            result = fetcher.process_legal_documents()

            mock_processor.process_documents.assert_called_once()
            mock_processor.filter_laws_by_criteria.assert_called_once()


class TestFetchDocumentsWithoutProcessor:
    """Test fetching documents when no processor is available."""

    def test_fetch_documents_constructs_urls_directly(self):
        """Test that URLs are constructed directly when processor is not available."""
        test_laws = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law",
                       "urn:lex:br:federal:lei:2020-01-01;123", "content")
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        fetcher.br_legal_fetcher = Mock()
        fetcher.br_legal_fetcher.process_url_list.return_value = []

        with patch.object(fetcher.br_legal_fetcher, 'process_url_list') as mock_process:
            mock_process.return_value = []
            fetcher.fetch_documents_in_batches(test_laws)

            # Verify URLs were constructed directly
            call_args = mock_process.call_args[0][0]  # Get the URLs argument
            expected_url = "https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;123"
            assert call_args[0] == expected_url


class TestIntegrationNotebookWorkflow:
    """Integration tests for notebook workflow compatibility."""

    def test_notebook_workflow_with_processor_instance(self):
        """Test the workflow that would be used in a notebook."""
        # Simulate what happens in a notebook
        with patch('legal_document_fetcher_main.LegalDocumentProcessor') as mock_processor_class:
            # Step 1: Create and process with LegalDocumentProcessor
            mock_processor = Mock()
            mock_processor.laws = [
                LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content")
            ]
            mock_processor.filter_laws_by_criteria.return_value = mock_processor.laws
            mock_processor.get_statistics.return_value = {'total_laws': 1}
            mock_processor_class.return_value = mock_processor

            # Step 2: Create fetcher with processor instance (notebook scenario)
            fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)

            # Step 3: Process should use existing processor
            laws = fetcher.process_legal_documents()

            # Verify no new processing was done
            mock_processor.process_documents.assert_not_called()
            assert laws == mock_processor.laws

    def test_notebook_workflow_with_laws_list(self):
        """Test workflow with direct laws list from notebook."""
        # Simulate laws already processed in notebook
        laws_from_notebook = [
            LawDocument("lei1.txt", "123", "2020-01-01", "2020", "Law 1", "urn1", "content1"),
            LawDocument("lei2.txt", "456", "2021-01-01", "2021", "Law 2", "urn2", "content2"),
        ]

        # Create fetcher with pre-processed laws
        fetcher = BRTaxQADocumentFetcher(laws=laws_from_notebook)

        # Process should use the provided laws
        result = fetcher.process_legal_documents(require_date=True)

        # Should return filtered laws (both have dates)
        assert len(result) == 2


class TestBackwardCompatibility:
    """Test that existing code continues to work."""

    def test_original_main_function_compatibility(self):
        """Test that the original main function approach still works."""
        with patch('legal_document_fetcher_main.LegalDocumentProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_documents.return_value = []
            mock_processor.filter_laws_by_criteria.return_value = []
            mock_processor.get_statistics.return_value = {}
            mock_processor_class.return_value = mock_processor

            # This is how the original code worked
            fetcher = BRTaxQADocumentFetcher(
                input_file='referred_legal_documents_QA_2024_v1.1.json',
                output_dir='./br_taxqa_documents'
            )

            # Should work without issues
            laws = fetcher.process_legal_documents()
            assert laws == []

    def test_run_complete_process_compatibility(self):
        """Test that run_complete_process works with all input modes."""
        test_laws = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content")
        ]

        with patch.object(BRTaxQADocumentFetcher, 'setup_br_legal_fetcher'), \
             patch.object(BRTaxQADocumentFetcher, 'fetch_documents_in_batches', return_value=[]), \
             patch.object(BRTaxQADocumentFetcher, 'save_reports'):

            fetcher = BRTaxQADocumentFetcher(laws=test_laws)

            # Should complete without errors
            results = fetcher.run_complete_process()

            assert 'total_runtime_seconds' in results
            assert results['laws_processed'] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])