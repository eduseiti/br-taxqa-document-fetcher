# Classification Review

- Total records: 478
- Empty filedata: 0 
- Filename↔filedata TYPE mismatches: 30
- Fell back to filename parsing: 63
- 'Outros' bucket (no formal norm identified): 8
- Groups of records sharing identical filedata (capture artifacts): 15

## Records with identical filedata (data-capture artifacts)

These distinct filenames were captured with byte-identical `filedata`, so they resolve to the same canonical name. This is a source-dataset artifact, not an extraction error.

| indices | shared canonical name | filenames |
| --- | --- | --- |
| [3, 34] | Ato Declaratório PGFN nº 3, de 18 de setembro de 2008 | `Ato Declaratório (AD) PGFN nº 3, de 18 de setembro de 2008.txt`<br>`Ato Declaratório PGFN nº 3.txt` |
| [58, 227] | Decreto-Lei nº 5.452, de 1º de maio de 1943 | `Consolidação das Leis do Trabalho (CLT).txt`<br>`Lei nº 5.452.txt` |
| [63, 83] | Decreto nº 56.435, de 8 de junho de 1965 | `Convenção de Viena, Decreto nº 56.435, de 8 de junho de 1965.txt`<br>`Decreto nº 56.435.txt` |
| [64, 65, 82] | Decreto nº 52.288, de 24 de julho de 1963 | `Convenção sobre Privilégios e Imunidades das Agências Especializadas.txt`<br>`Convenção sobre Privilégios e Imunidades das Nações Unidas.txt`<br>`Decreto nº 52.288.txt` |
| [67, 153, 162] | Lei nº 10.406, de 10 de janeiro de 2002 | `Código Civil.txt`<br>`Lei n° 10.406, de 10 de janeiro de 2002 - Código Civil.txt`<br>`Lei nº 10.406.txt` |
| [68, 226] | Lei nº 5.172, de 25 de outubro de 1966 | `Código Tributário Nacional (CTN).txt`<br>`Lei nº 5.172.txt` |
| [109, 241] | Lei nº 8.069, de 13 de julho de 1990 | `Estatuto da Criança e do Adolescente (ECA).txt`<br>`Lei nº 8.069.txt` |
| [110, 114] | Instrução Normativa RFB nº 1.500, de 29 de outubro de 2014 | `IN RFB nº 1.500, de 2014.txt`<br>`Instrução Normativa RFB nº 1.500.txt` |
| [139, 149] | Instrução Normativa SRF nº 599, de 28 de dezembro de 2005 | `Instrução Normativa RFB nº 599.txt`<br>`Instrução Normativa SRF nº 599, de 28 de dezembro de 2005.txt` |
| [152, 239] | Lei nº 8.036, de 11 de maio de 1990 | `Legislação do Fundo de Garantia do Tempo de Serviço (FGTS).txt`<br>`Lei nº 8.036.txt` |
| [154, 164] | Lei nº 10.522, de 19 de julho de 2002 | `Lei n° 10.522, de 19 de julho de 2002.txt`<br>`Lei nº 10.522.txt` |
| [253, 256] | Lei nº 8.981, de 20 de janeiro de 1995 | `Lei nº 8.891.txt`<br>`Lei nº 8.981.txt` |
| [297, 326] | Parecer Normativo CST nº 129, de 13 de setembro de 1973 | `Parecer Normativo CST nº 129, de 13 de setembro de 1973.txt`<br>`Parecer Normativo nº 129, de 13 de setembro de 1973.txt` |
| [334, 336] | Parecer SEI nº 110, de 26 de agosto de 2020 | `Parecer SEI Nº 110 2018 CRJPGACETPGFN-MF, aprovado pelo Despacho nº 3482020PGFN-ME, de 26 de agosto de 2020.txt`<br>`Parecer SEI nº 110 2018 CRJPGACETPGFN-MF.txt` |
| [409, 410] | Solução de Consulta Cosit nº 264, de 25 de setembro de 2019 | `Solução de Consulta Cosit nº 264, de 24 de junho de 2019.txt`<br>`Solução de Consulta Cosit nº 264, de 25 de setembro de 2019.txt` |

## Filename vs filedata type mismatches

