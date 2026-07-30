# Documents Still Missing — BR-TaxQA-R Referred Legal Documents

Generated: 2026-07-30 01:01:59

## Method

Every record in `output_canonical/canonical_referred_documents.json` (478 references) was
de-duplicated on `(type_slug, number, date, canonical_name)` and matched against the `.docx`
files present in:

- `fetched_documents/documents/` — `lei`
- `output_decretos/documents/` — `decreto`, `decreto_lei` (matched on the filename type prefix)
- `output_receita_federal/<type_slug>/documents/` — every Receita Federal act type

Match key is the filename convention `<prefix>_<number>_<YYYYMMDD>.docx`: document number with
thousand separators stripped, plus the canonical date normalized to `YYYYMMDD`. Numbered-suffix
duplicates (`..._1.docx`) and `_nodate` files are recognized. For canonical records with no date,
a number-only match within the correct type folder is accepted.

## Summary

| | Count |
|---|---:|
| Canonical references | 478 |
| Unique documents after de-duplication | 462 |
| **Present on disk as `.docx`** | **395** |
| Already on disk but filed under the wrong type | 3 |
| **Still to fetch** | **64** |

Breakdown of the documents still to fetch:

| Category | Count |
|---|---:|
| A. Fetch attempted and failed (pipeline exists) | 18 |
| B. Undated canonical reference — cannot be matched by date | 16 |
| C. No fetch pipeline for the document type | 30 |
| **Total** | **64** |

## A. Fetch attempted and failed — pipeline exists

18 documents. The type already has a working fetcher and the canonical record has
a usable number and date, but no `.docx` was produced. The error column is the reason recorded in
the run's `metadata/needs_review.json`. "none matched" means the portal returned candidates whose
tipo/number/órgão/date did not verify against the canonical act — usually an órgão mismatch or a
canonical date that is off by a few days from the DOU date.

| # | Document | Type slug | Number | Date | Pipeline | Recorded error |
|---:|---|---|---:|---|---|---|
| 1 | Ato Declaratório PGFN nº 1, de 2 de janeiro de 2014 | `ato_declaratorio_comum_pgfn` | 1 | 2014-01-02 | Receita Federal sijut2consulta | 7 candidate(s) found, none matched órgão=PGFN/number=1/date=2014-01-02 |
| 2 | Ato Declaratório Normativo CST nº 16, de 27 de julho de 1979 | `ato_declaratorio_normativo_cst` | 16 | 1979-07-27 | Receita Federal sijut2consulta | 2 candidate(s) found, none matched órgão=CST/number=16/date=1979-07-27 |
| 3 | Instrução Normativa RFB nº 1.131, de 20 de fevereiro de 2011 | `instrucao_normativa_rfb` | 1.131 | 2011-02-20 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=RFB/number=1131/date=2011-02-20 |
| 4 | Instrução Normativa SRF nº 23, de 25 de março de 1983 | `instrucao_normativa_srf` | 23 | 1983-03-25 | Receita Federal sijut2consulta | 25 candidate(s) found, none matched órgão=SRF/number=23/date=1983-03-25 |
| 5 | Instrução Normativa SRF nº 84, de 20 de dezembro de 1979 | `instrucao_normativa_srf` | 84 | 1979-12-20 | Receita Federal sijut2consulta | 17 candidate(s) found, none matched órgão=SRF/number=84/date=1979-12-20 |
| 6 | Parecer Normativo nº 129, de 13 de setembro de 1973 | `parecer_normativo` | 129 | 1973-09-13 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=None/number=129/date=1973-09-13 |
| 7 | Parecer Normativo CST nº 32, de 17 de agosto de 1981 | `parecer_normativo_cst` | 32 | 1981-08-17 | Receita Federal sijut2consulta | No idAto returned by search |
| 8 | Parecer Normativo CST nº 36, de 30 de maio de 1977 | `parecer_normativo_cst` | 36 | 1977-05-30 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=CST/number=36/date=1977-05-30 |
| 9 | Parecer Normativo CST nº 44, de 30 de junho de 1976 | `parecer_normativo_cst` | 44 | 1976-06-30 | Receita Federal sijut2consulta | 3 candidate(s) found, none matched órgão=CST/number=44/date=1976-06-30 |
| 10 | Parecer Normativo CST nº 68, de 14 de setembro de 1976 | `parecer_normativo_cst` | 68 | 1976-09-14 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=CST/number=68/date=1976-09-14 |
| 11 | Parecer Normativo CST nº 90, de 16 de outubro de 1978 | `parecer_normativo_cst` | 90 | 1978-10-16 | Receita Federal sijut2consulta | No idAto returned by search |
| 12 | Parecer Normativo CST nº 122, de 8 de junho de 1974 | `parecer_normativo_cst` | 122 | 1974-06-08 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=CST/number=122/date=1974-06-08 |
| 13 | Parecer Normativo CST nº 129, de 13 de setembro de 1973 | `parecer_normativo_cst` | 129 | 1973-09-13 | Receita Federal sijut2consulta | 1 candidate(s) found, none matched órgão=CST/number=129/date=1973-09-13 |
| 14 | Parecer Normativo CST nº 250, de 15 de março de 1971 | `parecer_normativo_cst` | 250 | 1971-03-15 | Receita Federal sijut2consulta | No idAto returned by search |
| 15 | Parecer PGFNCAT nº 1.503, de 19 de julho de 2010 | `parecer_pgfncat` | 1.503 | 2010-07-19 | Receita Federal sijut2consulta | No idAto returned by search |
| 16 | Parecer SEI nº 110, de 26 de agosto de 2020 | `parecer_sei` | 110 | 2020-08-26 | Receita Federal sijut2consulta | No idAto returned by search |
| 17 | Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006 | `solucao_de_consulta_interna_cosit` | 5 | 2006-03-28 | Receita Federal sijut2consulta | 14 candidate(s) found, none matched órgão=Cosit/number=5/date=2006-03-28 |
| 18 | Solução de Divergência Cosit nº 16, de 27 de setembro de 2012 | `solucao_de_divergencia_cosit` | 16 | 2012-09-27 | Receita Federal sijut2consulta | 3 candidate(s) found, none matched órgão=Cosit/number=16/date=2012-09-27 |

