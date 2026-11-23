# Bronze profile

970 files in `data/bronze/prices`.

## Overview per region

Files, rows and date range. Big swings in rows per file can mean partial scrapes.

| region | files | rows | first_day | last_day | avg_rows_per_file |
|---|---|---|---|---|---|
| bavaria | 485 | 13088249 | 2023-11-15 | 2025-09-09 | 26986.0 |
| schleswig-holstein | 485 | 7113644 | 2023-11-15 | 2025-09-08 | 14667.0 |

## Smallest and largest files

Outliers in row count. A file far below the average is probably incomplete.

| kind | region | snapshot_date | rows | pct_of_avg |
|---|---|---|---|---|
| smallest | schleswig-holstein | 2025-07-24 | 9080 | 62.0 |
| smallest | schleswig-holstein | 2024-01-11 | 10320 | 70.0 |
| smallest | schleswig-holstein | 2024-02-05 | 12240 | 83.0 |
| smallest | schleswig-holstein | 2024-01-22 | 12320 | 84.0 |
| smallest | schleswig-holstein | 2024-01-15 | 12320 | 84.0 |
| largest | bavaria | 2025-05-23 | 35680 | 132.0 |
| largest | bavaria | 2025-08-25 | 30280 | 112.0 |
| largest | bavaria | 2025-08-03 | 30280 | 112.0 |
| largest | bavaria | 2025-09-01 | 30240 | 112.0 |
| largest | bavaria | 2025-08-05 | 30240 | 112.0 |

## Missing days

Days without a file between a region's first and last day. A product absent on these days is unknown, not delisted.

| region | missing_days | dates |
|---|---|---|
| bavaria | 180 | 2023-11-16, 2024-01-11, 2024-01-13, 2024-01-19, 2024-01-24, 2024-01-30, 2024-02-03, 2024-02-10, 2024-02-17, 2024-02-2... |
| schleswig-holstein | 179 | 2023-11-16, 2024-01-13, 2024-01-19, 2024-01-24, 2024-01-29, 2024-01-30, 2024-02-03, 2024-02-10, 2024-02-17, 2024-02-2... |

## Duplicate EANs inside one file

If one EAN appears several times in the same day/region, the product is probably listed in more than one category (then category is many-to-many).

| duplicate_groups | extra_rows | differ_in_category | differ_in_price | differ_in_name |
|---|---|---|---|---|
| 2523971 | 2759388 | 2502437 | 864 | 285 |

## Duplicate EAN examples

A few concrete cases, latest snapshot first.

| region | snapshot_date | ean | categories | prices | name |
|---|---|---|---|---|---|
| bavaria | 2025-09-09 | 4337256382564 | Bewusste Ernährung \| Käse, Eier & Molkerei | 0.99 | REWE Beste Wahl High Protein Pudding Schoko 200g |
| bavaria | 2025-09-09 | 4013200105907 | Brot, Cerealien & Aufstriche \| Bewusste Ernährung | 3.99 | Liakada Olivenpaste 180g |
| bavaria | 2025-09-09 | 4260752810821 | Bewusste Ernährung \| Brot, Cerealien & Aufstriche \| Käse, Eier & Molkerei | 2.99 | EVOBAR Proteinriegel Vegan White Peanut Crunch vegan 60g |
| bavaria | 2025-09-09 | 4100130900327 | Getränke & Genussmittel \| Grillsaison \| Bewusste Ernährung | 4.99 | Beck's Blue alkoholfrei 6x0,33l |
| bavaria | 2025-09-09 | 4260372066776 | Fleisch & Fisch \| Bewusste Ernährung \| Fertiggerichte & Konserven | 4.99 | EatHappy Gyoza vegan 130g |
| bavaria | 2025-09-09 | 4005971394406 | Grillsaison \| Getränke & Genussmittel | 13.99 | Ramazzotti Crema Cappuccino 0,7l |
| bavaria | 2025-09-09 | 4260137741719 | Kochen & Backen \| Bewusste Ernährung | 3.29 | Frusano Bio-Getreidezucker 250g |
| bavaria | 2025-09-09 | 5038862435345 | Bewusste Ernährung \| Getränke & Genussmittel | 3.69 | Innocent Plus Saft Blue Break 750ml |
| bavaria | 2025-09-09 | 4009700071637 | Bewusste Ernährung \| Käse, Eier & Molkerei | 1.69 | YoPRO High Protein Drink Mango 270g |
| bavaria | 2025-09-09 | 4260166966008 | Grillsaison \| Getränke & Genussmittel | 14.99 | La Duchessa Aperitivo Bavarese 15% 0,7l |

## Pagination fingerprint

Rows per (file, category). If nearly all are multiples of 40, the source was scraped 40 products per page, and the last partial page of a category may be missing.

