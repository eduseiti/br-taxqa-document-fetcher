# Plan: rendering fidelity of the Receita Federal acts (ordinals, tables, amendment annotations, annexes)

Date: 2026-07-29
Scope: `receita_norma_fetcher.py` (segment → HTML → txt/docx pipeline) and the
`WordDocumentBuilder` it borrows from `br_legal_parser`. Reference defect report:
`IN SRF nº 84, de 11 de outubro de 2001`
(`output_receita_federal/instrucao_normativa_srf/documents/in_srf_84_20011011.*`,
`idAto=14400`). Follows up on `20260718_113911_receita_federal_all_acts_implementation.md`.

---

## 0. Executive summary

All four reported defects are real and all four are **corpus-wide**, not specific
to IN SRF 84. Live probing of the portal API established that the data needed to
fix every one of them **is already available** and is simply not being requested
or not being rendered:

| # | Reported issue | Root cause | Data source for the fix |
|---|---|---|---|
| 1 | Ordinal shown as lower-case `o` (`§ 1o`) | Source text really carries `o`/`No`/`°`; a second, *different* encoding (`N<strike>º</strike>`) also exists — 366 occurrences that any naive strike handling would turn into struck-through ordinals | Text normalization + `<strike>`-unwrapping rule |
| 2 | Art. 26 table flattened | The real table is **not** in `textoIntegra` — it is a base64 `tabela.htm` in `segmento.arquivoBinario`, which the pipeline ignores; `_segments_html` wraps everything in `<p>`, so even a `<table>` could not reach `_add_table` | `arquivoBinario.arquivoBinario` (inline base64 HTML) |
| 3 | Amendment/revocation annotations absent | The fetcher persists the **`original`** view, which has no `ancorasDestino` at all — and whose `omitir` mask is *inverted*, so we publish superseded wording and drop the current wording | render the **`vigente`** view exactly as the portal does: keep `omitir === false` segments, emit `ancorasDestino[].texto` as annotations, no strikethrough |
| 4 | Annex tables flattened | Same as #2, plus: annex binaries are **not inlined** — they must be pulled from an undocumented endpoint. **268 PDF annexes across 143 acts are currently missing entirely** (their `textoIntegra` is empty) | `GET /api/consulta-externa/ato/{idAto}/anexo/{idArquivoBinario}` (discovered live) |

Issue #4 is worse than reported: it is not only a formatting loss, it is a
**content loss** affecting 143 of 245 fetched acts.

A note on the premise of issue #2: the original is **not** tab-formatted. Across
all 245 acts there is exactly **one** tab character in `textoIntegra`. The
flattening comes from the portal's own plain-text rendition of an attached
HTML/Word/PDF table, which is what we are currently saving.

---

## 1. Evidence gathered (all verified live / against the saved corpus)

### 1.1 The segment model has three channels we ignore

For `idAto=14400`, segment `834855` (`idTipoSegmento=16`, *anexo*):

```
textoIntegra    = 'ANO DE % DE ANO DE % DE AQUISIÇÃO REDUÇÃO ... Até 1969 100% 1974 75% ...'
arquivoBinario  = {idArquivoBinario: 19358, idTipoArquivo: 4,
                   nomeArquivoBinario: 'tabela.htm',
                   arquivoBinario: '<base64 of a 14 679-byte Word-exported HTML>'}
```

Decoding that base64 yields a well-formed `<table>` with 7 rows × 8 columns,
including the caption row `PERCENTUAIS DE REDUÇÃO DO GANHO DE CAPITAL NA
ALIENAÇÃO DE BEM IMÓVEL`. The flattened `textoIntegra` is the portal's own
degraded fallback — exactly what ends up in our `.txt`/`.docx` today.

Attachment inventory over the 245 saved acts (307 attachment-bearing segments,
**151 acts**):

