# Bronze profile

30 files in `data/bronze/prices`.

## Overview per region

Files, rows and date range. Big swings in rows per file can mean partial scrapes.

| region | files | rows | first_day | last_day | avg_rows_per_file |
|---|---|---|---|---|---|
| bavaria | 15 | 447153 | 2025-08-25 | 2025-09-08 | 29810.0 |
| schleswig-holstein | 15 | 244998 | 2025-08-25 | 2025-09-08 | 16333.0 |

## Smallest and largest files

Outliers in row count. A file far below the average is probably incomplete.

| kind | region | snapshot_date | rows | pct_of_avg |
|---|---|---|---|---|
| smallest | schleswig-holstein | 2025-08-25 | 15800 | 97.0 |
| smallest | schleswig-holstein | 2025-08-30 | 15920 | 97.0 |
| smallest | schleswig-holstein | 2025-09-07 | 16040 | 98.0 |
| smallest | schleswig-holstein | 2025-09-08 | 16160 | 99.0 |
| smallest | schleswig-holstein | 2025-09-06 | 16320 | 100.0 |
| largest | bavaria | 2025-08-25 | 30280 | 102.0 |
| largest | bavaria | 2025-09-01 | 30240 | 101.0 |
| largest | bavaria | 2025-09-02 | 30160 | 101.0 |
| largest | bavaria | 2025-09-03 | 29920 | 100.0 |
| largest | bavaria | 2025-08-26 | 29920 | 100.0 |

## Missing days

Days without a file between a region's first and last day. A product absent on these days is unknown, not delisted.

_no rows_

## Duplicate EANs inside one file

If one EAN appears several times in the same day/region, the product is probably listed in more than one category (then category is many-to-many).

| duplicate_groups | extra_rows | differ_in_category | differ_in_price | differ_in_name |
|---|---|---|---|---|
| 105910 | 119885 | 105712 | 0 | 2 |

## Duplicate EAN examples

A few concrete cases, latest snapshot first.

| region | snapshot_date | ean | categories | prices | name |
|---|---|---|---|---|---|
| bavaria | 2025-09-08 | 8700216670647 | Babybedarf \| Monats-Highlights | 8.75 | Pampers Baby-Dry Pants Gr.7 17+kg 18 Stück |
| bavaria | 2025-09-08 | 4062300260795 | Monats-Highlights \| Babybedarf | 1.65 | Hipp Karotten mit Mais & Bio-Kalb 190g |
| bavaria | 2025-09-08 | 4018852036333 | Monats-Highlights \| Babybedarf | 1.15 | Bebivita Bio Früchtebrei Pfirsich mit Maracuja in Apfel 250g |
| bavaria | 2025-09-08 | 4062300289437 | Monats-Highlights \| Babybedarf | 3.79 | Hipp Bio Apfel-Banane & Babykeks 4x90g |
| bavaria | 2025-09-08 | 4065331001122 | Babybedarf \| Drogerie & Kosmetik \| Monats-Highlights | 1.79 | Bübchen Shampoo & Duschgel Himbeerspaß 230ml |
| bavaria | 2025-09-08 | 8700216669832 | Monats-Highlights \| Babybedarf | 8.75 | Pampers Night Pants Gr.6 15+kg 18 Stück |
| bavaria | 2025-09-08 | 4018852036012 | Monats-Highlights \| Babybedarf | 1.45 | Bebivita Mini-Makkaroni mit buntem Rahmgemüse 250g |
| bavaria | 2025-09-08 | 4001499908347 | Babybedarf \| Monats-Highlights \| Küche & Haushalt | 2.99 | Frosch Baby Spül-Reiniger 500ml |
| bavaria | 2025-09-08 | 4062300265967 | Monats-Highlights \| Babybedarf | 1.75 | Hipp Bio Pasta Bambini Gemüse-Lasagne 220g |
| bavaria | 2025-09-08 | 4065331003683 | Drogerie & Kosmetik \| Babybedarf | 1.79 | Bübchen Shampoo & Duschgel Bisasam 230ml |

## Pagination fingerprint

Rows per (file, category). If nearly all are multiples of 40, the source was scraped 40 products per page, and the last partial page of a category may be missing.

| region | category_files | multiple_of_40 | pct | min_rows | max_rows |
|---|---|---|---|---|---|
| bavaria | 300 | 299 | 99.7 | 280 | 3480 |
| schleswig-holstein | 300 | 298 | 99.3 | 40 | 2800 |

