# Implementation log: generalizing the Receita Federal fetcher to all act types

Date: 2026-07-18

Implements `20260718_110758_receita_federal_all_acts_fetch_plan.md`: extend the
Instrução-Normativa-SRF pipeline to fetch **every Receita-Federal-portal act type**
referenced in `output_canonical/canonical_referred_documents.json` from the same
`sijut2consulta` portal (plain `requests`, no Selenium), with **one output folder
per document kind**.

**Outcome:** **245 / 278** unique acts fetched (**88.13 %**) across **31 act
types**. All 33 non-fetches are genuine portal boundaries (undated references, or
number/date combos the portal does not carry), correctly routed to
`needs_review.json` — no wrong document is ever saved.

---

## 1. What changed

| File | Change |
|---|---|
| `receita_norma_fetcher.py` | `ActType` reworked to `(tipo_code, orgao)` + `_REGISTRY_TABLE` of **31 types**; search now sends `orgaosSelecionados`; `verify` keys on numeric `idTipoAto` and compares órgão **case-insensitively** / skips it when `orgao=None`. |
| `fetch_receita_normas_main.py` | **New** orchestrator. Per-kind output folders, aggregate roll-up report, `--only/--types/--exclude/--limit/--dry-run/--no-docx/--list`. |
| `fetch_instrucoes_normativas_main.py` | Now a **deprecated shim** → forwards to the new orchestrator, defaulting to IN SRF + `output_instrucoes_normativas/`. |
| `canonical_loader.py` | `_urn_type_for` derives a URN token for any Receita slug (no parallel list); no longer raises on unlisted Receita types. |
| `tests/test_instrucao_normativa_fetching.py` | Updated the wrong-type test to mutate `idTipoAto`; added 7 tests (registry coverage, órgão in search, `idTipoAto` verify, case-insensitive órgão, `orgao=None`, AD collision, per-kind path). |
| `CLAUDE.md` | Section rewritten from "Instrução Normativa" to "Receita Federal Norms (all act types)". |

## 2. Process followed

1. **Live reconnaissance** of `consulta.action` to enumerate the two orthogonal
   facets: 41 `Tipo do ato` codes (`input.chkTiposAtos`) and 446 `Órgãos e
   unidades` values (`input.chkOrgaos`, the value **is** the sigla). Confirmed all
   our órgãos are present (mixed casing: `SRF`/`RFB`/`CST` vs `Cosit`/`Codac`).
2. **Spot-checked one act per type family** against the content API to lock the
   `(tipo_code, órgão, épigrafe)` mapping: IN, SC, SCI, SD, ADI, ADN, AD, Parecer
   Normativo, Portaria, Resolução, Despacho, Parecer. Verified `idTipoAto` == the
   form tipo code in every case → adopted it as the verify key (robust to the
   punctuated siglas like `Parec. Norm.`).
3. **Classified all 478 canonical records**: 272 confidently portal-fetchable
   (25 slugs), 10 edge, 196 out-of-scope (other pipelines / courts).
4. Implemented the registry + search/verify changes and the per-kind orchestrator.
5. Ran the **full live fetch** and analyzed every `needs_review` case.

## 3. Design decisions that mattered

### 3.1 Órgão as a first-class search filter (not just a verify key)
The plan's key finding: the portal filters by órgão **server-side**. Adding
`orgaosSelecionados=<sigla>` turns collision-prone types into single-hit fetches.
Real case handled live: `Ato Declaratório nº 22/1997` exists for **SRF (1997-04-30),
Cosar (1997-06-02) and Cosit (1997-07-17)** — the SRF fetcher now retrieves exactly
the SRF/date-matching act.

### 3.2 "Ato Declaratório Comum" == plain `Ato Declaratório` (code 7)
"Comum" is not a portal type; the canonical suffix (`_srf`/`_cosit`/`_pgfn`) is the
**órgão**. Executivo/Interpretativo/Normativo are distinct codes (9/10/11).

### 3.3 `orgao=None` for ambiguous/regional acts
Generic `Parecer`, `Parecer SEI`, and `Disit/SRRF` Soluções de Consulta have no
fixed órgão sigla → match on tipo+number+date only. `solucao_de_consulta` (the
regional `Disit/SRRF03`, `Disit/SRRF06` entries) fetched **2/2** this way.

### 3.4 PGFN acts *are* in this portal; SEI/PGFNCAT pareceres are not
Confirmed live: `Ato Declaratório PGFN`, `Nota PGFN`, `Despacho PGFN` resolve.
`Parecer SEI` and `Parecer PGFNCAT` return **zero** results (different system) →
`needs_review`.

## 4. Results

Overall: **278 unique acts (after number+date de-dup), 245 fetched, 36 needs_review**
(some rows both fail and are undated). Every fetched act produced a lossless
`.json`, a reconstructed `.txt`, and a `.docx` — **245 of each**.

Per-type success (full table in `output_receita_federal/metadata/aggregate_report.json`):

