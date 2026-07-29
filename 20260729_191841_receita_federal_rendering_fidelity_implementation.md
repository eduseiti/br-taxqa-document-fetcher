# Implementation log: Receita Federal rendering fidelity

Date: 2026-07-29

Implements `20260729_171931_receita_federal_rendering_fidelity_plan.md` — the four
reported defects in the Receita Federal artifacts (ordinals shown as `1o`, tables
flattened, amendment/revocation annotations absent, annex tables flattened),
all of which the plan established were corpus-wide rather than specific to
`IN SRF nº 84/2001`. Follows up on
`20260718_113911_receita_federal_all_acts_implementation.md`, whose 245-act
corpus is the baseline every number below is measured against.

**Outcome:** all four defects fixed, **245/245 acts re-fetched** with **zero
content lost** and **zero unexplained regressions**. The corpus grew from
2.87 M to 6.22 M characters (**+117 %**), gained **778 real Word tables** where
it previously had **none**, and now carries **1 499 amendment/revocation
annotations** that were structurally absent before.

---

## 1. Verification of the plan before implementing

Every load-bearing claim was re-checked live rather than taken on trust. All
held, and two were corrected:

| Plan claim | Verified? | Notes |
|---|---|---|
| `<strike>` is only the ordinal hack (366×) | ✅ exact | 732 tag occurrences = 366 pairs, inner text `º` in 100 % of cases |
| `/anexo/{id}` endpoint returns the binaries | ✅ | 200 for `.pdf` / `.doc` / `.ods`, correct magic bytes |
| Attachment inventory (268 pdf, 19 html, 11 htm, 5 jpg, 3 doc, 1 ods; 151 acts) | ✅ exact | plus: **156** segments with a non-inlined annex carry an *empty* `textoIntegra` |
| `original` has no `ancorasDestino`; `vigente` has them | ✅ | act 14400: 0 vs 6 |
| `vigente` blanks a revoked provision to its stub | ✅ | seg 455831: `"II - alienação … R$ 20.000,00"` → `"II -"` |
| `omitir` mask is inverted between views | ✅ | act 15079 seg 815178: v1/v2 masks swap exactly as described |
| `tachado` set only in `multivigente` | ✅ | 0 / 0 / 6 across the three views |
| PyMuPDF extracts the annex tables | ✅ | `Ano-calendário` / `Valores isentos mensais` |
| **Ordinal context guard is needed** | ❌ **corrected** | see §2.1 |
| Corpus counts `No`+digit 76 / bare `[1-9]o` 151 / `°` 48 | ≈ | measured 78 / 153 / 48 (plan counted the `.txt`, this counts the source JSON) |

### 1.1 Where the plan was wrong: the ordinal context guard

The plan proposed gating the bare-ordinal rewrite on a preceding context token
(`art`, `§`, `inciso`, `nº`, `de`, …), "measured against the corpus so all 151
hits are covered". Measuring it directly showed the opposite: the guard **misses
16 of 157 genuine ordinals** whose left neighbour is a conjunction or
preposition — `arts. 5o e 6o`, `1o de janeiro`, `§§ 2o e 3o`, `13a Edição`,
`1a) - realizá-las` — while rejecting **nothing**, because every single
`\d{1,2}[oa]\b` occurrence in the corpus is a real ordinal.

So the guard was dropped. The anchoring is purely lexical, and safety comes from
**auditability** instead: `--audit-ordinals` prints every rewrite with 40
characters of context, so a future non-ordinal use surfaces in review rather
than silently changing text. All 300 rewrites were eyeballed once this way.

The one discriminator that *is* load-bearing was kept and confirmed exhaustively:
for `No`, the digit look-ahead separates all **78** abbreviation uses
(`Lei No 9.250`) from all **336** prepositional ones (`No caso de …`) with no
false positive in either direction.

---

## 2. What changed

| File | Change |
|---|---|
| `receita_text_normalize.py` | **New.** Ordinal rules (`1o`→`1º`, `No 9.250`→`nº 9.250`, `n°`/`3°`→`nº`/`3º`), `<strike>` unwrapping, `xml_safe()`. Applied to **text nodes only**, so attributes/hrefs can never be rewritten. `--audit-ordinals` CLI. |
| `receita_attachments.py` | **New.** `/anexo/` client with disk cache + pacing; converters for html/htm (bs4), pdf (PyMuPDF `find_tables()` + reading-order interleaving + rasterize-if-empty), ods (stdlib zipfile), jpg (data URI), doc (LibreOffice if present). Raw bytes always persisted first. |
| `receita_norma_fetcher.py` | View chain → `vigente`; `_segments_html` rewritten to emit **block-level siblings** with annotations, act-level revocation banner and attachment rendering; `reconstruct_text` → `fragment_to_text`, a document-order walker that renders tables; `_fetched_at` stamping; `--view`/`--also-save-original`/`--no-attachments` plumbing; render telemetry. |
| `br_legal_parser` (submodule `d6dfe6a`) | `<br>` → real line break; recursive inline walk so nesting composes; `<p>` with block children recurses; table cells rendered with formatting, `<th>` bolded, autofit. `s`/`strike`/`del` unwrapped, never `run.font.strike`. |
| `compare_receita_corpus.py` | **New.** Before/after diff; flags any act that loses text without an `omitir`/annex explanation. |
| `tests/test_receita_rendering.py` | **New**, 51 tests + 6 fixtures captured live. |
| `CLAUDE.md` | New "Rendering fidelity" section; `/anexo/` endpoint, view chain, `attachments/` folder, new flags. |