## B. Undated canonical references

16 documents. The source text cites only the act number, so neither the search form nor
the filename can be keyed by date, and no `.docx` exists for that number in the type folder. These
need the date resolved by hand (or a number-only portal search that then disambiguates).

| # | Document | Type slug | Number | Pipeline | Recorded error |
|---:|---|---|---:|---|---|
| 1 | Ato Declaratório Normativo CST nº 11 | `ato_declaratorio_normativo_cst` | 11 | Receita Federal sijut2consulta | 3 distinct acts verified: ['5859', '5858', '5857'] |
| 2 | Decreto nº 50.656 | `decreto` | 50.656 | planalto.gov.br | Decree URL not found in index |
| 3 | Instrução Normativa RFB nº 67 | `instrucao_normativa_rfb` | 67 | Receita Federal sijut2consulta | No idAto returned by search |
| 4 | Nota PGFN CRJ nº 1.040 | `nota_pgfn` | 1.040 | Receita Federal sijut2consulta | No idAto returned by search |
| 5 | Nota PGFN CRJ nº 1.104 | `nota_pgfn` | 1.104 | Receita Federal sijut2consulta | No idAto returned by search |
| 6 | Nota SEI nº 48 | `nota_sei` | 48 | Receita Federal sijut2consulta | No idAto returned by search |
| 7 | Parecer nº 93 | `parecer` | 93 | Receita Federal sijut2consulta | No idAto returned by search |
| 8 | Parecer Normativo CST nº 25 | `parecer_normativo_cst` | 25 | Receita Federal sijut2consulta | No idAto returned by search |
| 9 | Parecer PGFN nº 701 | `parecer_pgfn` | 701 | Receita Federal sijut2consulta | No idAto returned by search |
| 10 | Parecer PGFN nº 1.888 | `parecer_pgfn` | 1.888 | Receita Federal sijut2consulta | No idAto returned by search |
| 11 | Parecer PGFN nº 2.118 | `parecer_pgfn` | 2.118 | Receita Federal sijut2consulta | No idAto returned by search |
| 12 | Parecer PGFN nº 2.683 | `parecer_pgfn` | 2.683 | Receita Federal sijut2consulta | No idAto returned by search |
| 13 | Parecer PGFNCAT nº 815 | `parecer_pgfncat` | 815 | Receita Federal sijut2consulta | No idAto returned by search |
| 14 | Parecer SEI nº 110 | `parecer_sei` | 110 | Receita Federal sijut2consulta | No idAto returned by search |
| 15 | Parecer SEI nº 10.167 | `parecer_sei` | 10.167 | Receita Federal sijut2consulta | No idAto returned by search |
| 16 | Parecer SEI nº 15.069 | `parecer_sei` | 15.069 | Receita Federal sijut2consulta | No idAto returned by search |

## C. No fetch pipeline for the document type

30 documents. These types have no fetcher at all — they are not `lei`/`decreto`/
`decreto_lei` and they are not acts published on the Receita Federal norms portal. Each needs a new
source. Grouped by type:

### `outros` — 8 document(s)