| idx | filename type | filedata type | canonical name | filename |
| --- | --- | --- | --- | --- |
| 0 | adi | ato declaratório interpretativo | Ato Declaratório Interpretativo RFB nº 12, de 23 de novembro de 2016 | `ADI RFB nº 12, de 2016.txt` |
| 42 | ato declaratório | ato declaratório interpretativo | Ato Declaratório Interpretativo RFB nº 18, de 6 de dezembro de 2007 | `Ato Declaratório RFB nº 18.txt` |
| 43 | ato declaratório | ato declaratório executivo | Ato Declaratório Executivo RFB nº 3, de 2 de abril de 2024 | `Ato Declaratório RFB nº 3.txt` |
| 45 | ato declaratório | ato declaratório interpretativo | Ato Declaratório Interpretativo SRF nº 26, de 26 de dezembro de 2003 | `Ato Declaratório SRF nº 26.txt` |
| 49 | ato declaratório | ato declaratório interpretativo | Ato Declaratório Interpretativo SRF nº 7, de 25 de março de 2004 | `Ato Declaratório SRF nº 7.txt` |
| 50 | ato declaratório | ato declaratório interpretativo | Ato Declaratório Interpretativo SRF nº 8, de 23 de abril de 2003 | `Ato Declaratório SRF nº 8.txt` |
| 60 | convenção | decreto | Decreto nº 9.358, de 30 de abril de 2018 | `Convenção Postal Universal.txt` |
| 62 | convenção | decreto | Decreto nº 7.030, de 14 de dezembro de 2009 | `Convenção de Viena sobre o Direito dos Tratados.txt` |
| 63 | convenção | decreto | Decreto nº 56.435, de 8 de junho de 1965 | `Convenção de Viena, Decreto nº 56.435, de 8 de junho de 1965.txt` |
| 64 | convenção | decreto | Decreto nº 52.288, de 24 de julho de 1963 | `Convenção sobre Privilégios e Imunidades das Agências Especializadas.txt` |
| 65 | convenção | decreto | Decreto nº 52.288, de 24 de julho de 1963 | `Convenção sobre Privilégios e Imunidades das Nações Unidas.txt` |
| 66 | convênio | decreto | Decreto nº 85.801, de 10 de março de 1981 | `Convênio de Criação de um Conselho de Cooperação Aduaneira.txt` |
| 69 | decisão | ato declaratório | Ato Declaratório Cosit nº 2, de 18 de janeiro de 2000 | `Decisão Cosit nº 2, de 2000.txt` |
| 155 | lei | decreto-lei | Decreto-Lei nº 1.301, de 31 de dezembro de 1973 | `Lei nº 1.301.txt` |
| 156 | lei | decreto-lei | Decreto-Lei nº 1.381, de 23 de dezembro de 1974 | `Lei nº 1.381.txt` |
| 157 | lei | decreto-lei | Decreto-Lei nº 1.493, de 7 de dezembro de 1976 | `Lei nº 1.493.txt` |
| 158 | lei | decreto-lei | Decreto-Lei nº 1.510, de 27 de dezembro de 1976 | `Lei nº 1.510.txt` |
| 159 | lei | decreto-lei | Decreto-Lei nº 1.535, de 15 de abril de 1977 | `Lei nº 1.535.txt` |
| 171 | lei | lei complementar | Lei Complementar nº 109, de 29 de maio de 2001 | `Lei nº 109.txt` |
| 201 | lei | lei complementar | Lei Complementar nº 123, de 14 de dezembro de 2006 | `Lei nº 123.txt` |
| 216 | lei | decreto-lei | Decreto-Lei nº 167, de 14 de fevereiro de 1967 | `Lei nº 167.txt` |
| 217 | lei | decreto-lei | Decreto-Lei nº 2.396, de 21 de dezembro de 1987 | `Lei nº 2.396.txt` |
| 219 | lei | decreto-lei | Decreto-Lei nº 271, de 28 de fevereiro de 1967 | `Lei nº 271.txt` |
| 227 | lei | decreto-lei | Decreto-Lei nº 5.452, de 1º de maio de 1943 | `Lei nº 5.452.txt` |
| 229 | lei | decreto-lei | Decreto-Lei nº 5.844, de 23 de setembro de 1943 | `Lei nº 5.844.txt` |
| 230 | lei | decreto-lei | Decreto-Lei nº 58, de 10 de dezembro de 1937 | `Lei nº 58.txt` |
| 251 | lei | decreto-lei | Decreto-Lei nº 8.795, de 23 de janeiro de 1946 | `Lei nº 8.795.txt` |
| 293 | parecer | ato declaratório executivo | Ato Declaratório Executivo Cosit nº 30, de 23 de julho de 2001 | `Parecer Cosit nº 30, de 28 de setembro de 2001.txt` |
| 316 | parecer normativo | ato declaratório normativo | Ato Declaratório Normativo CST nº 8, de 28 de fevereiro de 1979 | `Parecer Normativo CST nº 8, de 1979.txt` |
| 461 | solução de consulta interna | solução de divergência | Solução de Divergência Cosit nº 27, de 30 de maio de 2008 | `Solução de Consulta Interna Cosit nº 27, de 7 de julho de 2008.txt` |

