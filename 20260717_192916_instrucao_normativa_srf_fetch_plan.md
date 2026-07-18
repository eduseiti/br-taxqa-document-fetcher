# Plan: Fetch "Instrução Normativa SRF" documents from normas.receita.fazenda.gov.br

Date: 2026-07-17

## 0. TL;DR — Is programmatic download possible?

**Yes, and without a browser / Selenium.** The Receita Federal norms portal
(`sijut2consulta`) is a server-rendered Struts app whose search form submits via
**GET**, and the document content is served by a **public JSON REST API** on a
companion host. Both stages are reachable with plain `requests`. This is
substantially simpler than the Selenium/Shadow-DOM path used for
`normas.leg.br` (`lei`, `decreto_lei`).

The two stages:

1. **Search** → `GET https://normas.receita.fazenda.gov.br/sijut2consulta/consulta.action`
   with the full form field set → server-rendered HTML listing → scrape the
   internal act id (`idAto`).
2. **Fetch content** → `GET https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{idAto}/visao/original`
   → JSON containing the épigrafe (type/number/date/órgão for verification), the
   ementa, and the full text as an ordered list of segments.

All of the following was verified live against IN SRF nº 107/1988 (`idAto=14681`).

---

## 1. Reverse-engineering findings (verified)

### 1.1 Search form (`consulta.action`)

- `<form id="frmPesquisa" method="get" action="consulta.action">`.
- A first `GET consulta.action` sets a `JSESSIONID` cookie (path
  `/sijut2consulta`); reuse it on the search request.
- The search returns **empty body (HTTP 200, Content-Length 0)** unless the
  **entire** field set is submitted. Sending only `numero_ato/ano_ato/tipo`
  silently yields nothing. A browser `User-Agent` + `Referer` header are also
  advisable.

Full field set submitted (mostly hidden, most left empty):

| field | value used |
|---|---|
| `facetsExistentes` | `` (empty) |
| `orgaosSelecionados` | `` (empty) |
| `tiposAtosSelecionados` | `42` ← **Instrução Normativa** |
| `lblTiposAtosSelecionados` | `Instrução Normativa` |
| `ordemColuna` / `ordemDirecao` | `` (empty) |
| `tipoConsulta` | `formulario` |
| `tipoAtoFacet` / `siglaOrgaoFacet` / `anoAtoFacet` | `` (empty) |
| `termoBusca` | `` (empty) |
| `numero_ato` | e.g. `107` |
| `tipoData` | `1` = data **do ato** (act date); `2` = **publicação** (default in page) |
| `ano_ato` | e.g. `1988` |
| `p` | `1` (page number) |

Type-code discovery: the "Tipo do ato" checkboxes carry `value=` codes. Relevant:
**Instrução Normativa = `42`**, Instrução Normativa Conjunta = `79`. (The full
map is inline in the page if other types are needed later.)

Result rows contain links of the form `link.action?idAto=NNNN` (and an
`?antigo=1&idAto=NNNN` variant). The facet sidebar shows counts, e.g.
`Instrução Normativa (1)`, useful as a sanity check.

**Important — SRF vs RFB & number collisions:** the search type is only
"Instrução Normativa"; the issuing órgão (SRF vs RFB) is a *separate* facet. The
same number can exist for different years and/or different órgãos (the SRF was
renamed RFB in 2007). The canonical list also contains genuine collisions:
`nº 84` appears twice (1979 and 2001) and `nº 599` appears twice (same date —
a true duplicate). **Therefore the returned `idAto` must always be verified**
against the canonical `(órgão sigla = SRF, number, date)` using the JSON in
stage 2 — never trust a single search hit blindly.

### 1.2 Detail link is a redirect only

`GET .../sijut2consulta/link.action?idAto=14681` returns a tiny HTML page whose
JS does `window.location.replace('https://normasinternet2.receita.fazenda.gov.br/#/consulta/externa/14681')`.
That second host runs an Angular SPA; the SPA calls the REST API below. We skip
the SPA entirely and call the API directly with the `idAto`.

### 1.3 Content REST API (`normasinternet2`)