| `idTipoArquivo` | kind | count | inline base64? |
|---|---|--:|---|
| 6 | `.pdf` | 268 | **no** (`arquivoBinario: null`) |
| 5 | `.html` | 19 | yes |
| 4 | `.htm` | 11 | yes |
| 2 | `.jpg` | 5 | yes |
| 7 | `.doc` | 3 | **no** |
| 17 | `.ods` | 1 | **no** |

The non-inlined ones are retrievable — endpoint found by probing:

```
GET https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{idAto}/anexo/{idArquivoBinario}
     (same-site Referer/Origin required, as with the /visao/ endpoint)
-> 200 application/octet-stream, verified for .doc (199 680 B, OLE),
   .pdf (25 408 B, %PDF-1.4) and .ods (59 689 B, ZIP)
```

All sibling paths tried (`/arquivo-binario/`, `/arquivo/`, `/segmento/{id}/arquivo`,
…) return 403; `/anexo/{id}` is the one that works.

**PDF-attachment segments carry `textoIntegra = ''`** — so those annexes are
absent from our output altogether, not merely unformatted.

### 1.2 The view we persist is the wrong one

`exibirVisoes` / the 406-fallback chain expose four views. The API always returns
the **same segment list** in every view; what changes is the per-segment flags:

| act | view | segs | `omitir` | `tachado` | `compilado=False` | `ancorasDestino` |
|---|---|--:|--:|--:|--:|--:|
| IN SRF 84 (14400) | `original` (**saved today**) | 205 | 0 | 0 | 6 | 0 |
| | `vigente` | 205 | 0 | 0 | 6 | **6** |
| | `multivigente` | 205 | 0 | **6** | 6 | 6 |
| IN SRF 208 (15079) | `original` | 322 | 48 | 0 | 59 | 0 |
| | `vigente` | 322 | **20** | 0 | 59 | **77** |
| | `multivigente` | 322 | 0 | **59** | 59 | 83 |
| Resol. CGSN 140 (92278) | `original` | 1800 | 376 | 0 | 228 | 0 |
| | `vigente` | 1800 | **155** | 0 | 228 | **385** |
| | `multivigente` | 1800 | 0 | **215** | 228 | 442 |

Reading of the flags, confirmed segment by segment:

* **`omitir`** is the view's own "do not render" mask. In `vigente` it marks
  exactly the **superseded wording** — an old version of an `idSegmento` that a
  later act replaced. Honoring it is what keeps outdated text out.
* **`ancorasDestino[].texto`** is the annotation ("Redação dada pelo(a) …",
  "Revogado(a) pelo(a) …", "Incluído(a) pelo(a) …", "Suprimido(a) - vide …") and
  its `href`/`idAto` is the amending act. Present from `vigente` on.
* **`tachado`** is the strikethrough flag and is set **only** in `multivigente`,
  whose purpose is to show every version side by side. It is **not used** here.

`vigente` is therefore self-sufficient, and the target behavior is simply "render
what the portal renders". That is not an inference — it is the portal's own
Angular component (`default-src_app_atos_atos_module_ts.js`, deobfuscated):

```js
this.segmentos = Array.isArray(this.visaoAto.outrosSegmentos)
    ? this.visaoAto.outrosSegmentos.filter(seg => seg.omitir === false) : [];
...
if (segmento.tachado) { classes = classes + ' tachado'; }
if (segmento.agendado) { classes = classes + ' agendado'; }
```
```css
.segmento .tachado { text-decoration-line: line-through; }
```

So: every non-`omitir` segment is rendered, in every view; strikethrough is driven
**solely** by `tachado`; and since `vigente` never sets `tachado`, the `vigente`
page contains **no struck text at all** — only the current wording plus the
annotations. `compilado`, despite its name, is used only for editor colouring
(`classeEditor`), never for visibility.

The same component also settles the attachment question of issues #2/#4:

