# Bugfix: legacy Word 97 (`.doc`) annex tables, and full act denominations in the log

Date: 2026-07-29

Follows up on `20260729_191841_receita_federal_rendering_fidelity_implementation.md`.

Two items, both reported after reviewing that run's output:

1. **`IN SRF nº 84/2001`'s annex tables were still flattened.** The annex lives in
   an attached `Anexo Único.doc`; the previous work classified legacy Word 97
   binaries as unconvertible and fell back to the portal's flattened text — so the
   whole 14-table index arrived as one unbroken run of characters. **Fixed:** a
   self-contained Word 97 reader now produces real Word tables.
2. **Failed fetches logged only a bare number** (`ato_declaratorio_normativo_cst 16`),
   which is not something you can look up on the portal. **Fixed:** the log now
   carries the act's full canonical denomination.

**Outcome:** `in_srf_84_20011011.docx` goes from **1 table to 15**; corpus-wide
**778 → 810** tables across **73 → 74** acts, and the only attachments still
unconverted are 2 files that are genuinely empty.

---

## 1. Root cause

My previous log listed this under "residual limitations":

> **5 attachments unconverted** (of 254): 3 legacy `.doc` (OLE) annexes with no
> in-process converter available […] the portal's flattened text is kept, so
> nothing regresses to nothing.

That was the wrong call. "Nothing regresses" was true only against the *previous*
corpus; measured against the **goal** — real tables — those three annexes were
still exhibiting exactly the defect the work existed to remove. And they are not
incidental attachments: they contain *nothing but tables*. `Anexo Único.doc` is
the entire "Tabela de Atualização do Custo de Bens e Direitos" — 14 tables of
monthly restatement indices. Falling back to flattened text meant the act's most
table-shaped content stayed a wall of numbers.

The original code was written to shell out to LibreOffice, which is not installed
here, so the fallback path was the only one that ever ran:

```python
soffice = shutil.which("soffice") or shutil.which("libreoffice")
if not soffice:
    return "", 0, "no .doc converter available (LibreOffice not installed)"
```

## 2. The fix: `receita_doc_parser.py`

I chose a **self-contained parser** over installing LibreOffice. For a research
corpus that has to be reproducible on someone else's machine,
`pip install -r requirements.txt` is a much better contract than a 65-package
system dependency. LibreOffice is still preferred when present (it handles merged
and nested cells that this parser only approximates); the new module is the
fallback that actually runs, and it needs only `olefile`.

Two facts from [MS-DOC] are enough:

* **Text location** — the character stream is in the `WordDocument` stream, laid
  out by the **piece table** (`CLX` → `PlcPcd`), which maps character positions to
  byte offsets and records per piece whether text is 1-byte cp1252 ("compressed")
  or 2-byte UTF-16LE. All three corpus files happen to be contiguous cp1252, so
  reading `fcMin..fcMac` would have worked — but that is wrong for any
  fast-saved or Unicode document, so the piece table is honored, with the naive
  range kept only as a last-resort fallback.
* **Table structure** — `\r` ends a paragraph and **`\x07` ends a table cell**. A
  row is terminated by an *additional* `\x07` paragraph that is empty.

### 2.1 The one hard part: empty cell vs row end

Both are `\x07`. [MS-DOC] distinguishes them with the paragraph property
`sprmPFTtp`, which would mean decoding `PlcfBtePapx`/`PAPX` grpprl — a lot of
format archaeology.

My first attempt used the obvious reading, "an empty unit ends the row". It parsed
`IN SRF nº 84`'s annex perfectly (14/14 rectangular tables) — and then
`IN SRF nº 208`'s `ANEXO II.doc` showed why that was luck rather than
correctness. That annex is a **blank fill-in form**: a table whose data cells are
all empty. Every empty cell read as a row end, collapsing a 28×3 grid into 55
one-cell rows.

The fix avoids `PAPX` entirely by exploiting **periodicity**: the unit sequence is
`N` cells followed by one empty row-end unit, so the block has period `N+1`.
Recovering `N` as the smallest period that puts an empty unit at *every* row-end
position separates the two meanings of `\x07` structurally:

```python
for width in range(1, n_units):
    period = width + 1
    if n_units % period:
        continue
    if all(units[i + width] == "" for i in range(0, n_units, period)):
        return [units[i:i + width] for i in range(0, n_units, period)], True
```

A block that no period fits is reported **ragged** rather than silently emitted as
a mangled grid. On this corpus, all **32 tables across the 3 files** come out
rectangular, so nothing is left guessing.

### 2.2 A second bug the form exposed

Treating any `\r` inside a table block as a multi-paragraph cell swallowed the
headings that separate an annex's sub-tables, merging `ANEXO II`'s four tables
into one 57-row mess. A `\r` now continues a cell only when it arrives **mid-row**
(the last unit is non-empty); at a row boundary it is real prose and closes the
table. That is what makes the form parse as 4 tables with its headings intact.

## 3. Validation

The portal's flattened `textoIntegra` is the degraded rendition being replaced,
which makes it an independent inventory of what the tables must contain. Using it
as an oracle:

| annex | tables | rectangular | flattened tokens missing from output |
|---|--:|---|--:|
| `in_srf_84` / `Anexo Único.doc` | 14 | all | **0** of 701 |
| `in_srf_208` / `ANEXO I.doc` | 14 | all | 0 (annex had *empty* `textoIntegra`) |
| `in_srf_208` / `ANEXO II.doc` | 4 | all | 0 (annex had *empty* `textoIntegra`) |

The two `IN SRF nº 208` annexes carried **no** `textoIntegra` at all, so they were
absent from the corpus outright before this work and are now fully present.

`IN SRF nº 84`'s `.docx`, the reported defect:

| | baseline | after previous work | **now** |
|---|--:|--:|--:|
| Word tables | 0 | 1 | **15** |
| paragraphs | 207 | 212 | 226 |
| flattened index run present | yes | **yes** | **no** |
| `.txt` shows `JAN \| 0,8166 \| -` | no | no | **yes** |

Table shapes recovered: one 7×8 (the Art. 26 HTML annex) plus fourteen 13-row
index tables of 3/4/5/6/8 columns.

## 4. Full denominations in the fetch log

`fetch_many` logged `self.act.type_slug` + the bare number. The canonical record
already carries the exact denomination, so the log now uses it, keeping the slug
and ISO date in brackets for grepping and to make an undated entry's failure
self-explanatory:

```
✗ Ato Declaratório Normativo CST nº 16, de 27 de julho de 1979 [ato_declaratorio_normativo_cst nº 16, date=1979-07-27] - date_mismatch: 2 candidate(s) found, none matched órgão=CST/number=16/date=1979-07-27
✗ Instrução Normativa RFB nº 67 [instrucao_normativa_rfb nº 67, date=None] - not_found: No idAto returned by search
```

Successes are logged the same way (`✓ <denomination> (idAto=…) -> <file>`).

## 5. Corpus re-run

Full re-fetch of all 31 types with the fix in place — **245/245 acts, 88.13 %
coverage, unchanged**.

| Measure | baseline | previous run | **now** |
|---|--:|--:|--:|
| Word tables | 0 | 778 | **810** |
| Acts containing a table | 0 | 73 | **74** |
| Attachments unconverted | — | 5 | **2** |
| Characters | 2 871 261 | 6 221 814 | **6 234 022** |
| Annotations | 0 | 1 499 | 1 499 |
| Struck runs (invariant) | 0 | 0 | **0** |
| Acts losing text unexplained | — | 0 | **0** |

The 2 remaining unconverted attachments are both a 3-byte file the portal itself
ships named **`vazio.htm`** ("empty.htm") — in `in_srf_588_20051221` and
`pn_cosit_11_19920930`. There is nothing in them to convert; the segment's own
text is kept, which is correct.

## 6. Testing

**162 tests pass** (was 148). New: `tests/test_receita_doc_annex.py` (14 tests,
2 real `.doc` fixtures):

* piece-table text extraction (length matches the FIB's `ccpText`, cell marks
  preserved);
* period detection parametrized over the real shapes — including a blank-form row
  and a row with a trailing empty cell, plus the ragged case that must be
  *reported* rather than guessed;
* the reference annex → 14 rectangular tables with spot-checked cell values, and
  the flattened-text oracle asserting no value is lost;
* the blank form → 28×3 grid with its headings still prose;
* end-to-end segment → fragment → `.docx`: 14 real Word tables, flattened
  duplicate gone, `.txt` showing pipe-delimited rows;
* a corrupt `.doc` still degrades to the flattened text instead of raising.

One robustness gap surfaced while writing these: `olefile` raises assorted
low-level errors (`ValueError`, struct errors) on a malformed container. Those are
now normalized to `DocParseError`, so a corrupt annex degrades gracefully instead
of escaping into the fetch pipeline.

## 7. Files changed

| File | Change |
|---|---|
| `receita_doc_parser.py` | **New.** Word 97 reader: piece table, field-code stripping, cell/row reconstruction by period detection, HTML emission. Runnable directly on a `.doc` to dump its tables. |
| `receita_attachments.py` | `doc_to_fragment` prefers LibreOffice, falls back to the new parser (and falls back if LibreOffice errors or produces nothing, rather than giving up). |
| `receita_norma_fetcher.py` | `fetch_many` logs the full canonical denomination on both success and failure. |
| `requirements.txt` | Added `olefile>=0.46` and `pymupdf>=1.24.0` (the latter was already relied on but undeclared). |
| `tests/test_receita_doc_annex.py` | **New**, 14 tests + 2 `.doc` fixtures. |
| `CLAUDE.md` | `.doc` conversion path; note that failures log full denominations. |

## 8. Note on the run

`in_srf_84_20011011.docx` was open in Word during the first re-run attempt.
`/work` is a Windows drive over 9p, which surfaces the lock as `EPERM`, so the
file could not be rewritten — worth knowing, since it fails on exactly the
document under review. Closing it and running once produced a single consistent
corpus.

## 9. Open items

Unchanged from the previous log, minus the `.doc` item which is now closed:

* `vigente` is a moving target; `_fetched_at` is stamped in every `.json`.
* Merged/nested cells in a `.doc` are approximated by the built-in parser — no
  instance in this corpus, and installing LibreOffice takes precedence
  automatically if higher fidelity is ever needed.
* PDF table extraction remains heuristic; raw PDFs are always retained.
* Out of scope: the decreto pipeline still drops planalto's genuine `<strike>`
  revocation marks.