| region | category_files | multiple_of_40 | pct | min_rows | max_rows |
|---|---|---|---|---|---|
| bavaria | 9571 | 9520 | 99.5 | 120 | 5000 |
| schleswig-holstein | 9553 | 9517 | 99.6 | 40 | 4149 |

## Duplicates inside the same category

Same EAN twice in one category on one day: another sign of page overlap while scraping.

| groups | extra_rows | categories_affected | example_category |
|---|---|---|---|
| 26742 | 27167 | 26 | Babybedarf |

## Gaps between appearances

For each product and region: how many snapshots pass between two appearances. 1 = seen on consecutive snapshots. Short gaps followed by a return are probably scraping misses; this sets max_gap_snapshots in dbt_project.yml.

| snapshots_between | occurrences | pct |
|---|---|---|
| 1 | 16874800 | 97.22 |
| 2 | 163373 | 0.94 |
| 3 | 70688 | 0.41 |
| 4 | 45321 | 0.26 |
| 5 | 30897 | 0.18 |
| 6+ | 172009 | 0.99 |

## EAN shape

EANs must be stored as text. Length 8 and 13 are normal (EAN-8 / EAN-13); anything else, or non-digits, needs a look.

| ean_length | only_digits | rows | distinct_eans | example |
|---|---|---|---|---|
| 13 | True | 18975127 | 53817 | 8711775028459 |
| 8 | True | 1138649 | 3197 | 20482169 |
| 11 | True | 60809 | 177 | 59527601559 |
| 12 | True | 26868 | 128 | 722252387578 |
| 2 | False | 440 | 1 | NA |

## Distinct products

How many products exist, and how many appear in both regions.

| distinct_eans | in_both_regions | in_one_region |
|---|---|---|
| 57320 | 28097 | 29223 |

## Price column

Prices are text in bronze. Values that fail to parse as a number need handling.

| rows | empty | unparseable | min_price | max_price | bad_example |
|---|---|---|---|---|---|
| 20201893 | 0 | 440 | 0.01 | 3990.00 | NA |

## How often prices change

Per product and region: number of distinct prices over the whole period. This shows how much the price-interval model will compress the data.

| distinct_prices | products | pct |
|---|---|---|
| 1 | 44759 | 52.4 |
| 2 | 19439 | 22.8 |
| 3 | 9722 | 11.4 |
| 4 | 5049 | 5.9 |
| 5 | 2923 | 3.4 |
| 6 | 1692 | 2.0 |
| 7 | 912 | 1.1 |
| 8 | 327 | 0.4 |
| 9 | 241 | 0.3 |
| 10 | 132 | 0.2 |
| 11 | 91 | 0.1 |
| 12 | 33 | 0.0 |
| 13 | 37 | 0.0 |
| 14 | 20 | 0.0 |
| 15 | 14 | 0.0 |

## Same EAN, different names

Products renamed over time. Decides whether dim_product needs name history.

| eans_with_several_names | example |
|---|---|
| 2325 | Conditorei Coppenrath & Wiese Kuchenliebe New York Cheesecake 740g \| Coppenrath & Wiese New York Cheesecake 740g |

## Sale column

Expected values: True / False.

| sale | rows |
|---|---|
| False | 19104897 |
| True | 1096996 |

## Brand column

'NA' (and empty) should become NULL in silver.

| brand_kind | rows |
|---|---|
| real brand | 19068776 |
| NA | 1133117 |

## Top brands

Most frequent brands on the latest snapshot.

| brand | products |
|---|---|
| NA | 1502 |
| REWE Beste Wahl | 682 |
| ja! | 582 |
| REWE Bio | 513 |
| Dr. Oetker | 316 |
| Maggi | 226 |
| NIVEA | 209 |
| Vivess | 178 |
| Knorr | 177 |
| Hipp | 173 |
| Ruf | 172 |
| Today | 149 |
| Wilhelm Brandenburg | 135 |
| Weinfreunde | 130 |
| Müller | 119 |

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
| Drogerie & Kosmetik | bavaria | 2638 |
| Drogerie & Kosmetik | schleswig-holstein | 1040 |
| Fertiggerichte & Konserven | bavaria | 2360 |
| Fertiggerichte & Konserven | schleswig-holstein | 1080 |
| Fleisch & Fisch | bavaria | 1120 |
| Fleisch & Fisch | schleswig-holstein | 800 |
| Getränke & Genussmittel | bavaria | 3360 |
| Getränke & Genussmittel | schleswig-holstein | 2760 |
| Grillsaison | bavaria | 680 |
| Grillsaison | schleswig-holstein | 560 |
| Haus & Freizeit | bavaria | 600 |
| Haus & Freizeit | schleswig-holstein | 280 |
| Kaffee, Tee & Kakao | bavaria | 840 |
| Kaffee, Tee & Kakao | schleswig-holstein | 480 |
| Kochen & Backen | bavaria | 1360 |
| Kochen & Backen | schleswig-holstein | 600 |
| Käse, Eier & Molkerei | bavaria | 1960 |
| Käse, Eier & Molkerei | schleswig-holstein | 1200 |
| Küche & Haushalt | bavaria | 440 |
| Küche & Haushalt | schleswig-holstein | 600 |
| Monats-Highlights | schleswig-holstein | 1080 |
| Obst & Gemüse | schleswig-holstein | 240 |
| Regional | schleswig-holstein | 40 |
| Süßes & Salziges | schleswig-holstein | 1240 |
| Tiefkühlkost | schleswig-holstein | 800 |
| Tierbedarf | schleswig-holstein | 480 |
| Öle, Soßen & Gewürze | schleswig-holstein | 720 |

