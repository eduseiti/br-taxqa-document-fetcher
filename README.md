# BR-TaxQA Legal Document Fetcher

This project provides a complete solution for fetching Brazilian legal documents from the normas.leg.br website based on the referred legal documents in the BR-TaxQA-R dataset. It processes law documents, constructs proper LexML URNs, and fetches them as DOCX files using the br_legal_parser implementation.

## Overview

The system takes the `referred_legal_documents_QA_2024_v1.1.json` file from the [BR-TaxQA-R dataset](https://huggingface.co/datasets/unicamp-dl/BR-TaxQA-R), filters for law documents, constructs proper URNs following the LexML standard, and fetches the documents from normas.leg.br.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Input Data                           │
│  referred_legal_documents_QA_2024_v1.1.json            │
│  (478 documents from BR-TaxQA-R dataset)               │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              LegalDocumentProcessor                     │
│  • Filter law documents (123 laws identified)          │
│  • Extract law numbers and dates                       │
│  • Construct LexML URNs                                │
│  • Validate URN format                                 │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              BRTaxQADocumentFetcher                     │
│  • Batch processing with rate limiting                 │
│  • Integration with br_legal_parser                    │
│  • Error handling and retry logic                      │
│  • Progress tracking and reporting                     │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                br_legal_parser                          │
│  • Selenium-based web scraping                         │
│  • Shadow DOM content extraction                       │
│  • DOCX file generation                                │
│  • normas.leg.br integration                           │
└─────────────────────────────────────────────────────────┘
```

## Key Features

- **Automatic Law Identification**: Filters 123 law documents from 478 total documents
- **LexML URN Construction**: Creates proper URNs following the format `urn:lex:br:federal:lei:YYYY-MM-DD;NUMBER`
- **Date Extraction**: Extracts publishing dates from filenames and content (99.19% success rate)
- **Batch Processing**: Processes documents in configurable batches with rate limiting
- **Error Handling**: Comprehensive error handling with retry logic and fallback strategies
- **Progress Tracking**: Detailed logging and progress reporting
- **Validation**: Multi-level validation of URNs, dates, and processing pipeline

## Installation

1. **Clone the repository and dependencies:**
   ```bash
   git clone https://github.com/eduseiti/br_legal_parser.git
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download the input data:**
   ```bash
   curl -L "https://huggingface.co/datasets/unicamp-dl/BR-TaxQA-R/resolve/main/referred_legal_documents_QA_2024_v1.1.json" -o referred_legal_documents_QA_2024_v1.1.json
   ```

## Quick Start

1. **Validate the setup:**
   ```bash
   python validate_setup.py
   ```

2. **Test document processing:**
   ```bash
   python legal_document_processor.py
   ```

3. **Run the complete fetching process:**
   ```bash
   python legal_document_fetcher_main.py
   ```

## Usage Examples

### Basic Document Processing

```python
from legal_document_processor import LegalDocumentProcessor

# Initialize processor
processor = LegalDocumentProcessor('referred_legal_documents_QA_2024_v1.1.json')

# Process documents
laws = processor.process_documents()

# Filter laws with valid dates
laws_with_dates = processor.filter_laws_by_criteria(require_date=True)

# Export results
processor.export_to_json(laws_with_dates, 'processed_laws.json')
processor.export_urls_list(laws_with_dates, 'law_urls.txt')
```

### Complete Document Fetching

```python
from legal_document_fetcher_main import BRTaxQADocumentFetcher

# Initialize fetcher
fetcher = BRTaxQADocumentFetcher(
    input_file='referred_legal_documents_QA_2024_v1.1.json',
    output_dir='./legal_documents',
    batch_size=5,
    delay_between_batches=10.0
)

# Run complete process
results = fetcher.run_complete_process(
    require_date=True,
    min_year=2000,      # Filter recent laws
    max_documents=20    # Limit for testing
)
```

### Custom Filtering

```python
# Filter laws by year range
recent_laws = processor.filter_laws_by_criteria(
    min_year=2010,
    max_year=2023,
    require_date=True
)

# Get specific law types (all laws are already filtered)
civil_code_laws = [law for law in laws if 'civil' in law.title.lower()]
```

## Output Structure

```
output_directory/
├── documents/              # DOCX files from normas.leg.br
│   ├── lei_10406_20020110.docx
│   ├── lei_8112_19901211.docx
│   └── ...
├── logs/
│   ├── legal_document_fetcher.log
│   └── processing.log
└── metadata/
    ├── fetch_report.json        # Comprehensive results
    ├── validation_report.json   # URN validation results
    ├── processed_laws.json      # Law metadata
    ├── fetch_results.csv        # br_legal_parser results
    └── failed_urls.txt          # URLs that failed to fetch
```

## Processing Statistics

Based on the BR-TaxQA-R dataset:

- **Total documents**: 478
- **Law documents identified**: 123
- **Laws with valid dates**: 122 (99.19%)
- **Date range**: 1937-2023
- **URN construction success**: ~100%

## URN Format

The system uses the LexML URN standard for Brazilian legislation:

```
urn:lex:br:federal:lei:YYYY-MM-DD;NUMBER
```

**Examples:**
- `urn:lex:br:federal:lei:2002-01-10;10406` (Código Civil)
- `urn:lex:br:federal:lei:1990-12-11;8112` (Regime Jurídico dos Servidores)
- `urn:lex:br:federal:lei:2000-12-19;10101` (Participação nos Lucros)

## Configuration Options

### Batch Processing
- `batch_size`: Number of documents per batch (default: 10)
- `delay_between_batches`: Delay between batches in seconds (default: 5.0)

### br_legal_parser Configuration
- `request_timeout`: HTTP timeout (default: 30s)
- `retry_attempts`: Number of retries (default: 3)
- `delay_between_requests`: Delay between individual requests (default: 2.0s)
- `selenium_wait_time`: Shadow DOM wait time (default: 20s)

### Filtering Options
- `require_date`: Only process laws with valid dates (default: True)
- `min_year`/`max_year`: Year range filters
- `max_documents`: Limit number of documents (for testing)

## Error Handling

The system includes multiple layers of error handling:

1. **URN Validation**: Validates URN format before fetching
2. **Network Errors**: Retry logic with exponential backoff
3. **Content Validation**: Validates fetched content
4. **Batch Isolation**: Failed batches don't stop the entire process
5. **Graceful Degradation**: Continues with partial results

## Validation Strategy

The system includes comprehensive validation:

1. **Setup Validation** (`validate_setup.py`):
   - Dependency checks
   - br_legal_parser integration
   - Input file validation
   - URN construction testing

2. **Processing Validation**:
   - Law document identification
   - Date extraction accuracy
   - URN format compliance

3. **Fetch Validation**:
   - URL accessibility
   - Content quality checks
   - DOCX file integrity

## Known Limitations

1. **Selenium Dependency**: Requires Chrome browser for JavaScript-rendered content
2. **Rate Limiting**: Manual configuration required to respect server limits
3. **Date Extraction**: Some laws may have ambiguous or missing dates
4. **Content Validation**: Limited validation of legal document structure

## Contributing

To add new features or fix issues:

1. **Fork the repository**
2. **Create feature branch**
3. **Add tests for new functionality**
4. **Update documentation**
5. **Submit pull request**

## Dependencies

- **selenium**: Web browser automation
- **beautifulsoup4**: HTML parsing
- **python-docx**: Word document generation
- **requests**: HTTP client
- **webdriver-manager**: ChromeDriver management
- **tqdm**: Progress bars
- **pandas**: Data processing

## License

This project uses the br_legal_parser which is licensed under MIT License. See the individual repository for details.

## Acknowledgments

- **br_legal_parser**: Eduardo Seiti for the foundational legal document fetching implementation
- **BR-TaxQA-R**: unicamp-dl team for the comprehensive legal document dataset
- **normas.leg.br**: Brazilian government for providing public access to legal documents

## Support

For issues related to:
- **Document processing**: Check the logs in `output/logs/`
- **br_legal_parser**: Refer to the original repository documentation
- **Dataset issues**: Contact the BR-TaxQA-R team
- **Chrome/Selenium**: Update ChromeDriver or check browser installation

## Recent Updates

### Version 1.0 (March 2026)
- Initial implementation
- Integration with br_legal_parser
- Comprehensive validation system
- Batch processing with rate limiting
- Multi-level error handling
- Detailed reporting and statistics