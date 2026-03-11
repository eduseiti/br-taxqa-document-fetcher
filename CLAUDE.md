# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Brazilian Legal Document Fetcher that processes the BR-TaxQA-R dataset to identify law documents, construct LexML URNs, and fetch legal documents from normas.leg.br as DOCX files using the br_legal_parser implementation.

## Key Commands

### Setup and Validation
```bash
# Install dependencies
pip install -r requirements.txt

# Clone br_legal_parser dependency
git clone https://github.com/eduseiti/br_legal_parser.git

# Validate environment setup
python validate_setup.py

# Download input dataset
curl -L "https://huggingface.co/datasets/unicamp-dl/BR-TaxQA-R/resolve/main/referred_legal_documents_QA_2024_v1.1.json" -o referred_legal_documents_QA_2024_v1.1.json
```

### Running the System
```bash
# Test document processing only
python legal_document_processor.py

# Run example usage
python example_usage.py

# Execute complete document fetching process
python legal_document_fetcher_main.py
```

### Development and Testing
```bash
# Test with limited documents for development
python -c "
from legal_document_fetcher_main import BRTaxQADocumentFetcher
fetcher = BRTaxQADocumentFetcher(max_documents=5)
results = fetcher.run_complete_process()
"
```

## Architecture Overview

The system follows a pipeline architecture:

```
Input Data (478 docs)
    ↓ [LegalDocumentProcessor]
Law Documents (123 filtered)
    ↓ [URN Construction]
Valid URNs (122 with dates)
    ↓ [BRTaxQADocumentFetcher]
DOCX Files + Reports
```

### Core Components

1. **LegalDocumentProcessor** (`legal_document_processor.py`)
   - Filters law documents from the BR-TaxQA dataset
   - Extracts law numbers and publishing dates (99.19% accuracy)
   - Constructs LexML URNs following format: `urn:lex:br:federal:lei:YYYY-MM-DD;NUMBER`

2. **BRTaxQADocumentFetcher** (`legal_document_fetcher_main.py`)
   - Orchestrates the complete document fetching process
   - Integrates with br_legal_parser for web scraping
   - Implements batch processing with rate limiting
   - Provides comprehensive error handling and reporting

3. **br_legal_parser** (external dependency)
   - Selenium-based web scraping of normas.leg.br
   - Handles JavaScript-rendered content with Shadow DOM extraction
   - Converts HTML content to DOCX format

## Key Data Structures

### LawDocument (dataclass)
- `filename`: Original filename from dataset
- `number`: Extracted law number
- `date`: Publishing date (YYYY-MM-DD format)
- `year`: Year extracted from date
- `title`: Law title
- `urn`: Constructed LexML URN
- `original_content`: Raw content from dataset

### Configuration Classes
- **FetcherConfig**: br_legal_parser configuration with rate limiting, timeouts, Selenium settings
- **BRTaxQADocumentFetcher**: Main orchestrator with batch processing and filtering options

## Important Implementation Details

### Date Extraction Patterns
The system uses multiple regex patterns to extract dates from Portuguese text:
- `dd de mês de yyyy` format (e.g., "10 de janeiro de 2002")
- `dd/mm/yyyy` and `yyyy-mm-dd` formats
- Month name mapping for Portuguese months

### URN Construction
Follows LexML standard for Brazilian federal laws:
```
urn:lex:br:federal:lei:YYYY-MM-DD;NUMBER
```

### Rate Limiting
- Default: 5.0s delay between batches
- Default batch size: 10 documents
- Configurable through BRTaxQADocumentFetcher parameters

### Error Handling
- Multi-level validation (setup, URN construction, content fetching)
- Graceful degradation on failures
- Comprehensive logging and error reporting
- Resume capability for interrupted processes

## Output Structure

```
output_directory/
├── documents/              # DOCX files from normas.leg.br
├── logs/                   # Processing and error logs
└── metadata/               # Reports and statistics
    ├── fetch_report.json
    ├── validation_report.json
    ├── processed_laws.json
    └── fetch_results.csv
```

## Dependencies

Key Python packages required:
- `selenium>=4.0.0` - Web browser automation
- `beautifulsoup4>=4.9.0` - HTML parsing
- `python-docx>=0.8.11` - Word document generation
- `requests>=2.25.0` - HTTP client
- `webdriver-manager>=3.8.0` - ChromeDriver management
- `tqdm>=4.60.0` - Progress bars
- `pandas>=1.3.0` - Data processing

## Processing Statistics

Based on BR-TaxQA-R dataset:
- **Total documents**: 478
- **Law documents identified**: 123 (25.7%)
- **Laws with valid dates**: 122 (99.19%)
- **Date range coverage**: 1937-2023 (87 years)
- **URN construction success**: 100%

## Common Filtering Options

```python
# Filter by year range
laws = processor.filter_laws_by_criteria(
    min_year=2010,
    max_year=2023,
    require_date=True
)

# Limit for testing
fetcher = BRTaxQADocumentFetcher(
    max_documents=20,
    batch_size=5
)
```

## Integration with br_legal_parser

The system integrates with the external br_legal_parser repository which handles:
- Selenium WebDriver setup and management
- Shadow DOM content extraction from normas.leg.br
- HTML to DOCX conversion with formatting preservation
- Robust error handling for web scraping

## Validation Strategy

Run `validate_setup.py` to verify:
- Python dependencies installation
- br_legal_parser integration
- Input file availability and format
- URN construction accuracy
- Sample document processing

This validation should be run before any document fetching operations.