# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Brazilian Legal Document Fetcher that processes the BR-TaxQA-R dataset to identify law documents, construct LexML URNs, and fetch legal documents from normas.leg.br as DOCX files using the br_legal_parser implementation.

## Decreto / Decreto-Lei Fetching (two sources)

Beyond `lei`, the project fetches `decreto` and `decreto_lei` documents, driven off
the curated `output_canonical/canonical_referred_documents.json` (fields
`type_slug`, `number`, `date`, `canonical_name`). Two source paths:

- **`decreto_lei` -> normas.leg.br** (Selenium, existing `br_legal_parser`):
  URN `urn:lex:br:federal:decreto.lei:YYYY-MM-DD;NUMBER`. Same Shadow-DOM SPA
  path as `lei`; only the docx filename prefix is type-aware
  (`decreto_lei_{NUMBER}_{YYYYMMDD}.docx`).
- **`decreto` -> planalto.gov.br** (`planalto_decreto_fetcher.py`, static HTML,
  ISO-8859-1): URLs are **not** formula-derivable. They are discovered from
  `_dec_ano.htm` (year index) -> per-year/decade index -> individual decree
  page, matching by (number, date). Anchor text is the reliable year signal for
  per-year links; the summary indexes use several date formats. Decrees absent
  from the indexes are recovered via a bounded direct-URL probe
  (`../Atos/decretos/YYYY/DNNNNN.html` etc.) and flagged `needs_review`.

Run: `python fetch_decretos_main.py` (both types), `--only decreto|decreto_lei`,
`--limit N`, `--dry-run`. Outputs go to `output_decretos/{documents,metadata}/`.
Undated references (e.g. `Decreto nº 50.656`) can't be matched by date and are
reported in `metadata/needs_review.json` for manual handling.

Key modules: `canonical_loader.py` (loads + de-dups canonical records by
number+date), `planalto_decreto_fetcher.py` (index discovery + clean static
extraction, reuses `WordDocumentBuilder`). Shared helpers `parse_pt_date` and
`construct_urn_helper` live in `legal_document_processor.py`. Offline tests:
`tests/test_decreto_fetching.py` (fixtures under `tests/fixtures/`).

## Instrução Normativa (Receita Federal) Fetching (third source)

`instrucao_normativa_srf` (and, parameterized, `instrucao_normativa_rfb`) come
from the Receita Federal norms portal (`sijut2consulta`) — **plain `requests`,
no Selenium**. Two stages:

- **Search** -> `GET normas.receita.fazenda.gov.br/sijut2consulta/consulta.action`
  with the *full* form field set (empty body otherwise), `tiposAtosSelecionados=42`
  (Instrução Normativa), `numero_ato`, `ano_ato`, `tipoData` (1=act date, 2=
  publicação) -> server-rendered HTML -> scrape `link.action?idAto=NNNN`.
- **Content** -> `GET normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{idAto}/visao/{slug}`
  (needs a same-site `Referer`/`Origin` or the WAF returns 403). JSON carries the
  épigrafe (type/number/date/órgão), ementa, and body segments (`outrosSegmentos`).
  View chain `original -> vigente -> multivigente` (406 = view unavailable).

Every `idAto` is **verified** against the canonical `(siglaTipoAto=IN, number,
órgão sigla=SRF, dataAto)` before saving — the same number recurs across years
and órgãos (SRF renamed RFB in 2007; genuine collisions like nº 84 in 1979 vs
2001). **Republications:** an act is often published in the DOU several times
(original + retificações), yielding multiple verified `idAto`s with identical
number/date/órgão; only the **earliest-published** one carries the full text
(later ones are correction excerpts), so it is chosen and the others recorded as
`alternate_id_atos`. Acts absent from the portal (e.g. IN SRF nº 23/1983,
nº 84/1979 predate its coverage) go to `needs_review.json`.

Run: `python fetch_instrucoes_normativas_main.py` (`--only`, `--limit N`,
`--dry-run`, `--no-docx`). Outputs to `output_instrucoes_normativas/{documents,
metadata}/`: per act a lossless `.json`, reconstructed `.txt`, and `.docx`
(parity). Key modules: `receita_norma_fetcher.py` (`ActType` registry makes the
`(tipo_code, orgao_sigla)` pair the only act-specific bits, reusable for other
RFB act types), `fetch_instrucoes_normativas_main.py` (orchestrator). Offline
tests: `tests/test_instrucao_normativa_fetching.py`.

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
python examples/example_usage.py

# Execute complete document fetching process
python legal_document_fetcher_main.py
```

### Development and Testing
```bash
# Run comprehensive test suite
python tests/run_tests.py

# Run specific test files
python -m pytest tests/test_br_tax_qa_fetcher.py -v
python -m pytest tests/test_edge_cases.py -v

# Test with limited documents for development
python -c "
from legal_document_fetcher_main import BRTaxQADocumentFetcher
fetcher = BRTaxQADocumentFetcher(max_documents=5)
results = fetcher.run_complete_process()
"

# Run example notebooks workflow
python examples/example_notebook_usage.py
python examples/notebook_workflow_validation.py
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

## Repository Structure

```
br-tax-qa/
├── legal_document_processor.py      # Core document processing
├── legal_document_fetcher_main.py   # Main orchestrator
├── validate_setup.py                # Environment validation
├── requirements.txt                 # Python dependencies
├── tests/                          # Test files
│   ├── test_br_tax_qa_fetcher.py   # Core functionality tests
│   ├── test_edge_cases.py          # Edge cases and error handling
│   └── run_tests.py                # Test runner
├── examples/                       # Usage examples
│   ├── example_usage.py            # Basic usage examples
│   ├── example_notebook_usage.py   # Jupyter notebook workflows
│   ├── notebook_workflow_validation.py  # Notebook validation
│   ├── example_*.json              # Sample data files
│   ├── example_*.txt               # Sample input files
│   └── test_recreation.ipynb       # Jupyter notebook
├── br_legal_parser/                # External dependency (submodule)
└── output_directory/               # Generated outputs
    ├── documents/                  # DOCX files from normas.leg.br
    ├── logs/                       # Processing and error logs
    └── metadata/                   # Reports and statistics
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