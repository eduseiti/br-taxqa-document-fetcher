# Canonical Duplicates and Remaining Missing Documents — Audit

**Generated:** 2026-07-31 21:26:54 (local time, from `date +%Y%m%d_%H%M%S`)
**Supersedes:** [`20260730_010159_missing_documents_to_fetch.md`](20260730_010159_missing_documents_to_fetch.md)
(64 documents were still to fetch at that point; the manual fetching round closed all but two)

## Scope

Two questions, answered against
`output_canonical/canonical_referred_documents.json` (478 references):

1. Which of the 478 references are **duplicates**, i.e. which collapse into the 462 unique documents?
2. Of those 462 unique documents, which still have **no `.docx`** in any of the four
   delivery folders?

## Method

**De-duplication key:** `(type_slug, number, date, canonical_name)`. Because canonical
naming already normalizes the act's identity, `canonical_name` alone yields exactly the
same 462 groups — the de-duplication is not sensitive to the choice.

**Folders scanned** (`.docx` only):

| Folder | `.docx` present | Notes |
|---|---:|---|
| `fetched_documents/documents` | 110 | `lei_*`, `lei_comp_*` |
| `output_decretos/documents` | 45 | `decreto_*`, `decreto_lei_*` |
| `output_receita_federal/documents` | 244 | flat symlink view over `<type_slug>/documents/` |
| `output_manual/documents` | 62 | hand-fetched, ad-hoc filenames |
| **Total** | **461** | |

**Matching**, in order of decreasing strictness:

1. `<expected_prefix>_<number>_<YYYYMMDD>[_N].docx`, where the expected prefix comes from
   `receita_norma_fetcher.ACT_TYPES[slug].file_prefix` (plus `lei`, `lei_comp`, `decreto`,
   `decreto_lei`). Number normalized by stripping thousand separators; date normalized from
   the Portuguese long form. — **402 matches**
2. Same number + date but a prefix outside the registry (all of them `output_manual`, whose
   naming is hand-made). — **12 matches**
3. Undated canonical record: `<expected_prefix>_<number>` with any trailing date/`_nodate`
   suffix, within the type-appropriate prefix. — **10 matches**
4. Hand-verified mapping for the `output_manual` files whose names cannot be derived from
   the canonical record (`REsp_1306393.docx`, `constituição_1988_19881005.docx`,
   `decreto_legislativo_92_19751105.docx`, …). Every one of these was confirmed by opening
   the `.docx` and reading its first paragraphs. — **36 matches**

## Answer 1 — the 16 duplicated references

478 references − 462 unique = **16 redundant records**, spread over **14 duplicate groups**
(two groups have three members each). Almost all of them are the same act cited once by its
colloquial name (Código Civil, CLT, CTN, ECA, FGTS, Convenção de Viena) and once by its
number.