- Base: `apiUrl = '/api'` on `https://normasinternet2.receita.fazenda.gov.br`.
- Endpoint (external consultation, by view):
  `GET /api/consulta-externa/ato/{idAto}/visao/{slug}`
- Requires a `Referer`/`Origin` of the site (WAF/CORS returns `403` with an
  empty body otherwise). No auth token or cookie is needed for the *external*
  view.
- View slugs: `original` (id 3), `multivigente` (1), `vigente` (2),
  `exclusiva` (4), `conjunta` (5), `relacional` (6).
  - Requesting an unavailable view returns **HTTP 406** with JSON
    `{"status":"NOT_ACCEPTABLE","message":"A visão solicitada não está
    disponível para este ato. Consulte a visão original"}`.
  - An invalid slug returns **403** empty.
  - **Strategy: request `original` first** (it was available for the test act
    and is the as-published text); fall back to `vigente`/`multivigente` only if
    `original` 406s.
- Related endpoints seen in the bundle (for future needs):
  attachments `GET /api/consulta-externa/ato/{idAto}/anexo/{idAnexo}`,
  relational view `.../{idAto}/visao-relacional`.

### 1.4 Content JSON shape (view `original`)

Top-level fields of interest:

- `idAto` (int)
- `epigrafe`: `{ tipoAto:{ idTipoAto, siglaTipoAto:"IN", nomeTipoAto }, numeroAto:"107", dataAto:"1988-07-14", orgaos:[{ siglaOrgao:"SRF", nomeOrgao:"Secretaria da Receita Federal", ... }], dataAtoPorExtenso }` ← **verification key**
- `epigrafeCompleta` (str) — full title, e.g. "Instrução Normativa SRF nº 107, de 14 de julho de 1988"
- `epigrafeSimplificada`, `dadosPublicacao`, `dataPublicacao`, `dataVigenciaInicio`
- `ementas` (list) — summary
- `outrosSegmentos` (list) — **the document body**: each item has `textoIntegra`
  (HTML/text). Concatenate in list order to reconstruct the full text.
- `tiposSegmento`, `historico`, `vigente`, `ehRepublicado`, etc.

`dataAto` (`YYYY-MM-DD`) matches the canonical act date exactly → primary match field.

---

## 2. Input & matching

- **Source of truth:** `output_canonical/canonical_referred_documents.json`
  (the same curated file the decreto pipeline uses), filtered to
  `type_slug == "instrucao_normativa_srf"` (17 records). Do **not** parse the
  `.md`; it is a generated view. Fields available per record: `number`,
  `date` (Portuguese, e.g. "14 de julho de 1988"), `canonical_name`,
  `filename`.
- Reuse existing helpers in `legal_document_processor.py`:
  `parse_pt_date` ("14 de julho de 1988" → `1988-07-14`) and
  `canonical_loader.py` for loading + de-duping records by number+date.
- **Matching rule per canonical record** — accept an `idAto` only if the stage-2
  JSON satisfies **all**: `epigrafe.tipoAto.siglaTipoAto == "IN"`,
  `epigrafe.numeroAto == number`, one of `epigrafe.orgaos[].siglaOrgao == "SRF"`,
  and `epigrafe.dataAto == parse_pt_date(date)`.

---

## 3. Fetch algorithm (per record)

1. `year = parse_pt_date(date).year`; `expected_iso = parse_pt_date(date)`.
2. Ensure a session with `JSESSIONID` (one warm-up `GET consulta.action`).
3. **Search**: `GET consulta.action` with the full field set,
   `tiposAtosSelecionados=42`, `numero_ato=number`, `tipoData=1`
   (search by act date), `ano_ato=year`, `p=1`, browser UA + Referer.
4. Parse result HTML → collect unique `idAto` values (regex/BS4 on
   `link.action?idAto=(\d+)`).
5. If no hits, retry with `tipoData=2` (publicação date), then as a last resort
   search number-only (omit `ano_ato`) and rely on stage-6 verification.
6. **Resolve + verify**: for each candidate `idAto`,
   `GET normasinternet2/api/consulta-externa/ato/{idAto}/visao/original`
   (Referer set). On 406, retry `vigente` then `multivigente`. Apply the
   §2 matching rule. Stop at the first fully-matching act.