```js
ɵɵproperty("ngIf", (segmento.idTipoSegmento !== 16 || !segmento.arquivoBinario) && !segmento.omitir);  // textoIntegra
ɵɵproperty("ngIf", segmento.arquivoBinario && !visaoSelecionada.isAnotacao() && !segmento.omitir);      // the attachment
...
if ([4, 5].indexOf(segmento.arquivoBinario?.idTipoArquivo) >= 0) { /* render as HTML */ }
```

When an *anexo* segment (`idTipoSegmento === 16`) carries a binary, the portal
renders the **attachment** and suppresses `textoIntegra` entirely — confirming
that the flattened text we currently save is a fallback that should be dropped in
favour of the real table (WP2).

The view difference covers **amendments** as well as revocations. `IN SRF
nº 208/2002` (`idAto=15079`), segment `815178`:

```
original      v1 omitir=False  "1. para trabalhar com vínculo empregatício, na data da chegada;"
              v2 omitir=True   "1. ... ou atuar como médico bolsista no âmbito do Programa Mais Médicos ..."
vigente       v1 omitir=True   (dropped)
              v2 omitir=False  + ancorasDestino "[Redação dada pelo(a) Instrução Normativa RFB nº 1383, de 7 de agosto de 2013]"
```

The `omitir` mask is **inverted between views**, which is why the current output
is wrong in the worst possible way: `_segments_html` drops `omitir` segments, so
against the `original` view we are today publishing the **superseded** wording
and discarding the current one. `vigente` gives exactly the opposite — and
exactly what is wanted. Corpus impact: **25 acts** have `omitir` segments (up to
376 in `Resolução CGSN nº 140/2018`).

#### 1.2.1 `vigente` blanks revoked provisions server-side

`omitir` is only half the mechanism. For a provision revoked **outright** there is
no replacement version to mask, so the API instead returns the segment
**truncated to its label**. Segment `455831` across the three views:

```
original      "II - alienação de bens ou direitos por valor igual ou inferior a R$ 20.000,00 (vinte mil reais);"
vigente       "II -"                    + ancorasDestino "[Revogado(a) pelo(a) IN SRF nº 599, de 28/12/2005]"
multivigente  "II - alienação de ..."   + tachado=true + the same annotation
```

The numbering skeleton is kept so the article stays readable; the wording is
gone. Measured across the four acts with the most amendment activity — for every
segment that `multivigente` strikes, what does `vigente` do?

| act | struck in `multivigente` | `omitir`-ed in `vigente` | truncated to stub | full text kept |
|---|--:|--:|--:|--:|
| IN SRF 84 (14400) | 6 | 0 | **6** | 0 |
| IN SRF 208 (15079) | 59 | 20 | **39** | 0 |
| Resol. CGSN 140 (92278) | 215 | 155 | **60** | 0 |
| IN RFB 1548 (61197) | 303 | 46 | 11 | **246** |

So `vigente` never carries superseded or individually-revoked wording: it is
either omitted or blanked. The 246 exceptions in `IN RFB 1548` are the
**whole-act** revocation — no provision was individually revoked, so the body
stays intact and the notice lives in the document header (below). This is what
makes the WP4 rendering rule sufficient on its own.

Two document-level signals are worth carrying over even though nothing is struck:

* **Whole-act revocation** is not a segment flag at all. `IN RFB 1548` reports it
  in the document header — `vigente: false` plus
  `ancorasNoAto: ["[Revogado(a) pelo(a) Instrução Normativa RFB nº 2172, de 9 de
  janeiro de 2024]"]`. Without it, a fully revoked act reads as if in force.
* **Future-dated provisions** exist (`agendado` / `compilado=False` with empty
  `textoIntegra`, e.g. 13 in `Resolução CGSN 140` carrying `[Incluído(a) pelo(a)
  Resolução CGSN nº 189, de 23 de abril de 2026]`). They render as an annotation
  with no text, which is correct and needs no special handling.

### 1.3 `<strike>` in this corpus never means "revoked"

732 tag occurrences were counted in `textoIntegra`; grouping by inner content:

