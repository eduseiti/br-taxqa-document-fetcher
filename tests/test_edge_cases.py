#!/usr/bin/env python3
"""
Edge case and error handling tests for BRTaxQADocumentFetcher.

Tests error conditions, edge cases, and resilience scenarios.
"""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legal_document_processor import LegalDocumentProcessor, LawDocument
from legal_document_fetcher_main import BRTaxQADocumentFetcher


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_no_input_method_provided(self):
        """Test behavior when no input method is provided."""
        # Should fall back to default behavior for backward compatibility
        fetcher = BRTaxQADocumentFetcher()
        assert fetcher.input_file is None
        assert fetcher.pre_processed_laws is None
        assert fetcher.processor_instance is None
        assert fetcher.urls_file is None

    def test_process_documents_with_no_valid_input_raises_error(self):
        """Test that process_legal_documents raises error with no valid input."""
        fetcher = BRTaxQADocumentFetcher()  # No input provided

        with pytest.raises(ValueError, match="No valid input method provided"):
            fetcher.process_legal_documents()

    def test_empty_laws_list(self):
        """Test behavior with empty laws list."""
        empty_laws = []
        fetcher = BRTaxQADocumentFetcher(laws=empty_laws)

        result = fetcher.process_legal_documents()
        assert result == []

    def test_laws_list_with_none_values(self):
        """Test laws list containing None values."""
        laws_with_none = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content"),
            None
        ]

        with pytest.raises(ValueError, match="list of LawDocument objects"):
            BRTaxQADocumentFetcher(laws=laws_with_none)

    def test_urls_file_with_empty_content(self):
        """Test URLs file with empty content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("")  # Empty file
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)
            assert laws == []
        finally:
            os.unlink(urls_file)

    def test_urls_file_with_only_whitespace(self):
        """Test URLs file with only whitespace."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("   \n  \t  \n   ")  # Only whitespace
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)
            assert laws == []
        finally:
            os.unlink(urls_file)

    def test_urls_file_with_malformed_urns(self):
        """Test URLs file with malformed URNs."""
        malformed_urls = """https://normas.leg.br/?urn=urn:lex:br:federal:lei:invalid-date;123
https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;invalid-number
https://normas.leg.br/?urn=completely:malformed:urn
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(malformed_urls)
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)
            # Should skip malformed URNs
            assert len(laws) == 0
        finally:
            os.unlink(urls_file)

    def test_processor_instance_without_laws_attribute(self):
        """Test processor instance that doesn't have laws attribute."""
        mock_processor = Mock(spec=LegalDocumentProcessor)
        # Remove the laws attribute
        del mock_processor.laws

        fetcher = BRTaxQADocumentFetcher(processor_instance=mock_processor)

        with pytest.raises(AttributeError):
            fetcher._get_laws_from_processor(mock_processor)

    def test_manual_filters_with_invalid_year_data(self):
        """Test manual filters with invalid year data."""
        test_laws = [
            LawDocument("test1.txt", "123", "2020-01-01", "invalid_year", "Law 1", "urn1", "content1"),
            LawDocument("test2.txt", "456", "2021-01-01", "", "Law 2", "urn2", "content2"),  # Empty year
            LawDocument("test3.txt", "789", "2022-01-01", None, "Law 3", "urn3", "content3"),  # None year
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)

        # Should handle invalid years gracefully
        result = fetcher._apply_manual_filters(test_laws, min_year=2021)
        # Only laws with valid years >= 2021 should be included (none in this case)
        assert len(result) == 0

    def test_fetch_without_br_legal_fetcher_setup(self):
        """Test fetching documents without setting up br_legal_fetcher."""
        test_laws = [
            LawDocument("test.txt", "123", "2020-01-01", "2020", "Test Law", "urn", "content")
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        # Don't call setup_br_legal_fetcher()

        with pytest.raises(ValueError, match="br_legal_fetcher not initialized"):
            fetcher.fetch_documents_in_batches(test_laws)


class TestDataConsistency:
    """Test data consistency across different input modes."""

    def test_same_laws_different_input_modes_produce_same_results(self):
        """Test that same laws via different input modes produce same results."""
        # Create test laws
        test_laws = [
            LawDocument("lei123.txt", "123", "2020-01-01", "2020", "Lei 123",
                       "urn:lex:br:federal:lei:2020-01-01;123", "content123"),
            LawDocument("lei456.txt", "456", "2021-06-15", "2021", "Lei 456",
                       "urn:lex:br:federal:lei:2021-06-15;456", "content456"),
        ]

        # Create URLs file with same laws
        urls_content = """https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;123
https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-06-15;456
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(urls_content)
            urls_file = f.name

        try:
            # Test with laws list
            fetcher1 = BRTaxQADocumentFetcher(laws=test_laws)
            result1 = fetcher1.process_legal_documents(require_date=True)

            # Test with URLs file
            fetcher2 = BRTaxQADocumentFetcher(urls_file=urls_file)
            result2 = fetcher2.process_legal_documents(require_date=True)

            # Results should have same number of laws
            assert len(result1) == len(result2) == 2

            # Results should have same law numbers (order might differ)
            numbers1 = {law.number for law in result1}
            numbers2 = {law.number for law in result2}
            assert numbers1 == numbers2 == {"123", "456"}

        finally:
            os.unlink(urls_file)

    def test_processor_vs_manual_filtering_consistency(self):
        """Test that processor filtering and manual filtering produce same results."""
        test_laws = [
            LawDocument("lei1.txt", "123", "2020-01-01", "2020", "Lei 123", "urn1", "content1"),
            LawDocument("lei2.txt", "456", "2021-01-01", "2021", "Lei 456", "urn2", "content2"),
            LawDocument("lei3.txt", "789", None, None, "Lei 789", "urn3", "content3"),
        ]

        # Mock processor with filtering
        mock_processor = Mock(spec=LegalDocumentProcessor)
        mock_processor.laws = test_laws
        mock_processor.filter_laws_by_criteria.return_value = test_laws[:2]  # Only laws with dates

        # Test with processor (should use processor filtering)
        fetcher1 = BRTaxQADocumentFetcher(processor_instance=mock_processor)
        result1 = fetcher1.process_legal_documents(require_date=True)

        # Test with laws only (should use manual filtering)
        fetcher2 = BRTaxQADocumentFetcher(laws=test_laws)
        result2 = fetcher2.process_legal_documents(require_date=True)

        # Both should filter out law without date
        assert len(result1) == 2
        assert len(result2) == 2
        assert {law.number for law in result1} == {"123", "456"}
        assert {law.number for law in result2} == {"123", "456"}


class TestPerformanceEdgeCases:
    """Test performance-related edge cases."""

    def test_large_laws_list(self):
        """Test with large number of laws."""
        # Create 1000 test laws
        large_laws_list = []
        for i in range(1000):
            law = LawDocument(
                filename=f"lei{i}.txt",
                number=str(i),
                date=f"2020-01-{(i % 28) + 1:02d}",
                year="2020",
                title=f"Lei {i}",
                urn=f"urn:lex:br:federal:lei:2020-01-{(i % 28) + 1:02d};{i}",
                original_content=f"content{i}"
            )
            large_laws_list.append(law)

        fetcher = BRTaxQADocumentFetcher(laws=large_laws_list)

        # Should handle large list without issues
        result = fetcher.process_legal_documents()
        assert len(result) == 1000

    def test_empty_filtering_results(self):
        """Test when filtering results in empty list."""
        test_laws = [
            LawDocument("lei1.txt", "123", "1950-01-01", "1950", "Old Lei", "urn1", "content1"),
            LawDocument("lei2.txt", "456", "1960-01-01", "1960", "Old Lei 2", "urn2", "content2"),
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)

        # Filter for laws after 2000 (should be empty)
        result = fetcher.process_legal_documents(min_year=2000)
        assert result == []


class TestSpecialCharactersAndEncoding:
    """Test handling of special characters and encoding issues."""

    def test_laws_with_special_characters(self):
        """Test laws with special characters in title and content."""
        test_laws = [
            LawDocument(
                filename="lei_ção.txt",
                number="123",
                date="2020-01-01",
                year="2020",
                title="Lei sobre Prevenção de Poluição",
                urn="urn:lex:br:federal:lei:2020-01-01;123",
                original_content="Conteúdo com acentos: ção, ãe, õ"
            )
        ]

        fetcher = BRTaxQADocumentFetcher(laws=test_laws)
        result = fetcher.process_legal_documents()

        assert len(result) == 1
        assert "ção" in result[0].title

    def test_urls_file_with_special_characters(self):
        """Test URLs file with special characters."""
        # URLs should be properly encoded, but test graceful handling
        urls_content = """https://normas.leg.br/?urn=urn:lex:br:federal:lei:2020-01-01;123
# Comment with special chars: ção, ãe, õ
https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-01-01;456
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            f.write(urls_content)
            urls_file = f.name

        try:
            fetcher = BRTaxQADocumentFetcher(urls_file=urls_file)
            laws = fetcher._load_from_urls_file(urls_file)

            # Should parse valid URLs and ignore comments
            assert len(laws) == 2
        finally:
            os.unlink(urls_file)


class TestConcurrentAccess:
    """Test thread safety and concurrent access scenarios."""

    def test_multiple_fetcher_instances(self):
        """Test multiple fetcher instances with same data."""
        test_laws = [
            LawDocument("lei.txt", "123", "2020-01-01", "2020", "Lei", "urn", "content")
        ]

        # Create multiple instances
        fetcher1 = BRTaxQADocumentFetcher(laws=test_laws)
        fetcher2 = BRTaxQADocumentFetcher(laws=test_laws)

        # Both should work independently
        result1 = fetcher1.process_legal_documents()
        result2 = fetcher2.process_legal_documents()

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].number == result2[0].number

    def test_state_isolation(self):
        """Test that fetcher instances don't share state."""
        test_laws1 = [
            LawDocument("lei1.txt", "123", "2020-01-01", "2020", "Lei 1", "urn1", "content1")
        ]
        test_laws2 = [
            LawDocument("lei2.txt", "456", "2021-01-01", "2021", "Lei 2", "urn2", "content2")
        ]

        fetcher1 = BRTaxQADocumentFetcher(laws=test_laws1)
        fetcher2 = BRTaxQADocumentFetcher(laws=test_laws2)

        result1 = fetcher1.process_legal_documents()
        result2 = fetcher2.process_legal_documents()

        # Each should have processed only its own laws
        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].number == "123"
        assert result2[0].number == "456"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])