7. **Persist** (see §4). If zero or multiple candidates survive verification, do
   not save the document — record it in `needs_review.json` with the reason
   (`not_found`, `ambiguous`, `date_mismatch`, `only_view_unavailable`).

Politeness: reuse the decreto pipeline's rate limiting (a small delay between
records); set a descriptive User-Agent; cache the raw JSON to avoid refetching.

---

## 4. Outputs (mirror the decreto pipeline layout)

Write under a new `output_instrucoes_normativas/` (parallel to
`output_decretos/`):

- `documents/` — one file per matched act. Save **both**:
  - `in_srf_{number}_{YYYYMMDD}.json` — the raw API JSON (lossless, keeps
    segments/ementas/metadata for downstream RAG use), and
  - `in_srf_{number}_{YYYYMMDD}.txt` (or `.docx`) — reconstructed plain text:
    `epigrafeCompleta` + ementa + `\n\n`.join(seg["textoIntegra"]) with HTML
    stripped. Reuse `WordDocumentBuilder` (as the decreto fetcher does) if a
    `.docx` is desired for parity with the other pipelines.
- `metadata/`
  - `fetch_report.json` — per-record status, chosen `idAto`, resolved view,
    source URLs, matched vs canonical fields.
  - `needs_review.json` — unmatched/ambiguous records with reasons.

---

## 5. Proposed module layout

- `receita_norma_fetcher.py` — new: `search_ato(session, numero, tipo_code,
  year, tipo_data)` → `[idAto]`; `fetch_ato_json(idAto, view="original")` →
  dict (with 406 fallback); `reconstruct_text(json)`; `verify(json, record)`.
  Purely `requests` + `re`/`BeautifulSoup`; no Selenium.
- `fetch_instrucoes_normativas_main.py` — new orchestrator mirroring
  `fetch_decretos_main.py`: CLI `--only`, `--limit N`, `--dry-run`, loads
  canonical records via `canonical_loader.py`, iterates §3, writes §4.
- Reuse `parse_pt_date` / `construct_urn_helper` from
  `legal_document_processor.py` and the loader from `canonical_loader.py`.
- Generalization note: the type code (`42`) and órgão sigla (`SRF`) are the only
  IN-SRF-specific bits. Parameterizing them makes this reusable for
  `instrucao_normativa_rfb` (same code `42`, órgão `RFB`) and many other RFB act
  types in `by_type/` (ADE, ADI, Portaria, Solução de Consulta, …), which all
  live in the same `sijut2consulta` system. Worth designing the fetcher around a
  `(tipo_code, orgao_sigla)` pair from the start.

---

## 6. Tests (offline, mirror `tests/test_decreto_fetching.py`)

- Save the live fixtures already captured during this investigation:
  - a `consulta.action` result HTML for IN 107/1988,
  - the `ato/14681/visao/original` JSON,
  - a 406 view-unavailable JSON.
- Unit tests: idAto extraction from result HTML; verification pass/fail on
  órgão/number/date (incl. the SRF-vs-RFB and nº 84 1979-vs-2001 collision
  cases); text reconstruction from `outrosSegmentos`; 406→fallback logic.

---

## 7. Risks / open items

- **Undated / ambiguous canonical entries** (e.g. the duplicated nº 599, or any
  IN with no source filename): may not disambiguate by date → route to
  `needs_review.json`, consistent with the decreto pipeline's handling of
  undated references.
- **WAF sensitivity:** the `/api` host requires a valid `Referer`/`Origin` and a
  browser UA; keep both. If it tightens, the fallback is to drive the public SPA
  with Selenium (same `idAto`), but that should not be necessary.
- **View availability:** a few acts may lack `original`; the 406 message
  explicitly directs to another view — the fallback chain handles it.
- **Segment HTML:** `textoIntegra` may contain markup/anchors; decide whether
  the RAG corpus wants raw HTML or cleaned text (recommend keeping the raw JSON
  regardless, so nothing is lost).
- **Rate limiting:** only 17 documents here, so load is trivial; still be polite
  for when this is generalized to the larger `by_type` buckets.