```
<strike>º</strike>  ->  366 occurrences (100 %), across 8 acts
```

It is the portal's typographic hack for the ordinal indicator's underline. Any
naive "honor `<strike>`" rule would render every ordinal in `in_rfb_1704` (124 of
them), `in_rfb_1627` (91), `in_rfb_1548` (78) and `in_srf_81` (50) as
struck-through. Since the target rendering has **no strikethrough anywhere**
(§1.2), the rule is simply: `<strike>` wrapping an ordinal character is unwrapped
to that character, and any other `<strike>` content is unwrapped to plain text.

Other inline markup present: `<br>` ×1699 (currently collapsed into a space by
`_collapse_ws`, e.g. `"ANEXO ÚNICO \n<br>\n Tabela de Atualização"` → one line),
`<a href>` ×450 (links to planalto/portal, currently reduced to bare text),
`<strong>` ×6, `<span>` ×2.

### 1.4 Ordinal-encoding survey over the 245 `.txt` files

| pattern | occurrences | files | action |
|---|--:|--:|---|
| `No`/`Nos` + **digit** (`Lei No 9.250`) | 76 | 17 | → `nº` |
| `No` + **word** (`No caso de…` — the preposition) | 268 | 52 | **must not be touched** |
| bare digit + `o` (`art. 1o`, `§ 3o`) | 151 | 18 | → `1º` |
| `°` degree sign (`3°`) | 48 | 8 | → `º` |
| bare digit + `a` (`2a`) | 2 | 1 | → `ª` (verify by hand) |

Every bare `<digit>o` in the corpus is **single-digit 1–9** (counts: 1→39, 2→30,
3→24, 4→16, 5→14, 6→12, 8→9, 9→5, 7→4), which matches Brazilian legal usage
(ordinal indicator only up to 9º). That makes `\b[1-9]o\b` a safe, complete rule
and removes any risk of mangling years, monetary values or `art. 10`.

### 1.5 The docx builder can already do most of the work

`br_legal_parser/legal_document_fetcher.py::WordDocumentBuilder`:

* `_add_table` (line 510) already builds real Word tables with rowspan/colspan
  merging and a `Light Grid Accent 1` style — it is simply **never reached**,
  because `_segments_html` emits `<p>{textoIntegra}</p>` for every segment and
  `add_html_content` only dispatches `table` at the **top level** of the soup.
* `_add_formatted_text` handles `b/strong`, `i/em`, `u` and falls through to
  plain text for everything else — notably no `br` (so `<br>`-separated lines
  collapse) and no nesting. Its lack of `strike`/`s`/`del` handling happens to
  match what we want here (§1.3), though it silently loses planalto's real
  strikethrough in the decreto pipeline (§5).
* `_add_image` handles `data:` URIs only — usable for the 5 inline JPEGs after
  we convert them to data URIs.

Confirmed on the current artifact: `in_srf_84_20011011.docx` has **207
paragraphs and 0 tables**; the Art. 26 table is paragraph 133 and the annex
table is paragraph 206.

### 1.6 Tooling available for annex conversion

`pymupdf 1.28.0` **is installed** and its `page.find_tables()` extracts the
annex tables cleanly — verified on `in_rfb_1500`'s `Anexo I.pdf`:

```
tables found: 1
['Ano-calendário', 'Valores isentos mensais (em R$)']
['2010', 'até 1.499,15']
['2011, até o mês de março', 'até 1.499,15']
```

`python-docx 1.2.0`, `lxml 6.1.1`, `beautifulsoup4 4.15.0` are present.
**Not** available: LibreOffice/`soffice`, `pandoc`, `antiword`, `mammoth` — so
the 3 legacy `.doc` (OLE) annexes have no in-process converter today.

---

## 2. Design of the fix

Five work packages. WP1–WP3 are pure rendering (no re-fetch needed to *develop*,
since the saved `.json` files are lossless inputs); WP4 changes what we fetch.