| type_slug | tot | ok | type_slug | tot | ok |
|---|--:|--:|---|--:|--:|
| solucao_de_consulta_cosit | 109 | **109** | ato_declaratorio_interpretativo_srf | 9 | 9 |
| instrucao_normativa_rfb | 24 | 22 | ato_declaratorio_normativo_cosit | 6 | 6 |
| parecer_normativo_cst | 24 | 15 | parecer_normativo_cosit | 7 | 7 |
| instrucao_normativa_srf | 16 | 14 | ato_declaratorio_comum_srf | 7 | 7 |
| ato_declaratorio_comum_pgfn | 15 | 14 | ato_declaratorio_normativo_cst | 7 | 5 |
| solucao_de_consulta_interna_cosit | 13 | 12 | portaria_mf | 3 | 3 |
| solucao_de_divergencia_cosit | 4 | 3 | resolucao_cgsn | 1 | 1 |
| nota_pgfn | 5 | 3 | despacho | 1 | 1 |
| parecer_pgfn | 5 | 1 | *(11 other 1–3-doc types)* | — | 100% |

The 10 `ato_declaratorio_executivo_*` / `_comum_cosit`/`_cosar` /
`ato_declaratorio_interpretativo_rfb` / `parecer_cosit` types fetched **100 %**.

### 4.1 Breakdown of the 36 needs_review (all legitimate)

| reason | n | meaning |
|---|--:|---|
| `not_found` | 19 | search returns nothing (18 of these are **undated** PGFN/SEI references — no year to search on; the rest predate/aren't in the portal) |
| `date_mismatch` | 13 | candidates found but no `(number, date, órgão)` match — the portal carries that number under a **different date** |
| `matched_without_date` | 3 | undated entry matched by number only (saved, but flagged for human confirmation) |
| `ambiguous` | 1 | distinct verified acts, not disambiguable |

**Verified the `date_mismatch` cases are real, not a matching bug** (live probe of
`parecer_normativo_cst`): portal has PN nº **129/1970** (canonical asks 1973), nº
**122/1972** (canonical 1974), nº **44** only for 1970/1971/1981 (canonical 1976).
The date guard correctly refuses to save a same-number, wrong-date act. These are
canonical-data / portal-coverage boundaries, not fetcher defects.

`parecer_normativo_cst` (15/24) is the weakest type purely because it is dominated
by 1970s pareceres whose exact number+date the portal does not index.

## 5. Output layout (one folder per kind)

```
output_receita_federal/
├── <type_slug>/              # 31 kinds, e.g. solucao_de_consulta_cosit/
│   ├── documents/            # {prefix}_{number}_{YYYYMMDD}.{json,txt,docx}
│   └── metadata/             # fetch_report.json (+ needs_review.json if any)
├── metadata/
│   └── aggregate_report.json # overall + by_type roll-up
└── fetch_receita_normas.log
```

## 6. Verification

- **Offline tests:** `python -m pytest tests/ -q` → **97 passed** (was 90; +7 new,
  1 updated for the `idTipoAto` verify key). Covers registry coverage, órgão in the
  search params, `idTipoAto` verification, case-insensitive órgão, `orgao=None`
  skip, the AD nº 22/1997 collision, and the per-kind output path.
- **Live end-to-end:** full run 245/278 (88.13 %); spot-checked
  `sc_cosit_100_20200928.txt` (clean full Solução de Consulta text), the per-kind
  folder tree, 245 json/txt/docx triples, and republication selection
  (IN SRF 208 → id 15079, alternates [15080, 15081]; 599 likewise).
- **Regression:** IN SRF still 14/16 and IN RFB 22/24 — unchanged behavior under
  the generalized code.

## 7. How to run

```bash
python fetch_receita_normas_main.py                 # whole registry -> output_receita_federal/<kind>/
python fetch_receita_normas_main.py --list          # registry + canonical counts
python fetch_receita_normas_main.py --only solucao_de_consulta_cosit
python fetch_receita_normas_main.py --types portaria_mf,resolucao_cgsn
python fetch_receita_normas_main.py --dry-run --limit 3
python fetch_instrucoes_normativas_main.py          # deprecated shim (IN SRF only)
python -m pytest tests/test_instrucao_normativa_fetching.py -v
```

## 8. Open items

- **Undated PGFN/SEI references (18):** `Nota PGFN CRJ nº 1.040`, `Parecer PGFN
  nº 1.888`, etc. carry no date in the canonical file, so they cannot be
  disambiguated by year; a manual idAto or a source date is needed.
- **1970s `parecer_normativo_cst` (≈9):** confirm whether the canonical dates are
  DOU-publication dates (vs act dates) — a `tipoData=2` retry keyed on publication
  date might recover a few; otherwise they are outside the portal's indexed range.
- **`parecer_sei` / `parecer_pgfncat` (6):** not in `sijut2consulta`; need the
  PGFN/SEI source if they are in scope.
- **`matched_without_date` (3):** saved on a number-only match — worth a human
  glance to confirm the right act was chosen.