## Duplicates inside the same category

Same EAN twice in one category on one day: another sign of page overlap while scraping.

| groups | extra_rows | categories_affected | example_category |
|---|---|---|---|
| 268 | 268 | 11 | Käse, Eier & Molkerei |

## Gaps between appearances

For each product and region: how many snapshots pass between two appearances. 1 = seen on consecutive snapshots. Short gaps followed by a return are probably scraping misses; this sets max_gap_snapshots in dbt_project.yml.

| snapshots_between | occurrences | pct |
|---|---|---|
| 1 | 521587 | 98.58 |
| 2 | 3511 | 0.66 |
| 3 | 1745 | 0.33 |
| 4 | 739 | 0.14 |
| 5 | 528 | 0.1 |
| 6+ | 1015 | 0.19 |

## EAN shape

EANs must be stored as text. Length 8 and 13 are normal (EAN-8 / EAN-13); anything else, or non-digits, needs a look.

| ean_length | only_digits | rows | distinct_eans | example |
|---|---|---|---|---|
| 13 | True | 651082 | 29816 | 8719449078243 |
| 8 | True | 37745 | 1723 | 22590541 |
| 11 | True | 2180 | 131 | 24000012559 |
| 12 | True | 1144 | 65 | 898999000503 |

## Distinct products

How many products exist, and how many appear in both regions.

| distinct_eans | in_both_regions | in_one_region |
|---|---|---|
| 31735 | 11406 | 20329 |

## Price column

Prices are text in bronze. Values that fail to parse as a number need handling.

| rows | empty | unparseable | min_price | max_price | bad_example |
|---|---|---|---|---|---|
| 692151 | 0 | 0 | 0.10 | 155.00 |  |

## How often prices change

Per product and region: number of distinct prices over the whole period. This shows how much the price-interval model will compress the data.

| distinct_prices | products | pct |
|---|---|---|
| 1 | 36715 | 85.1 |
| 2 | 6314 | 14.6 |
| 3 | 112 | 0.3 |

## Same EAN, different names

Products renamed over time. Decides whether dim_product needs name history.

| eans_with_several_names | example |
|---|---|
| 41 | Somat Excellence 4in1 47 Spülmaschinentabs 893g \| Somat Excellence 4in1 Caps 47 Spülmaschinentabs 893g |

## Sale column

Expected values: True / False.

| sale | rows |
|---|---|
| False | 655804 |
| True | 36347 |

## Brand column

'NA' (and empty) should become NULL in silver.

| brand_kind | rows |
|---|---|
| real brand | 641674 |
| NA | 50477 |

## Top brands

Most frequent brands on the latest snapshot.

| brand | products |
|---|---|
| NA | 3335 |
| REWE Beste Wahl | 1940 |
| ja! | 1900 |
| REWE Bio | 1510 |
| Vivess | 796 |
| Dr. Oetker | 670 |
| Maggi | 448 |
| ZooRoyal | 448 |
| Hipp | 410 |
| Knorr | 409 |
| NIVEA | 331 |
| REWE Feine Welt | 317 |
| Ostmann | 308 |
| Today | 299 |
| Wilhelm Brandenburg | 268 |

## Categories

Products per category on each region's latest snapshot.