### 2.1 Design decisions that mattered

**One rendering, two artifacts.** `_persist` builds the fragment **once** and
derives both the `.txt` and the `.docx` from it, so the two can never disagree
about what the document contains. Previously each re-derived its own.

**The renderer mirrors the portal, it does not invent.** Segment visibility
(`omitir === false`), attachment-vs-text precedence for *anexo* segments, and
"strikethrough comes only from `tachado`" are all lifted from the portal's own
deobfuscated Angular component. This is what makes "render `vigente` and stop"
sufficient — no cross-view joins, no overlay, one GET per act.

**`<strike>` unwrapping lives Receita-side.** The shared `WordDocumentBuilder`
is used by the planalto decreto pipeline, where `<strike>` marks genuinely
revoked provisions (5 804 of them in `D3000.htm`). Putting the unwrap rule in
the builder would have destroyed that signal, so the builder stays neutral
(unwraps to plain text, never emits strike) and the *semantic* decision is made
by the caller that knows which source it is reading.

---

## 3. Two bugs found by running it (not by reading it)

Both were caught because the full corpus was actually fetched and diffed, and
neither would have surfaced in the plan's fixture-level tests.

### 3.1 One bad glyph destroyed a whole act

PyMuPDF maps a PDF glyph it cannot resolve — typically a list bullet in a symbol
font — to **U+0001**, which is illegal in XML 1.0. `python-docx`/lxml rejects the
*entire document*: `All strings must be XML compatible`. Two acts
(`sc_cosit_337/2014`, `sc_cosit_152/2018`) were lost outright to a handful of
invisible characters.

Fixed with `xml_safe()` applied once to the assembled fragment — the single
choke point every source flows through (segment text, inline HTML annexes, PDF
and ODS conversions alike). The stripped code points carry no textual meaning,
so nothing a reader would see is lost. Regression tests cover each illegal
class and assert the document now builds.

### 3.2 Annex text bypassed normalization