Candidate source: not a normative act — obligation/form/system referenced by name only

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Declaração de Benefícios Fiscais (DFB) | — | — | `Declaração de Benefícios Fiscais (DFB).txt` |
| 2 | Declaração de Imposto de Renda Retido na Fonte (DIRF) | — | — | `Declaração de Imposto de Renda Retido na Fonte (DIRF).txt` |
| 3 | Declaração de Serviços Médicos e de Saúde (Dmed) | — | — | `Declaração de Serviços Médicos e de Saúde (Dmed).txt` |
| 4 | Declaração de informações sobre Atividades Imobiliárias (Dimob) | — | — | `Declaração de informações sobre Atividades Imobiliárias (Dimob).txt` |
| 5 | Declaração sobre Operações Imobiliárias (DOI) | — | — | `Declaração sobre Operações Imobiliárias (DOI).txt` |
| 6 | Documento de Informação e Apuração do ITR (Diat) | — | — | `Documento de Informação e Apuração do ITR (Diat).txt` |
| 7 | Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão) | — | — | `Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão).txt` |
| 8 | PMF nº 80 | 80 | — | `PMF nº 80, de 1979.txt` |

### `medida_provisoria` — 7 document(s)

Candidate source: planalto.gov.br / normas.leg.br — LexML URN `medida.provisoria`

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Medida Provisória nº 252, de 15 de junho de 2005 | 252 | 2005-06-15 | `Medida Provisória nº 252.txt` |
| 2 | Medida Provisória nº 497, de 27 de julho de 2010 | 497 | 2010-07-27 | `Medida Provisória nº 497, de 27 de julho de 2010.txt` |
| 3 | Medida Provisória nº 670, de 10 de março de 2015 | 670 | 2015-03-10 | `Medida Provisória nº 670, de 10 de março de 2015.txt` |
| 4 | Medida Provisória nº 2.228-1, de 6 de setembro de 2001 | 2.228-1 | 2001-09-06 | `Medida Provisória nº 2.228.txt` |
| 5 | Medida Provisória nº 2.158-35, de 24 de agosto de 2001 | 2.158-35 | 2001-08-24 | `Medida Provisória nº 2.158.txt` |
| 6 | Medida Provisória nº 2.159-70, de 24 de agosto de 2001 | 2.159-70 | 2001-08-24 | `Medida Provisória nº 2.159.txt` |
| 7 | Medida Provisória nº 2.189-49, de 23 de agosto de 2001 | 2.189-49 | 2001-08-23 | `Medida Provisória nº 2.189.txt` |

### `jurisprudencia_adi_stf` — 2 document(s)

Candidate source: portal.stf.jus.br case law (not a normative act)

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Ação Direta de Inconstitucionalidade (ADI) nº 5.422 | 5.422 | — | `Ação Direta de Inconstitucionalidade (ADI) nº 5.422, do Supremo Tribunal Federal.txt` |
| 2 | Ação Direta de Inconstitucionalidade nº 5.583 | 5.583 | — | `Ação Direta de Inconstitucionalidade nº 5.583DF do Supremo Tribunal Federal (STF).txt` |

### `sumula_stj` — 2 document(s)

Candidate source: scon.stj.jus.br súmulas

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Súmula nº 125 | 125 | — | `Súmula nº 125 do Superior Tribunal de Justiça (STJ).txt` |
| 2 | Súmula nº 136 | 136 | — | `Súmula nº 136 do Superior Tribunal de Justiça (STJ).txt` |

### `tratados_convencoes` — 2 document(s)

Candidate source: treaty text — promulgating decree on planalto.gov.br, or MRE Concórdia

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Acordo para Evitar a Dupla Tributação em Matéria de Impostos sobre a Renda e o Capital firmado entre o Brasil e a Alemanha | — | — | `Acordo para Evitar a Dupla Tributação em Matéria de Impostos sobre a Renda e o Capital firmado entre o Brasil e a Alemanha.txt` |
| 2 | Convenção de Berna da União Postal Universal (UPU) | — | — | `Convenção de Berna da União Postal Universal (UPU).txt` |

### `ato_declaratorio_comum_presidencia_da_mesa_do_congresso_nacional` — 1 document(s)

Candidate source: congresso/planalto — issued by the Congress Board, not by the Receita Federal

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Ato Declaratório do Presidente da Mesa do Congresso Nacional nº 38, de 14 de outubro de 2005 | 38 | 2005-10-14 | `Ato Declaratório do Presidente da Mesa do Congresso Nacional nº 38, de 14 de outubro de 2005.txt` |

### `circular_banco_central` — 1 document(s)

Candidate source: bcb.gov.br normativos search

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Circular do Banco Central do Brasil nº 3.432, de 3 de fevereiro de 2009 | 3.432 | 2009-02-03 | `Circular do Banco Central do Brasil nº 3.432, de 3 de fevereiro de 2009.txt` |