| category | region | products |
|---|---|---|
| Babybedarf | bavaria | 600 |
| Babybedarf | schleswig-holstein | 200 |
| Bewusste Ernährung | bavaria | 1760 |
| Bewusste Ernährung | schleswig-holstein | 1000 |
| Brot, Cerealien & Aufstriche | bavaria | 1680 |
| Brot, Cerealien & Aufstriche | schleswig-holstein | 960 |
| Drogerie & Kosmetik | bavaria | 2640 |
| Drogerie & Kosmetik | schleswig-holstein | 1040 |
| Fertiggerichte & Konserven | bavaria | 2400 |
| Fertiggerichte & Konserven | schleswig-holstein | 1080 |
| Fleisch & Fisch | bavaria | 1160 |
| Fleisch & Fisch | schleswig-holstein | 800 |
| Getränke & Genussmittel | bavaria | 3440 |
| Getränke & Genussmittel | schleswig-holstein | 2760 |
| Grillsaison | bavaria | 680 |
| Grillsaison | schleswig-holstein | 560 |
| Haus & Freizeit | bavaria | 600 |
| Haus & Freizeit | schleswig-holstein | 280 |
| Kaffee, Tee & Kakao | bavaria | 840 |
| Kaffee, Tee & Kakao | schleswig-holstein | 480 |
| Kochen & Backen | bavaria | 1360 |
| Kochen & Backen | schleswig-holstein | 600 |
| Käse, Eier & Molkerei | bavaria | 2000 |
| Käse, Eier & Molkerei | schleswig-holstein | 1200 |
| Küche & Haushalt | bavaria | 1480 |
| Küche & Haushalt | schleswig-holstein | 600 |
| Monats-Highlights | bavaria | 1840 |
| Monats-Highlights | schleswig-holstein | 1080 |
| Obst & Gemüse | bavaria | 280 |
| Obst & Gemüse | schleswig-holstein | 240 |
| Regional | bavaria | 320 |
| Regional | schleswig-holstein | 40 |
| Süßes & Salziges | bavaria | 2640 |
| Süßes & Salziges | schleswig-holstein | 1240 |
| Tiefkühlkost | bavaria | 960 |
| Tiefkühlkost | schleswig-holstein | 800 |
| Tierbedarf | bavaria | 1080 |
| Tierbedarf | schleswig-holstein | 480 |
| Öle, Soßen & Gewürze | bavaria | 1960 |
| Öle, Soßen & Gewürze | schleswig-holstein | 720 |

## Grammage patterns

Numbers replaced by N, so we can see which formats the parser must handle.

| pattern | rows | example |
|---|---|---|
| Ng (N kg = N €) | 357452 | 500g (1 kg = 2,98 €) |
| Nml (N l = N €) | 86542 | 230ml (1 l = 7,35 €) |
| Nl (N l = N €) | 66344 | 0,25l (1 l = 5,56 €) |
| N Stück | 61499 | 1 Stück |
| Ng | 31743 | 130g |
| NxNl (N l = N €) | 20061 | 6x0,33l (1 l = 3,03 €) |
| Nl | 19372 | 1l |
| NxNg (N kg = N €) | 17628 | 4x90g (1 kg = 7,36 €) |
| N Stück ca. N g (N kg = N €) | 7955 | 1 Stück ca. 200 g (1 kg = 1,99 €) |
| Nml | 7589 | 200ml |
| NxN Stück | 3753 | 3x48 Stück |
| NxNml (N l = N €) | 3363 | 9x55ml (1 l = 4,48 €) |
| Nkg | 2755 | 1kg |
| Nkg (N kg = N €) | 2687 | 2,50kg (1 kg = 0,96 €) |
| NA | 1409 | NA |
| Nm (N m  = N €) | 658 | 50m (1 m  = 0,04 €) |
| NxNg | 500 | 3x6g |
| Nm (N m = N €) | 268 | 66m (1 m = 0,08 €) |
| NxNl | 186 | 4x0,25l |
| Nm | 117 | 50m |
| NxNcm (N m = N €) | 53 | 20x6cm (1 m = 0,66 €) |
| NxNm (N m  = N €) | 45 | 10x10m (1 m  = 0,04 €) |
| NxNml | 43 | 3x65ml |
| NxNxNl (N l = N €) | 36 | 4x6x0,33l (1 l = 2,52 €) |
| NxNm (N m = N €) | 30 | 2x50m (1 m = 0,02 €) |
| Nl (N kg = N €) | 30 | 0,33l (1 kg = 4,70 €) |
| Ng (N l = N €) | 18 | 150g (1 l = 15,89 €) |
| Ng (N m = N €) | 15 | 56g (1 m = 0,88 €) |

## Unit price inside grammage

Share of rows with a '(1 kg = 3,96 €)'-style unit price, by base unit.

| base_unit | rows | pct | example |
|---|---|---|---|
| kg | 385752 | 55.7 | 500g (1 kg = 3,38 €) |
| l | 176364 | 25.5 | 230ml (1 l = 7,35 €) |
| <none> | 128966 | 18.6 | 1 Stück |
| m | 1069 | 0.2 | 20x6cm (1 m = 0,66 €) |

## Image column

Only checked, not used: we won't hotlink product images on a public site.

| empty_images | image_hosts |
|---|---|
| 0 | 1 |
