# Implementation log: fetching "Instrução Normativa SRF" from the Receita Federal portal

Date: 2026-07-18

Implements the plan in
`20260717_192916_instrucao_normativa_srf_fetch_plan.md`: fetch the 17 canonical
`instrucao_normativa_srf` references from the Receita Federal norms portal
(`sijut2consulta`) using plain `requests` (no Selenium), verify each hit against
the canonical `(type, number, órgão, date)`, and persist raw JSON + reconstructed
text + `.docx` under `output_instrucoes_normativas/`.

**Outcome:** 14 / 16 unique acts fetched (87.5%). The 2 not fetched genuinely do
not exist in the portal (confirmed live) and are routed to `needs_review.json`.

---

## 1. What was built

| File | Role |
|---|---|
| `receita_norma_fetcher.py` | New. Search + verify + fetch + reconstruct; `ActType` registry (parameterized by `(tipo_code, orgao_sigla)`). No Selenium. |
| `fetch_instrucoes_normativas_main.py` | New. Orchestrator mirroring `fetch_decretos_main.py` (`--only`, `--limit`, `--dry-run`, `--no-docx`). |
| `canonical_loader.py` | Added `instrucao_normativa_srf` / `instrucao_normativa_rfb` to `TYPE_SLUG_TO_URN_TYPE`. |
| `tests/test_instrucao_normativa_fetching.py` | New. 18 offline tests against live-captured fixtures. |
| `tests/fixtures/receita_*.{html,json}` | New. Trimmed `consulta.action` result, `visao/original` JSON, `visao/vigente` 406 body. |
| `CLAUDE.md` | Added an "Instrução Normativa (Receita Federal) Fetching" section. |

## 2. Process followed

1. **Studied the existing pipelines to mirror** — `fetch_decretos_main.py`
   (orchestration + reporting shape), `planalto_decreto_fetcher.py` (a
   `requests`-only fetcher with its own result dataclass, `fetch_one`/`fetch_many`,
   docx reuse), `canonical_loader.py` (load + de-dup by number+date), and
   `tests/test_decreto_fetching.py` (offline fixture-based tests).

2. **Verified the plan's endpoints live** before writing code:
   - Warm-up `GET consulta.action` sets `JSESSIONID`; the search with the full
     field set (`tiposAtosSelecionados=42`, `numero_ato=107`, `tipoData=1`,
     `ano_ato=1988`) returned exactly one `idAto=14681`.
   - `GET normasinternet2/api/consulta-externa/ato/14681/visao/original` (with a
     same-site `Referer`) returned the JSON with `epigrafe` (siglaTipoAto `IN`,
     numeroAto `107`, dataAto `1988-07-14`, órgão `SRF`), `ementas`, and 50
     `outrosSegmentos`. Confirmed the WAF returns **403** (not 406) without a
     `Referer`, and that `vigente`/`multivigente` return **406** for this act (so
     `original` is the available view here — validating the fallback chain).

3. **Captured fixtures** from those live responses (search HTML trimmed to a
   ~5 KB fragment around the result links) so tests stay offline.

4. **Implemented** `receita_norma_fetcher.py`:
   - `ActType` dataclass + `ACT_TYPES` registry — only `(tipo_code, orgao_sigla)`
     is act-specific, so the module already supports `instrucao_normativa_rfb`
     and generalizes to other RFB act types.
   - `build_search_params` (full field set), `extract_id_atos` (regex, dedup,
     handles the `?antigo=1&idAto=` and `&amp;` variants), `search_ato`,
     `fetch_ato_json` (view-chain with 406 fallback, per-`idAto` cache), `verify`
     (type/number/órgão/date), `reconstruct_text` (épigrafe + ementa + ordered
     segments, HTML stripped, `omitir` segments dropped), and persistence to
     `.json` + `.txt` + `.docx` (reusing `WordDocumentBuilder`).

5. **Wrote the orchestrator** and ran it live.

## 3. Findings that changed the design (beyond the plan)

The plan anticipated SRF-vs-RFB and cross-year number collisions. Two further
real-world cases surfaced only when running against all 16 records:

### 3.1 DOU republications (false "ambiguous")
Initial run flagged nº **208/2002** and nº **599/2005** as `ambiguous` — 3 verified
`idAto`s each. Inspection showed these are the **same act republished** in the DOU
(an original plus retificações), all sharing number/date/órgão:

```
208: 15079 pub 2002-10-01  textlen 51112  (full text, 322 segments)
     15080 pub 2002-10-08  textlen  1019  (retificação excerpt)
     15081 pub 2004-03-11  textlen  1360  (retificação excerpt)
```

The **earliest publication carries the full text**; later ones are correction
excerpts. Added `_select_primary`: when all verified candidates share one épigrafe
key (type/number/date/órgão-set), pick the earliest `dataPublicacao` and record the
rest as `alternate_id_atos` (no longer a review case). This recovered 208 and 599.
Genuinely distinct acts (different date/órgão — only reachable via an *undated*
canonical entry) still route to `ambiguous` → review.

### 3.2 Acts absent from the portal
nº **23/1983** and nº **84/1979** return **zero** results for a year-scoped search
on both `tipoData=1` and `2`. Number-only search shows the portal's nº 23 series
skips 1983 (…1982-04-30, 1985-04-02…) and nº 84 skips 1979 (earliest 1980-07-24) —
these two acts predate the portal's coverage. Correctly left in `needs_review.json`
(reason `date_mismatch`); no false document is saved.

## 4. Verification

- **Offline tests:** `python -m pytest tests/ -q` → **90 passed** (18 new; the
  existing 72 unaffected). New tests cover idAto extraction (incl. `antigo`/`&amp;`
  variants), the full search field set, verify pass/fail on type/number/órgão/date
  (incl. the SRF-vs-RFB collision), republication selection (earliest publication,
  distinct-act ambiguity), text reconstruction with markup stripping and `omitir`,
  and the 406 fixture shape.
- **Live end-to-end:** `python fetch_instrucoes_normativas_main.py` →
  14/16 success. Spot-checked `in_srf_208_20020927`: `.txt` is 53 KB of the full
  act, report row shows `id_ato=15079`, `alternate_id_atos=['15080','15081']`,
  `review_reason=republication_selected`; the `.docx` opens with 274 paragraphs and
  the correct title property.

## 5. How to run

```bash
python fetch_instrucoes_normativas_main.py                 # IN SRF (default)
python fetch_instrucoes_normativas_main.py --dry-run       # list, no fetch
python fetch_instrucoes_normativas_main.py --limit 3       # first 3, for testing
python fetch_instrucoes_normativas_main.py --only instrucao_normativa_rfb
python -m pytest tests/test_instrucao_normativa_fetching.py -v
```

Outputs: `output_instrucoes_normativas/documents/{in_srf_<n>_<YYYYMMDD>.{json,txt,
docx}}` and `metadata/{fetch_report.json,needs_review.json}`.

## 6. Notes / open items

- **Dependencies:** this environment lacked `beautifulsoup4`, `python-docx`,
  `selenium`, `tqdm`, `pytest`; installed via `pip --break-system-packages`. The
  Selenium import is only a transitive dependency of `br_legal_parser`'s
  `WordDocumentBuilder`; no browser is launched by this pipeline.
- **`needs_review` (23/1983, 84/1979):** absent from the portal — need a manual
  source (or confirmation they are out of scope).
- **Generalization:** `ACT_TYPES` + the `(tipo_code, orgao_sigla)` design make this
  directly reusable for `instrucao_normativa_rfb` and other `sijut2consulta` act
  types (ADE, ADI, Portaria, Solução de Consulta, …) by adding registry entries.