### WP1 — Ordinal / typography normalization (`issue 1`)

New module `receita_text_normalize.py`, applied to every `textoIntegra` (and to
text extracted from annexes) at the moment the HTML fragment is built — never to
the saved `.json`, which stays a lossless mirror of the API.

Ordered rules, each anchored so it cannot fire in prose:

1. `<strike>º</strike>` → `º` (all 366 corpus occurrences). Any other `<strike>`
   content is unwrapped to plain text and logged, so a future non-ordinal use
   surfaces in the report instead of silently becoming struck output.
2. `(?<![\w.])([1-9])o\b` → `\1º`, and `(?<![\w.])([1-9])a\b` → `\1ª`, but only
   when preceded within ~30 chars by an ordinal-bearing context token
   (`art`, `artigo`, `§`, `parágrafo`, `inciso`, `nº`, `n`, `no`, `de` for
   `1o de janeiro`) — measured against the corpus so all 151 hits are covered.
3. `\bN(o|os|O|OS)\.?(?=\s*\d)` → `nº`/`nos` (digit look-ahead is what separates
   `Lei No 9.250` from the 268 `No caso de …`).
4. `(?<=\d)\s*°` → `º`.

Deliverable: a `--audit-ordinals` mode that prints every rewrite with 40 chars of
context, so all ~277 corpus rewrites can be eyeballed once before adoption, and a
golden-file test built from the real contexts collected in §1.4.

### WP2 — Structured HTML assembly (`issues 2, 3, 4`)

Rewrite `ReceitaNormaFetcher._segments_html` so it emits **block-level siblings**
instead of a flat `<p>` list:

* text segment → `<p>` (normalized, `<br>` preserved, `<a>` preserved);
* segment with an HTML attachment → decode/download, extract the `<table>`
  elements and emit them **as top-level `<table>`**, dropping the redundant
  flattened `textoIntegra`; keep any non-table prose from the attachment;
* segment with a PDF/ODS/DOC attachment → §WP3;
* segment with a JPEG attachment → `<img src="data:image/jpeg;base64,…">`;
* `omitir === false` → rendered, everything else skipped — the portal's own rule
  (§1.2), now applied against the **`vigente`** mask, so the segment dropped is
  the superseded one rather than the current one;
* `ancorasDestino[].texto` → append as a trailing `<p class="anotacao"><i>[…]</i></p>`
  right after its segment, carrying the amending/revoking act (and its `idAto`);
* act-level revocation (`vigente: false` / `ancorasNoAto`) → one banner paragraph
  under the épigrafe;
* **no strikethrough is emitted anywhere** — no `<s>`/`<del>` in the fragment, and
  `tachado` is never consulted.

`WordDocumentBuilder` changes (in the `br_legal_parser` submodule — bump the
submodule, as previously done for the decreto docx fixes):

* `_add_formatted_text`: handle `br` → `run.add_break()`; handle `a` → keep text
  (optionally hyperlink); recurse into nested inline tags instead of
  `get_text()`-flattening them. `s`/`strike`/`del` are **unwrapped to plain text**
  — never `run.font.strike` — since no struck text is wanted in the output and
  the only `<strike>` in this corpus is the ordinal hack (§1.3).
* `add_html_content`: recurse into `p` when it contains block children, so a
  wrapper can never swallow a table again.
* `_add_table`: keep cell text formatted (currently `cell.get_text(strip=True)`)
  and mark header rows bold; add `autofit`.
* small guard: `_collapse_ws` must not eat `<br>`-derived breaks.

`reconstruct_text` must stop being `find_all('p')`: walk the fragment in document
order and render tables as pipe-delimited rows (one line per row), with
annotations on their own line. Otherwise the `.txt` — which is the artifact most
likely to feed the RAG evaluation — keeps losing every table.

### WP3 — Annex retrieval and conversion (`issue 4`)

New `receita_attachments.py`:

* `fetch_attachment(session, id_ato, id_arquivo)` → bytes, via
  `/api/consulta-externa/ato/{idAto}/anexo/{idArquivoBinario}` with the same-site
  headers, rate-limited like the other calls, cached on disk.
* Always persist the raw bytes to
  `output_receita_federal/<type_slug>/documents/attachments/<stem>__<idArquivo>_<nome>`
  so nothing is lost regardless of conversion success, and record them in the
  fetch report.
* Converters by `idTipoArquivo`:
  * `4`/`5` (htm/html) — parse with bs4, emit `<table>` verbatim. Already proven.
  * `6` (pdf) — PyMuPDF: `find_tables()` per page → `<table>`; non-table text →
    `<p>`; if a page yields neither (scanned image), render the page to PNG and
    embed as an image so nothing disappears.
  * `17` (ods) — `zipfile` + `content.xml` (`table:table-row`/`table-cell`,
    honoring `number-columns-repeated`) → `<table>`. One file; stdlib only.
  * `7` (doc, OLE) — no in-process converter available. Use LibreOffice
    (`soffice --headless --convert-to html`) **if present**; otherwise fall back
    to the portal's flattened `textoIntegra` and flag the act
    `attachment_not_converted` in `needs_review.json`. Only 3 acts.
  * `2` (jpg) — inline as a data URI.

### WP4 — Persist and render the `vigente` view (`issue 3`)

**Goal: the output is the currently in-force text plus the amendment/revocation
annotations, and nothing else — no superseded wording, no strikethrough.** This
is byte-for-byte the portal's `vigente` rendering (§1.2), so one view, one GET
per act, no overlay and no cross-view joins:

* `DEFAULT_VIEW_CHAIN` → `("vigente", "multivigente", "original")`, keeping the
  existing 406 fallback. `verify()` reads `epigrafe`, which is view-invariant, so
  matching/republication logic is untouched.
* Render rule, mirroring the component: keep segments with `omitir === false`;
  emit `ancorasDestino[].texto` as an annotation line after each segment; ignore
  `tachado` and `compilado` entirely.
* Net effect per class of change:

  | situation | what the output contains |
  |---|---|
  | wording replaced (`Redação dada pelo(a) …`) | **current** wording only + the annotation naming the amending act |
  | provision revoked / suppressed | the **label stub only** (`II -`, `§ 2º`) + the annotation (`Revogado(a) pelo(a) …` / `Suprimido(a) - vide …`) — the wording is blanked by the API itself (§1.2.1) |
  | provision added later (`Incluído(a) pelo(a) …`) | the text + the annotation |
  | future-dated provision | the annotation, with the (empty) text |
  | whole act revoked | full body (nothing was individually revoked) + a banner under the épigrafe from `ancorasNoAto` |

* If the fallback fires and an act resolves to `multivigente` (only where
  `vigente` is unavailable), strip `tachado` segments at render time so that act
  does not become the one document with struck text.
* Record `exibirVisoes` (observed `1111` ×228, `1000` ×11, `1110` ×5, `0010` ×1),
  the resolved `_view`, and the counts of omitted / annotated segments in the
  fetch report, so any act that fell back is visible.
* Add `--view` to `fetch_receita_normas_main.py` for reproducibility, plus
  `--also-save-original` for anyone wanting the as-published text as a second
  `.json` (one extra GET per act, off by default).

### WP5 — Re-run, diff and report

* Re-fetch all 31 types (245 acts ≈ 245 × ~3 requests + ~307 annex downloads —
  well within the existing 1.5 s pacing; budget ~40 min).
* Produce a before/after diff report: per act, Δ paragraphs, Δ tables, Δ
  characters, number of annotations, annexes recovered, and — for the 25 acts
  with `omitir` segments — which passages were swapped for their current wording.
  Any act that **loses** text without a matching `omitir`/annex explanation is a
  regression to investigate.
* Update `CLAUDE.md` (view chain, attachment endpoint, `attachments/` folder,
  normalization) and write the usual `YYYYMMDD_HHMMSS_*_implementation.md` log.