### `constituicao_federal` — 1 document(s)

Candidate source: planalto.gov.br (constituicao/constituicao.htm)

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Constituição da República Federativa do Brasil de 1988 | — | — | `Constituição Federal de 1988.txt` |

### `jurisprudencia_acordao_re_stf` — 1 document(s)

Candidate source: portal.stf.jus.br case law (not a normative act)

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Acórdão do RE nº 855.091 | 855.091 | — | `Acórdão do RE nº 855.091RS (Tema 808).txt` |

### `jurisprudencia_resp_stj` — 1 document(s)

Candidate source: scon.stj.jus.br case law (not a normative act)

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | REsp nº 1.306.393 | 1.306.393 | — | `REsp nº 1.306.393DF_ Tema Repetitivo nº 535.txt` |

### `portaria_conjunta` — 1 document(s)

Candidate source: Receita/TSE — joint act, not in the sijut2consulta órgão facets

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Portaria Conjunta SRFTSE nº 74, de 10 de janeiro de 2006 | 74 | 2006-01-10 | `Portaria Conjunta SRFTSE nº 74, de 10 de janeiro de 2006.txt` |

### `resolucao_cgpc` — 1 document(s)

Candidate source: gov.br/previdencia (Conselho de Gestão da Previdência Complementar)

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Resolução CGPC nº 26, de 29 de setembro de 2008 | 26 | 2008-09-29 | `Resolução CGPC nº 26, de 29 de setembro de 2008.txt` |

### `resolucao_tse` — 1 document(s)

Candidate source: tse.jus.br normative resolutions

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Resolução TSE nº 22.250 | 22.250 | — | `Resolução TSE nº 22.250, de 2006.txt` |

### `sumula_carf` — 1 document(s)

Candidate source: carf.economia.gov.br súmulas

| # | Document | Number | Date | Dataset filename |
|---:|---|---:|---|---|
| 1 | Súmula Carf nº 42 | 42 | — | `Súmula Carf nº 42.txt` |

## D. Already on disk, filed under the wrong type (no fetch needed)

3 documents. Fetched during an early `lei`-only run, so they carry the `lei_`
filename prefix and live in `fetched_documents/documents/` instead of a type-appropriate folder.
Content was opened and verified. These should be moved/renamed rather than re-fetched.

| # | Document | Expected type | File on disk | Verification |
|---:|---|---|---|---|
| 1 | Decreto-Lei nº 1.535, de 15 de abril de 1977 | `decreto_lei` | `fetched_documents/documents/lei_1535_19770413.docx` | content confirmed: "DECRETO-LEI Nº 1.535, DE 13 DE ABRIL DE 1977" — real date is 13/04/1977, canonical record says 15/04/1977 |
| 2 | Lei Complementar nº 109, de 29 de maio de 2001 | `lei_complementar` | `fetched_documents/documents/lei_109_20010529.docx` | content confirmed: "LEI COMPLEMENTAR Nº 109, DE 29 DE MAIO DE 2001" |
| 3 | Lei Complementar nº 123, de 14 de dezembro de 2006 | `lei_complementar` | `fetched_documents/documents/lei_123_20061214.docx` | content confirmed: "LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006" |

## E. Notes

### Extra `.docx` files on disk with no canonical record

`fetched_documents/documents/` holds 14 further `lei_*.docx` files that match no canonical `lei`
record. Nine of them (six distinct acts: nº 1.301, 1.381, 1.493, 2.396, 5.844, 8.795) are
decreto-leis already correctly re-fetched into `output_decretos/documents/` under the
`decreto_lei_` prefix — stale duplicates. The other five (`lei_58_19371210`,
`lei_167_19670214`, `lei_271_19670228`,
`lei_3071_19160101`, `lei_5869_19730111`) are documents cited only indirectly and not present as
canonical references. None of these affect the missing list; they are listed here only so the
folder count reconciles:

```
129 .docx in fetched_documents/documents/
 = 112 matched  -> 106 canonical `lei` documents (6 of the 112 are `_N` duplicates)
 +   3 misfiled -> section D (LC 109, LC 123, DL 1.535)
 +  14 extra    -> 9 stale decreto-lei duplicates + 5 non-canonical
```

### The `outros` bucket

The 8 `outros` entries are mostly not normative acts at all — they are tax obligations, forms and
systems (DIRF, Dmed, Dimob, DOI, DBF, Diat, Carnê-Leão) named in the answer text without an act
reference. There is nothing to fetch for these unless the intent is to fetch the instrução
normativa that creates each one. The exception is `PMF nº 80` (Portaria MF nº 80, de 1979), which
is a real act but has no date in the canonical record.