| # | Canonical document | `type_slug` | Copies | Dataset filenames (`index`) |
|---:|---|---|---:|---|
| 1 | Ato Declaratório PGFN nº 3, de 18 de setembro de 2008 | `ato_declaratorio_comum_pgfn` | 2 | `Ato Declaratório (AD) PGFN nº 3, de 18 de setembro de 2008.txt` (3) · `Ato Declaratório PGFN nº 3.txt` (34) |
| 2 | Decreto-Lei nº 5.452, de 1º de maio de 1943 | `decreto_lei` | 2 | `Consolidação das Leis do Trabalho (CLT).txt` (58) · `Lei nº 5.452.txt` (227) |
| 3 | Decreto nº 56.435, de 8 de junho de 1965 | `decreto` | 2 | `Convenção de Viena, Decreto nº 56.435, de 8 de junho de 1965.txt` (63) · `Decreto nº 56.435.txt` (83) |
| 4 | Decreto nº 52.288, de 24 de julho de 1963 | `decreto` | **3** | `Convenção sobre Privilégios e Imunidades das Agências Especializadas.txt` (64) · `Convenção sobre Privilégios e Imunidades das Nações Unidas.txt` (65) · `Decreto nº 52.288.txt` (82) |
| 5 | Decreto nº 85.801, de 10 de março de 1981 | `decreto` | 2 | `Convênio de Criação de um Conselho de Cooperação Aduaneira.txt` (66) · `Decreto nº 85.801.txt` (99) |
| 6 | Lei nº 10.406, de 10 de janeiro de 2002 | `lei` | **3** | `Código Civil.txt` (67) · `Lei n° 10.406, de 10 de janeiro de 2002 - Código Civil.txt` (153) · `Lei nº 10.406.txt` (162) |
| 7 | Lei nº 5.172, de 25 de outubro de 1966 | `lei` | 2 | `Código Tributário Nacional (CTN).txt` (68) · `Lei nº 5.172.txt` (226) |
| 8 | Lei nº 8.069, de 13 de julho de 1990 | `lei` | 2 | `Estatuto da Criança e do Adolescente (ECA).txt` (109) · `Lei nº 8.069.txt` (241) |
| 9 | Instrução Normativa RFB nº 1.500, de 29 de outubro de 2014 | `instrucao_normativa_rfb` | 2 | `IN RFB nº 1.500, de 2014.txt` (110) · `Instrução Normativa RFB nº 1.500.txt` (114) |
| 10 | Instrução Normativa SRF nº 599, de 28 de dezembro de 2005 | `instrucao_normativa_srf` | 2 | `Instrução Normativa RFB nº 599.txt` (139) · `Instrução Normativa SRF nº 599, de 28 de dezembro de 2005.txt` (149) |
| 11 | Lei nº 8.036, de 11 de maio de 1990 | `lei` | 2 | `Legislação do Fundo de Garantia do Tempo de Serviço (FGTS).txt` (152) · `Lei nº 8.036.txt` (239) |
| 12 | Lei nº 10.522, de 19 de julho de 2002 | `lei` | 2 | `Lei n° 10.522, de 19 de julho de 2002.txt` (154) · `Lei nº 10.522.txt` (164) |
| 13 | Lei nº 8.981, de 20 de janeiro de 1995 | `lei` | 2 | `Lei nº 8.891.txt` (253) · `Lei nº 8.981.txt` (256) |
| 14 | Solução de Consulta Cosit nº 264, de 25 de setembro de 2019 | `solucao_de_consulta_cosit` | 2 | `Solução de Consulta Cosit nº 264, de 24 de junho de 2019.txt` (409) · `Solução de Consulta Cosit nº 264, de 25 de setembro de 2019.txt` (410) |

Two groups are duplicates only because the **dataset filename is wrong**, and the canonical
extraction recovered the real identity from the file contents:

- Group 13 — `Lei nº 8.891.txt` contains `LEI Nº 8.981, DE 20 DE JANEIRO DE 1995`
  (the filename digit transposition 8.981 → 8.891).
- Group 14 — `Solução de Consulta Cosit nº 264, de 24 de junho de 2019.txt` contains the
  25/09/2019 act; the June date in the filename does not exist.

Group 4 is the widest collapse: three different treaty names all promulgated by the single
Decreto nº 52.288/1963.

## Answer 2 — coverage of the 462 unique documents

| | Count |
|---|---:|
| Unique canonical documents | 462 |
| **Present on disk as `.docx`** | **460** (99.6%) |
| **Still missing** | **2** |

The 460 present documents are served by **458 distinct files** — two files each satisfy two
canonical records (see "Files serving two records" below). Of the 461 `.docx` on disk, 458
are matched and 3 are unmatched (see "Unmatched files").

### Coverage by type