## Records parsed from filename (no canonical filedata header)

| idx | canonical name | type bucket | source | filename |
| --- | --- | --- | --- | --- |
| 1 | Acordo para Evitar a Dupla Tributação em Matéria de Impostos sobre a Renda e o Capital firmado entre o Brasil e a Alemanha | Tratados e Convenções Internacionais | filename | `Acordo para Evitar a Dupla Tributação em Matéria de Impostos sobre a Renda e o Capital firmado entre o Brasil e a Alemanha.txt` |
| 2 | Acórdão do RE nº 855.091 | Jurisprudência - Acórdão/RE (STF) | filename | `Acórdão do RE nº 855.091RS (Tema 808).txt` |
| 16 | Ato Declaratório Normativo CST nº 11 | Ato Declaratório Normativo CST | filename | `Ato Declaratório Normativo CST nº 11, de 1978.txt` |
| 17 | Ato Declaratório Normativo CST nº 16, de 27 de julho de 1979 | Ato Declaratório Normativo CST | filename | `Ato Declaratório Normativo CST nº 16, de 27 de julho de 1979.txt` |
| 29 | Ato Declaratório PGFN nº 1, de 2 de janeiro de 2014 | Ato Declaratório Comum PGFN | filename | `Ato Declaratório PGFN Nº 1, de 2 de janeiro de 2014.txt` |
| 54 | Ato Declaratório do Presidente da Mesa do Congresso Nacional nº 38, de 14 de outubro de 2005 | Ato Declaratório Comum Presidência da Mesa do Congresso Nacional | filename | `Ato Declaratório do Presidente da Mesa do Congresso Nacional nº 38, de 14 de outubro de 2005.txt` |
| 55 | Ação Direta de Inconstitucionalidade (ADI) nº 5.422 | Jurisprudência - ADI (STF) | filename | `Ação Direta de Inconstitucionalidade (ADI) nº 5.422, do Supremo Tribunal Federal.txt` |
| 56 | Ação Direta de Inconstitucionalidade nº 5.583 | Jurisprudência - ADI (STF) | filename | `Ação Direta de Inconstitucionalidade nº 5.583DF do Supremo Tribunal Federal (STF).txt` |
| 57 | Circular do Banco Central do Brasil nº 3.432, de 3 de fevereiro de 2009 | Circular Banco Central | filename | `Circular do Banco Central do Brasil nº 3.432, de 3 de fevereiro de 2009.txt` |
| 61 | Convenção de Berna da União Postal Universal (UPU) | Tratados e Convenções Internacionais | filename | `Convenção de Berna da União Postal Universal (UPU).txt` |
| 70 | Declaração de Benefícios Fiscais (DFB) | Outros | filename | `Declaração de Benefícios Fiscais (DFB).txt` |
| 71 | Declaração de Imposto de Renda Retido na Fonte (DIRF) | Outros | filename | `Declaração de Imposto de Renda Retido na Fonte (DIRF).txt` |
| 72 | Declaração de Serviços Médicos e de Saúde (Dmed) | Outros | filename | `Declaração de Serviços Médicos e de Saúde (Dmed).txt` |
| 73 | Declaração de informações sobre Atividades Imobiliárias (Dimob) | Outros | filename | `Declaração de informações sobre Atividades Imobiliárias (Dimob).txt` |
| 74 | Declaração sobre Operações Imobiliárias (DOI) | Outros | filename | `Declaração sobre Operações Imobiliárias (DOI).txt` |
| 81 | Decreto nº 50.656 | Decreto | filename | `Decreto nº 50.656.txt` |
| 108 | Documento de Informação e Apuração do ITR (Diat) | Outros | filename | `Documento de Informação e Apuração do ITR (Diat).txt` |
| 140 | Instrução Normativa RFB nº 67 | Instrução Normativa RFB | filename | `Instrução Normativa RFB nº 67.txt` |
| 147 | Instrução Normativa SRF nº 23, de 25 de março de 1983 | Instrução Normativa SRF | filename | `Instrução Normativa SRF nº 23, de 25 de março de 1983.txt` |
| 178 | Lei nº 11.437 | Lei | filename | `Lei nº 11.437.txt` |
| 180 | Lei nº 11.472 | Lei | filename | `Lei nº 11.472.txt` |
| 215 | Lei nº 14.754 | Lei | filename | `Lei nº 14.754.txt` |
| 283 | Nota PGFN CRJ nº 1.040 | Nota PGFN | filename | `Nota PGFN CRJ nº 1.040 2015.txt` |
| 284 | Nota PGFN CRJ nº 1.104 | Nota PGFN | filename | `Nota PGFN CRJ nº 1.104 2017.txt` |
| 286 | Nota PGFN CRJ nº 981 | Nota PGFN | filename | `Nota PGFN CRJ nº 981 2015.txt` |
| 288 | Nota SEI nº 48 | Nota SEI | filename | `Nota SEI nº 48 2018 CRJPGACETPGFN-MF.txt` |
| 291 | PMF nº 80 | Outros | filename | `PMF nº 80, de 1979.txt` |
| 292 | Parecer Cosit nº 26, de 29 de junho de 2000 | Parecer Cosit | filename | `Parecer Cosit nº 26, de 29 de junho de 2000.txt` |
| 296 | Parecer Normativo CST nº 122, de 8 de junho de 1974 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 122, de 8 de junho de 1974.txt` |
| 297 | Parecer Normativo CST nº 129, de 13 de setembro de 1973 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 129, de 13 de setembro de 1973.txt` |
| 302 | Parecer Normativo CST nº 2, de 15 de janeiro de 1980 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 2, de 15 de janeiro de 1980.txt` |
| 303 | Parecer Normativo CST nº 25 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 25, de 1976.txt` |
| 304 | Parecer Normativo CST nº 250, de 15 de março de 1971 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 250, de 15 de março de 1971.txt` |
| 306 | Parecer Normativo CST nº 32, de 17 de agosto de 1981 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 32, de 17 de agosto de 1981.txt` |
| 307 | Parecer Normativo CST nº 36, de 30 de maio de 1977 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 36, de 30 de maio de 1977.txt` |
| 308 | Parecer Normativo CST nº 38 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 38, de 1975.txt` |
| 309 | Parecer Normativo CST nº 44, de 30 de junho de 1976 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 44, de 30 de junho de 1976.txt` |
| 314 | Parecer Normativo CST nº 68, de 14 de setembro de 1976 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 68, de 14 de setembro de 1976.txt` |
| 315 | Parecer Normativo CST nº 72 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 72, de 1979.txt` |
| 318 | Parecer Normativo CST nº 90, de 16 de outubro de 1978 | Parecer Normativo CST | filename | `Parecer Normativo CST nº 90, de 16 de outubro de 1978.txt` |
| 326 | Parecer Normativo nº 129, de 13 de setembro de 1973 | Parecer Normativo | filename | `Parecer Normativo nº 129, de 13 de setembro de 1973.txt` |
| 327 | Parecer PGFN nº 1.888 | Parecer PGFN | filename | `Parecer PGFN nº 1.888 2008.txt` |
| 328 | Parecer PGFN nº 2.118 | Parecer PGFN | filename | `Parecer PGFN nº 2118 2011.txt` |
| 329 | Parecer PGFN nº 2.683 | Parecer PGFN | filename | `Parecer PGFN nº 2683 2008.txt` |
| 330 | Parecer PGFN nº 701 | Parecer PGFN | filename | `Parecer PGFN nº 701 2016.txt` |
| 331 | Parecer PGFNCAT nº 1.503, de 19 de julho de 2010 | Parecer PGFNCAT | filename | `Parecer PGFNCAT nº 1.503, de 19 de julho de 2010, aprovado pelo Ministro de Estado da Fazenda em 26 de julho de 2010.txt` |
| 332 | Parecer PGFNCAT nº 815 | Parecer PGFNCAT | filename | `Parecer PGFNCAT nº 815 2010.txt` |
| 334 | Parecer SEI nº 110, de 26 de agosto de 2020 | Parecer SEI | filename | `Parecer SEI Nº 110 2018 CRJPGACETPGFN-MF, aprovado pelo Despacho nº 3482020PGFN-ME, de 26 de agosto de 2020.txt` |
| 335 | Parecer SEI nº 10.167 | Parecer SEI | filename | `Parecer SEI nº 10167 2021 ME.txt` |
| 336 | Parecer SEI nº 110 | Parecer SEI | filename | `Parecer SEI nº 110 2018 CRJPGACETPGFN-MF.txt` |
| 337 | Parecer SEI nº 15.069 | Parecer SEI | filename | `Parecer SEI nº 15069 2022 ME.txt` |
| 338 | Parecer nº 93 | Parecer | filename | `Parecer nº 93 2018 DECOR CGU AGU.txt` |
| 339 | Portaria Conjunta SRFTSE nº 74, de 10 de janeiro de 2006 | Portaria Conjunta | filename | `Portaria Conjunta SRFTSE nº 74, de 10 de janeiro de 2006.txt` |
| 341 | REsp nº 1.306.393 | Jurisprudência - REsp (STJ) | filename | `REsp nº 1.306.393DF_ Tema Repetitivo nº 535.txt` |
| 342 | Resolução CGPC nº 26, de 29 de setembro de 2008 | Resolução CGPC | filename | `Resolução CGPC nº 26, de 29 de setembro de 2008.txt` |
| 344 | Resolução TSE nº 22.250 | Resolução TSE | filename | `Resolução TSE nº 22.250, de 2006.txt` |
| 345 | Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão) | Outros | filename | `Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão).txt` |
| 466 | Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006 | Solução de Consulta Interna Cosit | filename | `Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006.txt` |
| 468 | Solução de Consulta Interna Cosit nº 7, de 17 de maio de 2012 | Solução de Consulta Interna Cosit | filename | `Solução de Consulta Interna Cosit nº 7, de 17 de maio de 2012.txt` |
| 473 | Solução de Divergência Cosit nº 16, de 27 de setembro de 2012 | Solução de Divergência Cosit | filename | `Solução de Divergência Cosit nº 16, de 27 de setembro de 2012.txt` |
| 475 | Súmula Carf nº 42 | Súmula CARF | filename | `Súmula Carf nº 42.txt` |
| 476 | Súmula nº 125 | Súmula STJ | filename | `Súmula nº 125 do Superior Tribunal de Justiça (STJ).txt` |
| 477 | Súmula nº 136 | Súmula STJ | filename | `Súmula nº 136 do Superior Tribunal de Justiça (STJ).txt` |

## 'Outros' bucket (needs manual canonicalization)

| idx | canonical name | filename |
| --- | --- | --- |
| 70 | Declaração de Benefícios Fiscais (DFB) | `Declaração de Benefícios Fiscais (DFB).txt` |
| 71 | Declaração de Imposto de Renda Retido na Fonte (DIRF) | `Declaração de Imposto de Renda Retido na Fonte (DIRF).txt` |
| 72 | Declaração de Serviços Médicos e de Saúde (Dmed) | `Declaração de Serviços Médicos e de Saúde (Dmed).txt` |
| 73 | Declaração de informações sobre Atividades Imobiliárias (Dimob) | `Declaração de informações sobre Atividades Imobiliárias (Dimob).txt` |
| 74 | Declaração sobre Operações Imobiliárias (DOI) | `Declaração sobre Operações Imobiliárias (DOI).txt` |
| 108 | Documento de Informação e Apuração do ITR (Diat) | `Documento de Informação e Apuração do ITR (Diat).txt` |
| 291 | PMF nº 80 | `PMF nº 80, de 1979.txt` |
| 345 | Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão) | `Sistema de Recolhimento Mensal Obrigatório (Carnê-Leão).txt` |
