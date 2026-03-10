# Legal Document Fetching Script Plan

## Overview
Create a Python script that processes the BR-TaxQA-R referred legal documents list, filters for laws, constructs proper LexML URNs, and fetches documents from normas.leg.br using the existing br_legal_parser implementation.

## Implementation Steps

### 1. Data Processing Module
- **Download and parse** the `referred_legal_documents_QA_2024_v1.1.json` file
- **Filter documents** by type to select only laws (e.g., "Lei", "Lei Complementar", "Lei Delegada")
- **Extract key information**: document type, number, year, publishing date, jurisdiction level
- **Create data structures** for organizing filtered law documents

### 2. URN Construction Module
- **Implement LexML URN builder** following the standard format:
  - Base: `urn:lex:br`
  - Authority level: `federal`, `estadual:{state}`, `municipal:{city}:{state}`
  - Document type: `lei`, `lei.complementar`, `lei.delegada`
  - Date: `{YYYY-MM-DD}`
  - Number: `{number}`
  - Version (if applicable): `@{YYYY-MM-DD}`
- **Handle edge cases**: missing dates, special numbering schemes, different jurisdictions
- **Validate URN format** against LexML specification

### 3. Integration with br_legal_parser
- **Clone/setup** the br_legal_parser repository as a dependency
- **Import legal_document_fetcher** module
- **Configure fetcher parameters** for normas.leg.br integration
- **Handle authentication/rate limiting** if required

### 4. Document Fetching Module
- **Batch processing** with configurable concurrency limits
- **Error handling** for failed fetches (network, URN not found, etc.)
- **Progress tracking** with logging for large datasets
- **DOCX file organization** in structured directory hierarchy

### 5. Validation Strategy
- **URN validation**: Test constructed URNs against known working examples
- **Sample testing**: Manual verification of 10-20 documents across different types/years
- **Data integrity checks**: Verify document metadata matches source
- **File validation**: Ensure DOCX files are properly formatted and readable
- **Coverage analysis**: Report success/failure rates by document type and year
- **Duplicate detection**: Handle cases where same law appears multiple times

## Output Structure
```
output/
├── logs/
│   ├── processing.log
│   ├── errors.log
│   └── validation_report.json
├── documents/
│   ├── federal/
│   │   ├── lei/
│   │   └── lei_complementar/
│   └── estadual/
│       └── {state}/
└── metadata/
    ├── processed_documents.json
    ├── failed_urns.json
    └── statistics.json
```

## Configuration Options
- **Source file path**: Configurable input JSON file
- **Output directory**: Customizable save location
- **Filtering criteria**: Document types to include/exclude
- **Fetch parameters**: Rate limiting, retry logic, timeout settings
- **Validation level**: Basic vs comprehensive validation

## Error Handling & Recovery
- **Resume capability**: Track processed documents to enable restarts
- **Retry logic**: Exponential backoff for network failures
- **URN fallbacks**: Alternative URN construction strategies
- **Partial success**: Continue processing even if some documents fail