| `type_slug` | unique | fetched | decretos | receita | manual | missing |
|---|---:|---:|---:|---:|---:|---:|
| `ato_declaratorio_comum_cosar` | 1 | | | 1 | | |
| `ato_declaratorio_comum_cosit` | 1 | | | 1 | | |
| `ato_declaratorio_comum_pgfn` | 15 | | | 14 | 1 | |
| `ato_declaratorio_comum_presidencia_da_mesa_do_congresso_nacional` | 1 | | | | 1 | |
| `ato_declaratorio_comum_srf` | 7 | | | 7 | | |
| `ato_declaratorio_executivo_codac` | 1 | | | 1 | | |
| `ato_declaratorio_executivo_cosit` | 1 | | | 1 | | |
| `ato_declaratorio_executivo_rfb` | 2 | | | 2 | | |
| `ato_declaratorio_executivo_srf` | 1 | | | 1 | | |
| `ato_declaratorio_interpretativo_rfb` | 3 | | | 3 | | |
| `ato_declaratorio_interpretativo_srf` | 9 | | | 9 | | |
| `ato_declaratorio_normativo_cosit` | 6 | | | 6 | | |
| `ato_declaratorio_normativo_cst` | 7 | | | 5 | 2 | |
| `circular_banco_central` | 1 | | | | 1 | |
| `constituicao_federal` | 1 | | | | 1 | |
| `decreto` | 34 | | 33 | | 1 | |
| `decreto_lei` | 12 | | 12 | | | |
| `despacho` | 1 | | | 1 | | |
| `instrucao_normativa_rfb` | 24 | | | 22 | 2 | |
| `instrucao_normativa_srf` | 16 | | | 14 | 2 | |
| `jurisprudencia_acordao_re_stf` | 1 | | | | 1 | |
| `jurisprudencia_adi_stf` | 2 | | | | 2 | |
| `jurisprudencia_resp_stj` | 1 | | | | 1 | |
| `lei` | 106 | 106 | | | | |
| `lei_complementar` | 2 | 2 | | | | |
| `medida_provisoria` | 7 | | | | 7 | |
| `nota_pgfn` | 5 | | | 2 | 3 | |
| `nota_sei` | 1 | | | | 1 | |
| `outros` | 8 | | | | 8 | |
| `parecer` | 1 | | | | 1 | |
| `parecer_cosit` | 1 | | | 1 | | |
| `parecer_normativo` | 1 | | | | 1 | |
| `parecer_normativo_cosit` | 7 | | | 7 | | |
| `parecer_normativo_cst` | 24 | | | 15 | 9 | |
| `parecer_pgfn` | 5 | | | 1 | 4 | |
| `parecer_pgfncat` | 2 | | | | 2 | |
| `parecer_sei` | 4 | | | | 4 | |
| `portaria_conjunta` | 1 | | | | 1 | |
| `portaria_mf` | 3 | | | 3 | | |
| `resolucao_cgpc` | 1 | | | | 1 | |
| `resolucao_cgsn` | 1 | | | 1 | | |
| `resolucao_tse` | 1 | | | | 1 | |
| `solucao_de_consulta` | 2 | | | 2 | | |
| `solucao_de_consulta_cosit` | 109 | | | 109 | | |
| `solucao_de_consulta_interna_cosit` | 13 | | | 12 | | **1** |
| `solucao_de_divergencia_cosit` | 4 | | | 3 | 1 | |
| `sumula_carf` | 1 | | | | 1 | |
| `sumula_stj` | 2 | | | | 2 | |
| `tratados_convencoes` | 2 | | | | 1 | **1** |
| **Total** | **462** | **108** | **45** | **244** | **63** | **2** |

(`manual` = 63 records served by 61 distinct files.)

Every category A/B/C of the previous report is now closed except the two entries below —
the manual round supplied all 30 "no fetch pipeline" documents, all 16 undated references,
and 17 of the 18 failed fetches.

### The 2 documents still missing

| # | Document | `type_slug` | Dataset filename | Why it is still open |
|---:|---|---|---|---|
| 1 | Convenção de Berna da União Postal Universal (UPU) | `tratados_convencoes` | `Convenção de Berna da União Postal Universal (UPU).txt` | No act number and no date; the dataset's own `filedata` for this entry is a **Wikipedia article** about the UPU (8 110 chars of nav chrome + prose), not a treaty text. There is no Brazilian normative act to fetch unless the target is redefined as the promulgating decree of a specific UPU act. |
| 2 | Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006 | `solucao_de_consulta_interna_cosit` | `Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006.txt` | **The canonical record is mislabelled.** The dataset's `filedata` for this file is the normas.leg.br page of **`Ato Declaratório Executivo Cosit nº 5, de 24 de fevereiro de 2006`** (DOU de 06/03/2006), not a Solução de Consulta Interna. No SCI Cosit nº 5 dated 28/03/2006 exists on the portal, which is why the fetcher never resolved it. |

**Recommended action for #2:** re-key the canonical record to
`type_slug = ato_declaratorio_executivo_cosit`, `number = 5`, `date = 24 de fevereiro de 2006`
and re-run `python fetch_receita_normas_main.py --only ato_declaratorio_executivo_cosit`.
That folder currently holds only `ade_cosit_30_20010723.docx`, so the act is genuinely absent
and the existing pipeline should retrieve it unchanged.

## Findings worth recording

### Files serving two canonical records

| File | Canonical records served |
|---|---|
| `output_manual/documents/parecer_sei_110_2018.docx` | `Parecer SEI nº 110, de 26 de agosto de 2020` (idx 334) and `Parecer SEI nº 110` (idx 336) |
| `output_manual/documents/pn_cst_129_19730913.docx` | `Parecer Normativo CST nº 129, de 13 de setembro de 1973` and `Parecer Normativo nº 129, de 13 de setembro de 1973` |