---

## 3. Corpus-wide impact (why none of this is IN-SRF-84-specific)

| defect | acts affected (of 245) | how measured |
|---|--:|---|
| Missing/flattened attachments | **151** (143 with non-inlined ones) | segments with `arquivoBinario` |
| PDF annexes lost entirely (empty `textoIntegra`) | **143** | 268 pdf attachments |
| Wrong wording published + annotations missing | **25** (`omitir`) / **all 245** (annotations) | inverted `omitir` mask; `ancorasDestino` absent from `original` |
| Ordinal `o`/`No`/`°` | **~40** (18 + 17 + 8, overlapping) | §1.4 |
| `<strike>º</strike>` mis-render risk | **8** | 366 occurrences |

The same rendering path is used by every act type in the registry, so all 31
kinds benefit; `resolucao_cgsn_140` (1800 segments, 376 `omitir`) is the largest
single beneficiary.

---

## 4. Testing

Offline, fixture-driven — extend `tests/test_instrucao_normativa_fetching.py`
and add `tests/test_receita_rendering.py`:

1. **Ordinals** — parametrized table of real corpus strings, including the 268
   `No caso de…` negatives and `R$ 20.000,00`, `art. 10`, `1994` non-matches.
2. **`<strike>º</strike>`** — renders as `º` with `run.font.strike is not True`;
   a synthetic `<strike>texto qualquer</strike>` renders as plain text, also
   unstruck, and is logged.
3. **Inline HTML table** — fixture = the real base64 `tabela.htm` from segment
   `834855`; assert the produced `Document` has ≥1 table, 7×8, with
   `Até 1969`/`100%` in the right cells, and that the flattened duplicate
   paragraph is gone.
4. **Revocation annotation** — fixture trimmed from `14400/visao/vigente`;
   assert segment 455831 renders as the stub `II -` (i.e. the revoked wording
   `alienação de bens ou direitos … R$ 20.000,00` appears **nowhere** in the
   `.txt`), that the following paragraph contains `Revogado(a) pelo(a) Instrução
   Normativa SRF nº 599`, and that **no run in the whole document** has
   `font.strike is True` (the global no-strike invariant).
5. **Amendment pair** — fixture from `15079` segment `815178` (`vigente`); assert
   the superseded v1 (`omitir=True`) is **absent**, v2 present and annotated
   `Redação dada pelo(a) …`. Add the mirror-image assertion on the `original`
   fixture to lock in the inverted-`omitir` bug that this replaces.
5b. **Document-level cases** — an act-level revocation (`IN RFB 1548`,
   `vigente: false` + `ancorasNoAto`) produces exactly one banner under the
   épigrafe; a future-dated segment (`CGSN 140` / `Resolução CGSN nº 189/2026`)
   yields its annotation with empty text; a `multivigente` fallback act has its
   `tachado` segments stripped rather than struck.
6. **PDF annex** — commit the 25 KB `Anexo I.pdf` fixture; assert a 2-column
   table with `Ano-calendário` header.
7. **`.txt` reconstruction** — tables appear as pipe-delimited rows; annotations
   on their own line; no content silently dropped.
8. **Attachment endpoint** — mocked `requests` session; assert URL shape,
   headers, and that raw bytes land in `attachments/`.

Live smoke test after WP4: `--only instrucao_normativa_srf --limit 3`, then a
manual read of `in_srf_84_20011011.docx` against
`normas.receita.fazenda.gov.br/sijut2consulta/link.action?idAto=14400`.

---

## 5. Risks and decisions

* **The view switch changes every output file — including its legal meaning.**
  Today's `.txt`/`.docx` are the *as-published* text (and, for 25 acts, the wrong
  version of it); after the change they are the *currently in-force* text plus
  amendment annotations. Any downstream index, embedding or QA pair built on the
  current corpus must be rebuilt, not patched. Mitigation: `--view`, the optional
  `--also-save-original`, and the before/after diff report in WP5.
