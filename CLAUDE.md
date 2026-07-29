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

## Receita Federal Norms Fetching (third source — all act types)

All Receita-Federal-portal acts referenced in the canonical file come from the
Receita norms portal (`sijut2consulta`) — **plain `requests`, no Selenium**. This
started as Instrução Normativa SRF and is now generalized to **every act type in
the `ACT_TYPES` registry**: IN (SRF/RFB), Solução de Consulta / Interna /
Divergência (Cosit), Ato Declaratório "Comum"/Executivo/Interpretativo/Normativo
(SRF/RFB/Cosit/Cosar/Codac/PGFN), Parecer Normativo (CST/Cosit), Portaria MF,
Resolução CGSN, Despacho, etc. Two stages:

- **Search** -> `GET normas.receita.fazenda.gov.br/sijut2consulta/consulta.action`
  with the *full* form field set (empty body otherwise): `tiposAtosSelecionados`
  = the "Tipo do ato" code (IN=42, SC=72, SCI=75, SD=73, AD=7, ADE=9, ADI=10,
  ADN=11, Parec. Norm.=59, Parec.=61, Nota=77, Port.=57, Resol.=67, Desp.=35),
  **`orgaosSelecionados` = the órgão facet value** (e.g. `SRF`, `RFB`, `Cosit`,
  `CST`, `PGFN`, `Codac`, `MF`, `CGSN` — the value **is** the sigla; the portal
  filters by órgão server-side, which resolves same-number/same-year collisions
  across órgãos), `numero_ato`, `ano_ato`, `tipoData` (1=act date, 2=publicação)
  -> server-rendered HTML -> scrape `link.action?idAto=NNNN`.
- **Content** -> `GET normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{idAto}/visao/{slug}`
  (needs a same-site `Referer`/`Origin` or the WAF returns 403). JSON carries the
  épigrafe (type/number/date/órgão), ementa, and body segments (`outrosSegmentos`).
  View chain **`vigente -> multivigente -> original`** (406 = view unavailable);
  see "Rendering fidelity" below for why `vigente` and not `original`.
- **Annexes** -> `GET .../api/consulta-externa/ato/{idAto}/anexo/{idArquivoBinario}`
  (same-site headers likewise; undocumented — every sibling path 403s).

Every `idAto` is **verified** against the canonical act before saving:
`epigrafe.tipoAto.idTipoAto == tipo_code` (numeric — robust to punctuated siglas
like `Parec. Norm.`), `numeroAto == number`, `orgaos[].siglaOrgao == orgao`
(**case-insensitive**; portal mixes `SRF`/`RFB`/`CST` with `Cosit`/`Codac`), and
`dataAto`. The same number recurs across years/órgãos (SRF renamed RFB in 2007;
`AD nº 22/1997` exists for SRF, Cosar **and** Cosit with three different dates).
Act types whose issuing unit is ambiguous/regional (a generic `Parecer`, or
`Disit/SRRF` Soluções de Consulta) use `orgao=None` → match on tipo+number+date
only. **Republications:** an act published in the DOU several times (original +
retificações) yields multiple verified `idAto`s with identical number/date/órgão;
only the **earliest-published** one carries the full text, so it is chosen and the
others recorded as `alternate_id_atos`. Acts absent from the portal (e.g. IN SRF
nº 23/1983, Parecer SEI, Parecer PGFNCAT) go to `needs_review.json`.

Run: `python fetch_receita_normas_main.py` (default: whole registry;
`--only <slug>`, `--types a,b,c`, `--exclude`, `--limit N`, `--dry-run`,
`--no-docx`, `--list`, `--view <slug>`, `--also-save-original`,
`--no-attachments`). **Output — one folder per document kind:**
`output_receita_federal/<type_slug>/{documents,metadata}/` (per act a lossless
`.json`, reconstructed `.txt`, and `.docx`; raw annexes under
`documents/attachments/`), plus
`output_receita_federal/metadata/aggregate_report.json` (roll-up across kinds).
Key modules: `receita_norma_fetcher.py` (`ActType` + `_REGISTRY_TABLE` make the
`(tipo_code, orgao)` pair the only act-specific bits), `fetch_receita_normas_main.py`
(orchestrator). The old `fetch_instrucoes_normativas_main.py` is a deprecated shim
that defaults to IN SRF + `output_instrucoes_normativas/`. Offline tests:
`tests/test_instrucao_normativa_fetching.py`.

### Rendering fidelity: the `vigente` view, annexes, ordinals

The artifacts are the act **as currently in force**, plus amendment/revocation
annotations — a deliberate change from the as-published text. Four coupled rules,
all mirroring the portal's own Angular renderer rather than inventing a layout:

- **View = `vigente`, not `original`.** Every view returns the *same* segment
  list and varies only per-segment flags. `original` carries **no
  `ancorasDestino` at all** (so no annotations) and its `omitir` mask is
  *inverted*: rendering it publishes the **superseded** wording and drops the
  current one. `vigente` also blanks individually-revoked provisions server-side,
  truncating them to their label stub (`II -`) with a `Revogado(a) pelo(a) …`
  annotation, so revoked wording cannot leak through. Whole-act revocation is not
  a segment flag — it is `vigente: false` + `ancorasNoAto` in the header, emitted
  as one banner under the épigrafe.
- **No strikethrough is ever emitted.** `tachado` is set only in `multivigente`;
  if the chain falls back there, struck segments are *dropped* instead.
- **Annexes are real content, not decoration.** An *anexo* segment
  (`idTipoSegmento == 16`) with an `arquivoBinario` renders the **attachment**
  and its flattened `textoIntegra` is dropped (the portal does the same). Inline
  base64 covers `.htm`/`.html`/`.jpg`; **PDF/DOC/ODS are by-reference** and must
  be pulled from the `/anexo/` endpoint — 268 PDFs across 143 acts, 156 of whose
  segments carry an *empty* `textoIntegra`, i.e. they were missing outright
  before. Converters: bs4 (html), PyMuPDF `find_tables()` (pdf), stdlib zipfile
  (ods), data-URI (jpg); legacy `.doc` needs LibreOffice and otherwise falls back
  to the flattened text. Raw bytes are **always** persisted first, so a converter
  failure degrades to "unformatted", never to "lost".
- **Ordinals are normalized** (`receita_text_normalize.py`): `art. 1o` → `1º`,
  `Lei No 9.250` → `Lei nº 9.250` (a digit look-ahead separates it from the
  preposition `No caso de …`), `art. 3°` → `3º`, and `<strike>º</strike>` →
  `º`. In this corpus `<strike>` is **only** a typographic hack around ordinals
  (366/366 occurrences), so it is always unwrapped — the opposite of planalto,
  which uses it for genuinely revoked text. That is why the unwrapping lives
  Receita-side and never in the shared `WordDocumentBuilder`.

Normalization touches only the `.txt`/`.docx`; the `.json` stays a byte-faithful
mirror of the API. Because `vigente` is a **moving target**, every act records
`_fetched_at` (and `exibirVisoes` / resolved `view` in the fetch report).
`--also-save-original` keeps the as-published text as a second `.json`.

Key modules: `receita_text_normalize.py` (`--audit-ordinals` prints every rewrite
with context), `receita_attachments.py` (endpoint client + converters),
`compare_receita_corpus.py` (`--baseline DIR` before/after diff, flags any act
that loses text without an `omitir`/annex explanation). Offline tests:
`tests/test_receita_rendering.py`.

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