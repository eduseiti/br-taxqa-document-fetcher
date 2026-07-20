# Plan: Generalize the Receita Federal fetcher to all SRF/RFB (and sibling-órgão) acts

Date: 2026-07-18

Builds on `20260717_192916_instrucao_normativa_srf_fetch_plan.md` and the
implementation logged in `20260718_091450_instrucao_normativa_srf_implementation.md`.
Goal: reuse the exact same `sijut2consulta` search + `normasinternet2` REST-API
mechanism (plain `requests`, no Selenium) to fetch **all** Receita-Federal-portal
act types referenced in `output_canonical/canonical_referred_documents.json` — not
just `instrucao_normativa_srf` — and route every document kind into its **own
output folder**.

## 0. TL;DR

- The `instrucao_normativa_srf` pipeline is already **type-generic by design**:
  only the `(tipo_code, orgao_sigla)` pair is act-specific (`ActType` registry).
  Extending it is mostly **registry data + orchestration + output layout**, not
  new fetching logic.
- Live reconnaissance (this session) confirms the portal covers **every órgão we
  need** — SRF, RFB, Cosit, CST, PGFN, Cosar, Codac, MF, CGSN — and enumerates
  the exact `Tipo do ato` codes. **272 / 478** canonical records (25 type_slugs)
  are confidently portal-fetchable this way; **10** are edge cases needing a
  per-record órgão decision; **196** belong to other pipelines/sources.
