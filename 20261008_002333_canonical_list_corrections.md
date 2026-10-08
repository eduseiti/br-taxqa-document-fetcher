# Canonical list corrections (BR-TaxQA-R v2.0 rebuild)

**Created:** 2026-10-08 00:23:33
**Requested by:** the rebuild of `../br-taxqa-r_v2.0`, step R4 of
`../br-taxqa-r_v2.0/docs/20261007_180833_corpus_fixes_and_full_rebuild_plan.md` (§3.3, item 6 of
the dataset note's §7).

## Problem

`output_canonical/canonical_referred_documents.json` maps each v1.1 reference file name to the act
it names (type, number, date). BR-TaxQA-R v2.0's dataset build finds each act's document by type +
number + date. For 27 records the list named the **wrong act**. Cosit numbers its Soluções de
Consulta per year, and the v1.1 file names had no date ("Solução de Consulta Cosit nº 50.txt"), so
the extraction picked a same-numbered act of another year. Other records had another act type or no
date. The corrections lived only in br-taxqa-r_v2.0's `reference_overrides.json`, so this list (the
fetcher's source of truth, and the input of any re-fetch) still named the wrong acts.

## Change

- `output_canonical/canonical_corrections_20261008.json`: the reviewed corrections (file name →
  fields to set, reason).
- `scripts/fix_canonical_records.py`: applies them. Each corrected record gets `source: "manual"`
  and `correction: {date, was, reason}` (`was` = the old `canonical_name`). Records whose act has no
  document get a `status`. Re-running it changes nothing. It also regenerates
  `output_canonical/by_type/*.md` and `index.md` with `extract_canonical_names`' writers.
  Re-running `extract_canonical_names.py` would **undo** the corrections; run
  `fix_canonical_records.py` after it.

```bash
python3 scripts/fix_canonical_records.py output_canonical/canonical_corrections_20261008.json
```

| Records | Correction |
|---|---|
| SC Cosit nº 7, 50, 64, 69, 75, 123, 140, 166, 173, 179, 194, 211, 214, 354 | date (and name) of the cited act instead of a same-numbered SC of another year |
| SC Cosit nº 183 | the record named SC nº 134/2014 (the text v1 held); now SC nº 183, de 25/06/2014 |
| `Lei nº 8.794.txt` | Decreto-Lei nº 8.794/1946 (was Lei 8.794/1993) |
| AD PGFN nº 2, nº 3 | 2016 acts (were 2018 / 2008; Q179 cites AD PGFN 3/2008 under another file name) |
| `Ato Declaratório RFB nº 3.txt` | ADI RFB nº 3/2016 (was ADE RFB 3/2024) |
| PN CST nº 38/1975, nº 72/1979 | full date added (24/03/1975, 18/12/1979) |
| Resolução TSE nº 22.250/2006 | date added (29/06/2006) |
| `Parecer PGFNCAT nº 815 2010.txt` | Nota PGFN/CRJ nº 981/2015, the document v1 held under this name (user decision) |
| IN RFB nº 1.997/2019 | was IN RFB 1.911/2019 |
| Convenção sobre Privilégios e Imunidades das Nações Unidas | Decreto nº 27.784/1950 (was Decreto 52.288/1963, the Specialized Agencies convention) |
| `Parecer Cosit nº 30, de 28 de setembro de 2001.txt` | `status: nonexistent_act`, `canonical_name: null` (no such act; was ADE Cosit 30/2001) |
| `Solução de Consulta Interna Cosit nº 27, de 7 de julho de 2008.txt` | `status: not_found` (cannot be found; was Solução de Divergência 27/2008) |

The corrected documents were fetched by hand into `../br-taxqa-r_v2.0/original/` (commits
`ce032e6`, `a575acc`, `7c44d73` there). The build there now resolves them from this list
(`auto_exact`). It takes each record's `correction.reason` as the `resolution_note`, and a record
with `status` resolves to no document. It also records this repository's git commit in
`dataset/build_report.json`.