The first complete diff showed legacy ordinal encodings falling only
**277 → 173**, not to ~0. All 173 residuals were inside PDF annexes
(recognizable by their `Fls.` / `CÓPIA` scan markers): normalization was applied
to `textoIntegra` but not to annex-derived HTML, which reaches the fragment
through a different path. The plan had specified both ("applied to every
`textoIntegra` **and to text extracted from annexes**"); the implementation had
covered only the first.

Fixed by normalizing the converted annex fragment too — and annexes turn out to
be *richer* in legacy encodings than the segment text, being scans of the same-era
typescript (`Art. 3°, §§ 1° e 4°`). After the fix the count is **277 → 1**.

That last one is not a miss but a **confirmation**: in `sc_cosit_200_20211214`
the `.txt` reads `… pelo banco. No` / `1` / `Solução de Consulta … Fls. 3` /
`entanto, informa que …`. The `No` is the preposition in "**No** entanto"
("However"), separated from its own sentence by a PDF page-break footer. Within
its own block there is no digit after it, so the digit look-ahead correctly
declined to rewrite it — exactly the discrimination §1.1 relies on. The
diff tool's detector, which scans the joined text, is the thing producing the
false positive.

---

## 4. Results

### 4.1 Fetch

**245 / 278 acts (88.13 %)** — identical to the baseline, so the rendering work
cost no coverage. The 33 `needs_review` cases are the same genuine portal
boundaries analysed in the previous log (undated PGFN/SEI references, 1970s
`parecer_normativo_cst` whose number+date the portal does not index).

View resolution: **234 acts on `vigente`**, **11 on `original`** (acts whose
`exibirVisoes` is `1000` — only the original exists), **0 on `multivigente`**.
Every fallback is visible in the fetch report.

### 4.2 Before / after (`compare_receita_corpus.py`)

| Measure | Before | After |
|---|--:|--:|
| Acts | 245 | 245 |
| Characters | 2 871 261 | **6 221 814** (+117 %) |
| Word tables | **0** | **778** |
| Acts containing a table | **0** | **73** |
| Amendment/revocation annotations | 0 | **1 499** (36 acts) |
| Superseded segments correctly dropped | 0 | **551** (25 acts) |
| Wholly-revoked acts flagged with a banner | 0 | **9** |
| Attachments retrieved | 0 | **254** |
| Legacy ordinal encodings | 277 | **1** (a detector false positive — §3.2) |
| Legacy ordinal encodings | 277 | **1** (a false positive — §3.2) |
| Struck runs (invariant: must be 0) | 0 | **0** |
| **Acts losing text unexplained** | — | **0** |

Largest gains are exactly the acts the plan predicted: `in_rfb_1911` (+155 720
chars, 133 tables), `resol_cgsn_140` (+141 086, 98 tables, 450 annotations),
`in_rfb_1500` (+56 847, 45 tables, 255 annotations).

The **only** act that shrank materially is the reference defect case,
`in_srf_84_20011011` (−154 chars) — precisely as intended: the revoked
provision's wording was replaced by its stub plus a revocation notice, and the
flattened pseudo-table by a real one.

### 4.3 The reference act, `IN SRF nº 84/2001`

| | before | after |
|---|--:|--:|
| docx paragraphs | 207 | 212 |
| docx tables | **0** | **1** (7 × 8) |
| bare `[1-9]o` ordinals in `.txt` | 64 | **0** |
| revoked wording `alienação … R$ 20.000,00` present | **yes** | **no** |
| `Revogado(a) pelo(a) IN SRF nº 599` annotation | absent | **present** |
| struck runs | 0 | 0 |

### 4.4 Residual limitations

* **5 attachments unconverted** (of 254): 3 legacy `.doc` (OLE) annexes with no
  in-process converter available, plus 2 zero-content placeholders the portal
  itself ships (a 3-byte file literally named `vazio.htm`). All are downloaded
  and stored under `documents/attachments/`, and the portal's flattened text is
  kept, so nothing regresses to nothing.
* **PDF table extraction is heuristic.** It is strong on the ruled tables this
  corpus uses; the raw PDF is always retained so any act can be re-examined.

---

## 5. Testing

* **148 offline tests pass** (was 97): 51 new in `tests/test_receita_rendering.py`,
  fixture-driven, no network. Coverage follows the plan's list 1–8 plus the two
  bugs above:
  ordinal rewrites (10 real corpus strings) and negatives (the `No caso de`
  preposition, `R$ 20.000,00`, `art. 10`, years); `<strike>` unwrapping and the
  **global no-strike invariant** across four real acts; the inline `tabela.htm`
  producing a 7×8 Word table with the flattened duplicate gone; the revoked stub
  plus its annotation as its own block; the **amendment pair asserted in both
  views**, so the inverted-`omitir` bug is pinned from both sides; act-level
  revocation banner; future-dated segment; `multivigente` fallback stripping
  `tachado`; PDF and ODS conversion; `.txt` table rendering and `<br>`
  preservation; the `/anexo/` URL shape, same-site headers, disk cache and raw
  persistence; and that the saved `.json` stays a **lossless** mirror while the
  `.txt` is normalized.
* **Submodule:** 69/69 tests pass; the decreto fixture still renders correctly
  (and its `DECRETO No 361` is *not* normalized — normalization is Receita-side
  only, as designed).
* **Live:** four full corpus runs; the final one is the corpus on disk.

## 6. How to run

```bash
python fetch_receita_normas_main.py                        # whole registry, vigente
python fetch_receita_normas_main.py --view original        # pin a view (no fallback)
python fetch_receita_normas_main.py --also-save-original   # keep as-published too
python fetch_receita_normas_main.py --no-attachments       # skip annex downloads
python receita_text_normalize.py --audit-ordinals          # every rewrite, with context
python compare_receita_corpus.py --baseline <snapshot>     # before/after diff
python -m pytest tests/ -q
```

## 7. Open items

* **The corpus changed legal meaning.** It is now the text *in force as of the
  fetch date*, not as published. Any downstream index, embedding or QA pair built
  on the previous corpus must be **rebuilt, not patched**. `_fetched_at` is
  stamped in every `.json` and every report row; `--also-save-original` recovers
  the as-published text.
* **`vigente` is a moving target** — a later fetch may legitimately differ. For a
  fixed reference point the API also exposes a point-in-time `data` view, not
  wired up here.
* **Legacy `.doc` annexes (3 acts)** need LibreOffice to convert.
* **Out of scope, worth a separate look:** the decreto pipeline drops planalto's
  genuine `<strike>` revocation marks (all 44 decreto `.docx` contain zero struck
  runs). The builder now has the recursion needed to support it; only the
  decreto-side decision is missing.
* Unchanged from the previous log: undated PGFN/SEI references (18), 1970s
  `parecer_normativo_cst` (≈9), `parecer_sei`/`parecer_pgfncat` (6),
  `matched_without_date` (3).