- Two mechanism improvements surfaced and should be folded in:
  1. **Filter the search by órgão** (`orgaosSelecionados`) — the portal filters
     server-side, which cleanly resolves same-number/same-year collisions across
     órgãos (verified: `Ato Declaratório nº 22/1997` exists for SRF, Cosar **and**
     Cosit with three different dates).
  2. **Verify by numeric `idTipoAto`** (== the form's tipo code) instead of the
     punctuated sigla string (`"Parec. Norm."`) — robust to casing/punctuation.

---

## 1. Live reconnaissance findings (all verified this session)

### 1.1 `Tipo do ato` codes (`tiposAtosSelecionados`)

Scraped from `consulta.action` (`input.chkTiposAtos`, attrs `value`/`sigla`/`nome`).
The ones we need (full list of 41 is in the form):

| code | sigla | Tipo do ato |
|---|---|---|
| 42 | IN | Instrução Normativa |
| 79 | IN Conj. | Instrução Normativa Conjunta |
| 72 | SC | Solução de Consulta |
| 75 | SCI | Solução de Consulta Interna |
| 73 | SD | Solução de Divergência |
| 7 | AD | Ato Declaratório *(this is the "Comum" in canonical names)* |
| 9 | ADE | Ato Declaratório Executivo |
| 10 | ADI | Ato Declaratório Interpretativo |
| 11 | ADN | Ato Declaratório Normativo |
| 59 | Parec. Norm. | Parecer Normativo |
| 61 | Parec. | Parecer |
| 77 | Nota | Nota |
| 57 | Port. | Portaria |
| 67 | Resol. | Resolução |
| 35 | Desp. | Despacho |

**Key insight:** "Ato Declaratório **Comum**" is not a distinct portal type — it is
the plain `Ato Declaratório` (code **7**, sigla `AD`). The canonical suffix
(`_srf`, `_cosit`, `_cosar`, `_pgfn`) is the **órgão**, not part of the type.

### 1.2 `Órgãos e unidades` facet (`orgaosSelecionados`)

The facet has **446** órgão checkboxes (`input.chkOrgaos`); the checkbox `value`
**is the órgão sigla** submitted. Casing is display-cased and mixed — this matters:

- Uppercase: `SRF`, `RFB`, `CST`, `PGFN`, `CGSN`, `MF`, `SRRF01`…`SRRF10`, `BCB`, `Carf`.
- Title-case: `Cosit`, `Cosar`, `Codac`, `Coana`, `Cotec`, `Sutri`, `Suara`, `Sufis`.

All órgãos referenced by our canonical suffixes are present. Verified live that
`orgaosSelecionados` filters **server-side**:

```
Ato Declaratório nº 22/1997, tipo=7 (AD):
  no órgão filter -> idAto 1266 (Cosit, 1997-07-17)
                     idAto 1265 (Cosar, 1997-06-02)
                     idAto 1264 (SRF,   1997-04-30)
  orgaosSelecionados=SRF   -> idAto 1264 only
  orgaosSelecionados=Cosar -> idAto 1265 only
```

This is the decisive reason to add órgão to the search (§4.2): it turns a
3-candidate verify problem into a 1-candidate fetch. **Answer to "which other
documents can be downloaded from the same portal": every act whose órgão is in
this facet — which for our dataset means all SRF, RFB, Cosit, CST, PGFN, Cosar,
Codac, MF and CGSN acts (see §2).**

### 1.3 Content JSON verification keys (unchanged mechanism, sturdier keys)

For every act type spot-checked (IN, SC, SCI, SD, ADI, ADN, AD, Parecer Normativo)
the `visao/{original|vigente|multivigente}` JSON `epigrafe.tipoAto` carries:

- `idTipoAto` **==** the form tipo code (42, 72, 59, 7, 11, …) in every case →
  use this numeric field as the verify key.
- `siglaTipoAto` == the form `sigla` (`IN`, `SC`, `AD`, `ADN`, … and the
  punctuated `Parec. Norm.`).

`epigrafe.orgaos[].siglaOrgao` returns the same mixed casing as the facet
(`Cosit`, `SRF`, `PGFN`, `CST`) — **verify órgão case-insensitively** (§4.3).

### 1.4 Spot-checked acts (all resolved + verified live)

| canonical | tipo | idAto | épigrafe (sigla, nº, data, órgão) |
|---|---|---|---|
| SC Cosit 100/2020 | 72 | 112717 | SC, 100, 2020-09-28, [Cosit] |
| ADI SRF 14/2005 | 10 | 5655 | ADI, 14, 2005-12-01, [SRF] |
| AD (Comum) SRF 22/1997 | 7 | 1264 | AD, 22, 1997-04-30, [SRF] |
| Parecer Normativo CST 1/1985 | 59 | 30870 | Parec. Norm., 1, 1985-02-04, [CST] |
| ADN Cosit 19/1998 | 11 | 5954 | ADN, 19, 1998-11-11, [Cosit] |
| SD Cosit 27/2008 | 73 | 117198 | SD, 27, 2008-05-30, [Cosit] |
| SCI Cosit 10/2014 | 75 | 53396 | SCI, 10, 2014-06-05, [Cosit] |
| **AD Comum PGFN 3/2008** | 7 | 435 | AD, 3, 2008-09-18, [PGFN] |

The PGFN row confirms PGFN acts are indexed in this portal (not only RFB acts).

---

## 2. Coverage classification of the full canonical file (478 records)

### 2.1 Portal-fetchable — add to the registry (25 slugs, 272 docs)

| type_slug | n | tipo_code | tipo_sigla | órgão (search & verify) |
|---|--:|--:|---|---|
| instrucao_normativa_srf | 17 | 42 | IN | SRF *(already done)* |
| instrucao_normativa_rfb | 25 | 42 | IN | RFB *(registry exists; not yet run)* |
| solucao_de_consulta_cosit | 110 | 72 | SC | Cosit |
| parecer_normativo_cst | 24 | 59 | Parec. Norm. | CST |
| ato_declaratorio_comum_pgfn | 16 | 7 | AD | PGFN |
| solucao_de_consulta_interna_cosit | 13 | 75 | SCI | Cosit |
| ato_declaratorio_interpretativo_srf | 9 | 10 | ADI | SRF |
| ato_declaratorio_normativo_cst | 7 | 11 | ADN | CST |
| ato_declaratorio_comum_srf | 7 | 7 | AD | SRF |
| parecer_normativo_cosit | 7 | 59 | Parec. Norm. | Cosit |
| ato_declaratorio_normativo_cosit | 6 | 11 | ADN | Cosit |
| nota_pgfn | 5 | 77 | Nota | PGFN ⚠ verify live |
| parecer_pgfn | 5 | 61 | Parec. | PGFN ⚠ verify live |
| solucao_de_divergencia_cosit | 4 | 73 | SD | Cosit |
| ato_declaratorio_interpretativo_rfb | 3 | 10 | ADI | RFB |
| portaria_mf | 3 | 57 | Port. | MF |
| ato_declaratorio_executivo_rfb | 2 | 9 | ADE | RFB |
| parecer_pgfncat | 2 | 61 | Parec. | PGFN ⚠ verify órgão sigla |
| ato_declaratorio_comum_cosit | 1 | 7 | AD | Cosit |
| ato_declaratorio_executivo_codac | 1 | 9 | ADE | Codac |
| ato_declaratorio_executivo_srf | 1 | 9 | ADE | SRF |
| ato_declaratorio_comum_cosar | 1 | 7 | AD | Cosar |
| ato_declaratorio_executivo_cosit | 1 | 9 | ADE | Cosit |
| parecer_cosit | 1 | 61 | Parec. | Cosit |
| resolucao_cgsn | 1 | 67 | Resol. | CGSN ⚠ verify live |

⚠ = mechanism identical, but the specific `(tipo, órgão)` pair was **not**
spot-checked this session; confirm with one live probe before the batch run
(PGFN Nota/Parecer and CGSN Resolução are the untested pairs).

### 2.2 Edge cases — per-record órgão decision (6 slugs, 10 docs)

| type_slug | n | note |
|---|--:|---|
| solucao_de_consulta | 2 | Regional: names carry `Disit/SRRF03`, `Disit/SRRF06` → órgão is the regional unit (`SRRF03`…), not a fixed sigla. Derive órgão from `canonical_name`, or search by number+date and verify tipo `SC` accepting any órgão. |
| parecer_normativo | 1 | No órgão in name ("Parecer Normativo nº 129/1973"); 1970s PNs are CST — verify by number+date, órgão unconstrained. |
| parecer_sei / nota_sei / parecer / despacho | 7 | SEI/loose pareceres & a despacho — órgão ambiguous; handle as "tipo + number + date, any órgão", else `needs_review`. |

Recommended handling: allow an `ActType` with `orgao_sigla=None` meaning *don't
filter/verify by órgão* (match on tipo+number+date only), and record the resolved
órgão in the report for auditing.

### 2.3 Out of scope for this portal (18 slugs, 196 docs)

- Legislative (other pipelines): `lei` (113), `decreto` (38), `decreto_lei` (13),
  `medida_provisoria` (7), `lei_complementar` (2), `constituicao_federal` (1),
  `tratados_convencoes` (2).
- Courts/other bodies: `jurisprudencia_*` (4 total), `sumula_stj` (2),
  `sumula_carf` (1), `circular_banco_central` (1), `resolucao_tse` (1),
  `resolucao_cgpc` (1, órgão not in facet), `portaria_conjunta` (1),
  `ato_declaratorio_comum_presidencia_da_mesa_do_congresso_nacional` (1),
  `outros` (8, heterogeneous).

`medida_provisoria` and `lei_complementar` could be added to the **normas.leg.br**
(LexML/Selenium) pipeline later, but that is out of scope here.

---

## 3. Design change A — output folder per document kind

Current: everything lands in `output_instrucoes_normativas/documents/` with a
`file_prefix` (`in_srf`) distinguishing files. Requirement: **each kind in its own
folder.** Proposed layout (single parent, per-`type_slug` subtree):

```
output_receita_federal/
├── instrucao_normativa_srf/
│   ├── documents/   in_srf_107_19880714.{json,txt,docx}
│   └── metadata/    fetch_report.json, needs_review.json
├── instrucao_normativa_rfb/
│   ├── documents/ ...
│   └── metadata/ ...
├── solucao_de_consulta_cosit/
│   ├── documents/   sc_cosit_100_20200928.{json,txt,docx}
│   └── metadata/ ...
├── ... (one subtree per fetched type_slug) ...
└── metadata/
    └── aggregate_report.json   # roll-up across all kinds
```

- The per-kind `documents/`/`metadata/` mirrors today's structure, so
  `ReceitaNormaFetcher._persist`/report code barely changes — it just receives a
  per-kind `output_dir`.
- `file_prefix` stays for readable stems but is now scoped inside its own folder,
  so cross-type stem collisions are impossible.
- Add a top-level `aggregate_report.json` summing all kinds (per-type totals +
  overall success rate).
- **Migration:** keep the existing `output_instrucoes_normativas/` outputs or move
  IN SRF under the new tree as `instrucao_normativa_srf/`. Recommend the new tree
  for everything and leave the old dir in place (no destructive move).

---

## 4. Design change B — generalize the fetcher

Small, surgical edits to `receita_norma_fetcher.py`:

### 4.1 Expand the `ActType` registry (data, not logic)

Add every §2.1 slug. Extend `ActType` with two fields:

- `orgao_search: Optional[str]` — the facet value to submit in `orgaosSelecionados`
  (e.g. `"Cosit"`, `"SRF"`, `"PGFN"`); `None` = don't filter (edge cases).
- keep `orgao_sigla` for verification (same string; compared case-insensitively).
- Replace `tipo_sigla` verification with `tipo_code`-based `idTipoAto` matching
  (keep `tipo_sigla` only as a human label). Add `file_prefix` per slug
  (e.g. `sc_cosit`, `adi_srf`, `ad_pgfn`).

Optionally **generate** the registry from a compact table (the §2.1 table) plus the
scraped tipo-code map, so adding a type is a one-line entry.

### 4.2 Add órgão to the search

`build_search_params(...)` currently hard-codes `orgaosSelecionados=""`. Pass
`act.orgao_search or ""`. This narrows collision-prone types (all `AD`/`ADE`/
`Parecer`/`SC` numbers recur across órgãos) to a single server-side hit and makes
verification a formality. Keep the number-only / `tipoData=2` fallbacks for acts
missing from the órgão-scoped index.

### 4.3 Robust verification

`verify(...)`:
- `epigrafe.tipoAto.idTipoAto == act.tipo_code` (numeric) — replaces the
  `siglaTipoAto == "Parec. Norm."` string compare.
- number match (unchanged, dot/space-insensitive).
- órgão: `act.orgao_sigla is None` → skip; else case-insensitive membership
  (`act.orgao_sigla.casefold() in {o.casefold() for o in orgaos}`).
- date match (unchanged).

The existing republication selection (`_select_primary`, earliest `dataPublicacao`
carries full text) and 406 view-chain fallback are **type-agnostic and stay as-is**
— they already handled IN correctly and apply verbatim to SC/AD/Parecer/etc.

### 4.4 Generalize the orchestrator

Rename/extend `fetch_instrucoes_normativas_main.py` → `fetch_receita_normas_main.py`
(keep the old filename as a thin shim importing the new one, to not break the
documented IN command). Changes:

- `DEFAULT_TYPES` → all §2.1 slugs (registry keys), or a curated default set.
- `--only <slug>` (choices = registry keys), `--limit`, `--dry-run`, `--no-docx`
  unchanged; add `--types a,b,c` for a subset and `--exclude`.
- For each fetched slug, build `output_dir = output_receita_federal/<slug>` and
  call the existing `fetch_type` + `write_reports` (per-kind), then write the
  aggregate roll-up.
- `canonical_loader.load_canonical_docs` already loads by `type_slug`; just add
  the new slugs to `TYPE_SLUG_TO_URN_TYPE` (URN token is informational for these).

---

## 5. Tests (extend `tests/test_instrucao_normativa_fetching.py`)

Offline, fixture-driven (capture 2–3 new live responses, trimmed):

- Registry completeness: every §2.1 slug present; `(tipo_code, orgao_search)` set.
- `build_search_params` now emits `orgaosSelecionados=<facet value>`.
- `verify` by `idTipoAto` (numeric) passes for `AD`/`SC`/`Parec. Norm.`; órgão
  compare is **case-insensitive** (`Cosit` vs `COSIT`).
- The `AD nº 22/1997` 3-órgão fixture: órgão-filtered search returns one idAto;
  unfiltered search + verify still selects the SRF/date-matching act.
- Edge slug with `orgao_sigla=None`: matches on tipo+number+date, any órgão.
- Output path: `_persist` writes under `output_receita_federal/<slug>/documents/`.

Keep the existing 90 tests green (the IN path behavior is unchanged when
`orgao_search` is set to `SRF`/`RFB`).

---

## 6. Risks / open items

- **Untested `(tipo, órgão)` pairs** (⚠ in §2.1): PGFN `Nota`(77)/`Parecer`(61),
  `parecer_pgfncat`, `resolucao_cgsn`(67). One live probe each before the batch;
  if a pair 0-results, fall back to number-only search + verify, else
  `needs_review`. PGFN pareceres/notas may partly live on a separate PGFN system —
  confirm the portal indexes them (AD PGFN is confirmed).
- **Regional `solucao_de_consulta`** (`Disit/SRRF0x`): órgão is a regional unit;
  either derive the sigla from `canonical_name` or fetch órgão-unconstrained and
  record the resolved órgão. Small volume (2).
- **Órgão-scoped index gaps:** a few acts may be filed under a parent órgão (e.g.
  RFB vs a coordenação). The number-only + `tipoData=2` fallbacks (already in
  `fetch_one`) cover this; verification still guards correctness.
- **Volume/politeness:** ~255 new fetches (dominated by 110 SC Cosit). Keep the
  1.5 s inter-record delay + the per-idAto JSON cache; total run is well under an
  hour. Consider `--types` batching to run órgão-by-órgão.
- **`AD` (code 7) vs the executivo/interpretativo/normativo variants:** they are
  *distinct* type codes (7/9/10/11). Ensure each canonical `ato_declaratorio_*`
  slug maps to the right code (table §2.1), or a search will return the wrong
  family. Verification by `idTipoAto` catches a mis-map (0 survivors → review).

---

## 7. Suggested rollout order

1. Add registry entries + `orgao_search`/`idTipoAto` verify + órgão in search
   (§4.1–4.3); keep IN SRF/RFB behavior identical (regression: rerun IN SRF, expect
   the same 14/16).
2. Per-kind output layout (§3) + aggregate report.
3. Live-probe the ⚠ pairs (§6); wire edge slugs with `orgao_sigla=None`.
4. Run high-value órgãos first: `--only solucao_de_consulta_cosit` (110),
   `parecer_normativo_cst` (24), `ato_declaratorio_comum_pgfn` (16), then the rest.
5. Extend tests (§5); update `CLAUDE.md` (new section generalizing the IN one:
   registry table, órgão facet, per-kind folders, new entry point).