Both pairs are the *same* act under two canonical names, so the de-duplication key
`(type_slug, number, date, canonical_name)` slightly over-counts. The Parecer SEI pair
differs only in that one dataset filename carries the approving despacho's date
(26/08/2020) while the act itself is `PARECER SEI Nº 110/2018/CRJ/PGACET/PGFN-MF`; the
Parecer Normativo pair differs only in whether the órgão `CST` was written out. A stricter
key of `(type_slug-family, number, act date)` would make the unique count **460**.

### Unmatched files on disk (3)

| File | Status |
|---|---|
| `fetched_documents/documents/lei_3071_19160101.docx` | Código Civil de 1916 — cited only indirectly, no canonical record. Already noted in the previous report. |
| `fetched_documents/documents/lei_5869_19730111.docx` | CPC de 1973 — same situation. |
| `output_manual/documents/sci_cosit_20130215.docx` | **Redundant.** Its content is `Solução de Consulta Interna Cosit nº 5, de 15 de fevereiro de 2013`, i.e. canonical index 465, which is already served by `output_receita_federal/solucao_de_consulta_interna_cosit/documents/sci_cosit_5_20130215.docx` (42 KB, full text with the Relatório) — the manual copy is a 14 KB ementa-only extract of the same act. It does **not** cover the missing 28/03/2006 record. Safe to delete. |

The 14 stale `lei_*.docx` duplicates flagged in the previous report are gone: the folder went
from 129 to 110 files, the misfiled LC 109 / LC 123 now carry the `lei_comp_` prefix, and
`lei_1535_19770413.docx` is now `output_decretos/documents/decreto_lei_1535_19770413.docx`.

### Date and identity discrepancies confirmed by opening the `.docx`

None of these block coverage; they are canonical-metadata defects worth fixing at the source.

| Canonical record | On disk | Discrepancy |
|---|---|---|
| `Decreto-Lei nº 1.535, de 15 de abril de 1977` | `decreto_lei_1535_19770413.docx` | Act text reads *"DE 13 DE ABRIL DE 1977"*. The canonical date (15/04) is wrong. |
| `Instrução Normativa RFB nº 1.131, de 20 de fevereiro de 2011` | `in_rfb_1131_20110221.docx` | Act text reads *"DE 21/02/2011"* (DOU 22/02). Canonical date off by one day. |
| `Ato Declaratório Normativo CST nº 16, de 27 de julho de 1979` | `adn_cst_16_19790627.docx` | Canonical date is right (*"nº 16 de 27/07/1979"* in the document); the **filename** carries `19790627` instead of `19790727`. Renaming it would let rule 1 match it without the hand mapping. |
| `Instrução Normativa RFB nº 67` (undated) | `in_srf_67_19880421.docx` | The dataset content is **IN SRF nº 67 de 21/04/1988** — the órgão in the canonical record (`RFB`) is wrong; it should be `instrucao_normativa_srf`, date 1988-04-21. |
| `Parecer PGFNCAT nº 815` (undated) | `parecer_pgfncat_815_2010_nota_pgfn_crj_981_2015.docx` | The dataset's own `filedata` for `Parecer PGFNCAT nº 815 2010.txt` is **Nota PGFN/CRJ nº 981/2015**, which merely *cites* Parecer PGFN/CAT nº 815/2010. The manual file faithfully reproduces what the dataset holds; the Parecer's own text is not in the corpus (by dataset design, not by omission). |
| `Resolução TSE nº 22.250` (undated) | `resol_tse_22_20060523.docx` | **Mismatch — needs review.** The file is `RESOLUÇÃO TSE Nº 22.205` (*"Regulamenta a Lei nº 11.300… propaganda, financiamento e prestação de contas"*, 23/05/2006). The dataset text (a TSE portal index dump listing ~28 resolutions) names 22.250 as *"Dispõe sobre a arrecadação e a aplicação de recursos nas campanhas eleitorais e sobre a prestação de contas nas eleições"* — a related but different act. Either re-fetch Res. TSE nº 22.250 or record 22.205 as a deliberate substitution. |

## Reproducing this audit

The audit script is not committed; it is ~100 lines and reconstructible from the "Method"
section. Its two inputs are `output_canonical/canonical_referred_documents.json` and a
`ls *.docx` of the four folders, and its only project dependency is
`receita_norma_fetcher.ACT_TYPES` for the `type_slug → file_prefix` table. The hand-verified
mapping for the 36 `output_manual` files is the only part that cannot be regenerated
mechanically — it is embedded in the tables above.