* **`vigente` is a moving target.** It reflects the law as of the fetch date, so
  the corpus is only reproducible if the fetch date is recorded. Mitigation:
  stamp `_fetched_at` and the act's `dataVigenciaInicio` into every `.json` and
  into the fetch report; the API also exposes a `data` view for point-in-time
  queries if a fixed reference date is ever needed.
* **No residual revoked text — the API guarantees it** (§1.2.1). `vigente` blanks
  individually revoked provisions to their label stub server-side, so there is no
  "keep it or drop it" decision left to make in the renderer. The only case where
  a fully-worded body survives alongside a revocation notice is a **wholly**
  revoked act, where the notice is the act-level banner; that is the portal's own
  presentation and is correct.
* **PDF table extraction is heuristic.** PyMuPDF's `find_tables()` is good on
  ruled tables (as in the verified sample) and weaker on whitespace-aligned ones.
  Mitigation: always keep the raw PDF in `attachments/`, count extracted tables
  per act in the report, and flag acts where a PDF produced neither table nor
  text.
* **Legacy `.doc` annexes (3 acts)** cannot be converted without LibreOffice.
  They will be downloaded, stored and flagged; the flattened portal text is kept
  so no content regresses.
* **Ordinal rewriting mutates source text.** Confined to the `.txt`/`.docx`
  renditions; the `.json` stays byte-faithful to the API, so any rule can be
  revisited without re-fetching.
* **Submodule coupling — `<strike>` means opposite things in the two sources.**
  `WordDocumentBuilder` is shared with the lei/decreto pipelines, and planalto
  *does* use `<strike>` for genuine strikethrough: `D3000.htm` (RIR/1999) carries
  **5 804** `<strike>` tags marking revoked provisions. In the Receita corpus the
  same tag is only the ordinal hack. So the unwrapping rule must live
  **Receita-side** (in `_segments_html`), never in the shared builder. The
  builder changes (`<br>`, nested inline, block recursion, richer table cells)
  are additive; re-run `tests/` for the lei/decreto pipelines before bumping the
  submodule.
  *Observed in passing, out of scope:* the shared builder has no `strike`
  handling at all, so all 44 decreto `.docx` currently contain **zero** struck
  runs — planalto's revocation marks are being dropped there too. Worth a
  separate look after this work.

---

## 6. Task list

- [ ] **T1** `receita_text_normalize.py` + `--audit-ordinals` + tests (WP1)
- [ ] **T2** `receita_attachments.py`: `/anexo/` client, disk cache, raw
      persistence (WP3a)
- [ ] **T3** converters: html/htm, pdf (PyMuPDF), ods, jpg, doc-fallback (WP3b)
- [ ] **T4** rewrite `_segments_html` → structured fragment (annotations,
      `<strike>` unwrapping, no strike emitted); `reconstruct_text` →
      document-order walker with table rendering (WP2a)
- [ ] **T5** `WordDocumentBuilder`: `br` / `a` / nested inline / block recursion /
      richer table cells; bump submodule (WP2b)
- [ ] **T6** view chain → `vigente`; annotation rendering; act-level-revocation
      banner; `tachado`-strip guard on the `multivigente` fallback; `--view`,
      `--also-save-original`; `_fetched_at` + report fields (WP4)
- [ ] **T7** tests 1–8 + fixtures (`tabela.htm`, `14400/vigente` trimmed,
      `15079` segment pair in `vigente` **and** `original`, `CGSN 140`
      future-dated segment, `IN RFB 1548` header, `Anexo I.pdf`)
- [ ] **T8** full re-run + before/after diff report + regression check on lei /
      decreto pipelines
- [ ] **T9** `CLAUDE.md` update + implementation log

Suggested order: T1 → T4/T5 (unblocks visual verification against saved JSON) →
T2/T3 → T6 → T7 → T8 → T9.