## Grammage patterns

Numbers replaced by N, so we can see which formats the parser must handle.

| pattern | rows | example |
|---|---|---|
| Ng (N kg = N €) | 10712819 | 250g (1 kg = 6,76 €) |
| Nml (N l = N €) | 2496436 | 230ml (1 l = 7,78 €) |
| Nl (N l = N €) | 1955695 | 8l (1 l = 0,24 €) |
| N Stück | 1727618 | 1 Stück |
| Ng | 793508 | 1000g |
| Nl | 585496 | 1l |
| NxNl (N l = N €) | 504010 | 10x0,25l (1 l = 0,44 €) |
| NxNg (N kg = N €) | 484891 | 4x100g (1 kg = 3,88 €) |
| N Stück ca. N g (N kg = N €) | 242974 | 1 Stück ca. 200 g (1 kg = 2,29 €) |
| Nml | 193207 | 5ml |
| Nkg (N kg = N €) | 80869 | 2,50kg (1 kg = 0,96 €) |
| NA | 80543 | NA |
| Nkg | 75500 | 1kg |
| NxNml (N l = N €) | 74780 | 2x200ml (1 l = 4,98 €) |
| NxN Stück | 71493 | 2x80 Stück |
| Nml (N kg = N €) | 29679 | 340ml (1 kg = 6,44 €) |
| NxNg | 21602 | 3x1g |
| NxNl | 15693 | 4x0,25l |
| Nm (N m  = N €) | 13485 | 20m (1 m  = 0,20 €) |
| Nm (N m = N €) | 11606 | 100m (1 m = 0,01 €) |
| Ng (N l = N €) | 10272 | 330g (1 l = 4,70 €) |
| NxNg (N l = N €) | 4433 | 4x62g (1 l = 14,48 €) |
| Nm | 4344 | 15m |
| NxNml | 2094 | 4x1,50ml |
| NxNcm (N m = N €) | 1901 | 20x6cm (1 m = 0,99 €) |
| Nl (N kg = N €) | 1748 | 238l (1 kg = 12,56 €) |
| NxNxNl (N l = N €) | 1505 | 4x6x0,33l (1 l = 2,92 €) |
| NxNm (N m  = N €) | 892 | 2x10m (1 m  = 0,16 €) |
| Ncm (N m = N €) | 805 | 29cm (1 m = 7,55 €) |
| NxNmm | 633 | 84x1mm |
| NxNm (N m = N €) | 591 | 10x10m (1 m = 0,04 €) |
| NmN (N mN = N €) | 318 | 0,01m3 (1 m3 = 799 €) |
| NxNcm | 222 | 84x1cm |
| NxNxNl | 65 | 4x6x0,33l |
| NxNxNml (N l = N €) | 45 | 4x6x355ml (1 l = 3,52 €) |
| NxNml (N kg = N €) | 31 | 5x90ml (1 kg = 37,25 €) |
| Ng (N m = N €) | 29 | 56g (1 m = 0,88 €) |
| Ncm (N kg = N €) | 28 | 56cm (1 kg = 35,54 €) |
| NxNxNkg (N l = N €) | 16 | 4x6x0,33kg (1 l = 2,52 €) |
| Ncm | 15 | 180cm |

## Unit price inside grammage

Share of rows with a '(1 kg = 3,96 €)'-style unit price, by base unit.

| base_unit | rows | pct | example |
|---|---|---|---|
| kg | 11553039 | 57.2 | 250g (1 kg = 9,16 €) |
| l | 5047192 | 25.0 | 250ml (1 l = 9,96 €) |
| <none> | 3572035 | 17.7 | 1 Stück |
| m | 29309 | 0.1 | 50m (1 m = 0,04 €) |
| m3 | 318 | 0.0 | 0,01m3 (1 m3 = 799 €) |

## Image column

Only checked, not used: we won't hotlink product images on a public site.

| empty_images | image_hosts |
|---|---|
| 0 | 1 |
