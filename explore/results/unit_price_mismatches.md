# unit_price_mismatches

## Size of the problem

| mismatching_intervals | all_intervals | pct | products | on_sale_intervals |
|---|---|---|---|---|
| 105 | 52981 | 0.2 | 71 | 3 |

## By grammage pattern and sale flag

| pattern | on_sale | intervals | median_ratio | min_ratio | max_ratio | example |
|---|---|---|---|---|---|---|
| Ng (N kg = N €) | False | 58 | 1.428 | 0.714 | 4.25 | 180g (1 kg = 9,97 €) |
| NxNg (N kg = N €) | False | 36 | 0.25 | 0.006 | 1.114 | 2x180g (1 kg = 23,83 €) |
| Nl (N l = N €) | False | 3 | 0.623 | 0.623 | 0.624 | 16l (1 l = 0,47 €) |
| NxNl (N l = N €) | False | 2 | 0.167 | 0.167 | 0.167 | 6x1,50l (1 l = 7,16 €) |
| NxNg (N kg = N €) | True | 2 | 0.5 | 0.5 | 0.5 | 2x500g (1 kg = 15,98 €) |
| Nml (N l = N €) | False | 1 | 0.75 | 0.75 | 0.75 | 400ml (1 l = 16,63 €) |
| NxNml (N l = N €) | False | 1 | 0.333 | 0.333 | 0.333 | 3x100ml (1 l = 59,90 €) |
| Ng (N kg = N €) | True | 1 | 0.919 | 0.919 | 0.919 | 135g (1 kg = 40,24 €) |
| N Stück ca. N g (N kg = N €) | False | 1 | 0.964 | 0.964 | 0.964 | 1 Stück ca. 50 g (1 kg = 2,49 €) |

## Ratio buckets (our unit price / source unit price)

| ratio_bucket | intervals |
|---|---|
| a) < 0.5 | 32 |
| b) 0.5 - 0.9 | 16 |
| c) 0.9 - 1.0 | 5 |
| d) 1.0 - 1.1 | 5 |
| e) 1.1 - 2.0 | 40 |
| f) >= 2.0 | 7 |

## By primary category

| primary_category | intervals |
|---|---|
| Fertiggerichte & Konserven | 60 |
| Öle, Soßen & Gewürze | 7 |
| Kaffee, Tee & Kakao | 6 |
| Brot, Cerealien & Aufstriche | 6 |
| Käse, Eier & Molkerei | 5 |
| Fleisch & Fisch | 4 |
| Süßes & Salziges | 4 |
| Obst & Gemüse | 3 |
| Kochen & Backen | 3 |
| Drogerie & Kosmetik | 3 |
| Getränke & Genussmittel | 2 |
| Küche & Haushalt | 2 |

## Examples

| name | primary_category | region | valid_from | price | on_sale | grammage | our_unit_price | source_unit_price | ratio |
|---|---|---|---|---|---|---|---|---|---|
| Ruf Farbstifte für Lebensmittel 8 Stück 68g | Kochen & Backen | schleswig-holstein | 2025-08-31 | 6.69 | False | 16g (1 kg = 98,38 €) | 418.125 | 98.3800 | 4.25 |
| Ruf Farbstifte für Lebensmittel 8 Stück 68g | Kochen & Backen | bavaria | 2025-08-25 | 6.69 | False | 16g (1 kg = 98,38 €) | 418.125 | 98.3800 | 4.25 |
| Ruf Farbstifte für Lebensmittel 8 Stück 68g | Kochen & Backen | bavaria | 2025-09-04 | 6.69 | False | 16g (1 kg = 98,38 €) | 418.125 | 98.3800 | 4.25 |
| Feinkost Dittmann Spanische Oliven mit Blue Cheese 85g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 2.19 | False | 85g (1 kg = 10,95 €) | 25.7647 | 10.9500 | 2.353 |
| Kattus Getrocknete Tomaten mariniert 145g | Fertiggerichte & Konserven | bavaria | 2025-08-31 | 3.59 | False | 145g (1 kg = 12,17 €) | 24.7586 | 12.1700 | 2.034 |
| Kattus Getrocknete Tomaten in Streifen 145g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 3.89 | False | 145g (1 kg = 13,19 €) | 26.8276 | 13.1900 | 2.034 |
| Homann Bratrollmops mit Zwiebeln 250g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-26 | 4.29 | False | 250g (1 kg = 8,58 €) | 17.16 | 8.5800 | 2.0 |
| Ehrmann Grand Dessert Mousse Vanille 170g | Käse, Eier & Molkerei | bavaria | 2025-08-31 | 1.49 | False | 170x170g (1 kg = 8,76 €) | 0.0516 | 8.7600 | 0.006 |
| Ehrmann Grand Dessert Mousse Vanille 170g | Käse, Eier & Molkerei | schleswig-holstein | 2025-08-25 | 1.49 | False | 170x170g (1 kg = 8,76 €) | 0.0516 | 8.7600 | 0.006 |
| Argeta Junior Orginal 95g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 1.59 | False | 12x95g (1 kg = 16,74 €) | 1.3947 | 16.7400 | 0.083 |
| Argeta Junior Orginal 95g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 1.59 | False | 12x95g (1 kg = 16,74 €) | 1.3947 | 16.7400 | 0.083 |
| Argeta Junior Orginal 95g | Fertiggerichte & Konserven | schleswig-holstein | 2025-09-08 | 1.49 | False | 12x95g (1 kg = 15,68 €) | 1.307 | 15.6800 | 0.083 |
| Niederegger Marzipan Cappuccino 10x22g | Kaffee, Tee & Kakao | schleswig-holstein | 2025-08-26 | 5.40 | False | 10x220g (1 kg = 24,55 €) | 2.4545 | 24.5500 | 0.1 |
| Niederegger Typ Marzipan Milchkaffee 10x20g | Kaffee, Tee & Kakao | schleswig-holstein | 2025-08-26 | 5.40 | False | 10x200g (1 kg = 27 €) | 2.7 | 27.0000 | 0.1 |
| Niederegger Typ Marzipan Trinkschokolade 10x25g | Kaffee, Tee & Kakao | schleswig-holstein | 2025-08-26 | 5.40 | False | 10x250g (1 kg = 21,60 €) | 2.16 | 21.6000 | 0.1 |
| REWE Beste Wahl Antipasti Gegrillte Champignons 150g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 2.99 | False | 150g (1 kg = 10,68 €) | 19.9333 | 10.6800 | 1.866 |
| Bamboo Garden Wok-Gemüse Karotte Ingwer 180g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 3.39 | False | 180g (1 kg = 10,27 €) | 18.8333 | 10.2700 | 1.834 |
| Harry Bauern-Goldkrüstchen 6x80g | Brot, Cerealien & Aufstriche | schleswig-holstein | 2025-08-25 | 2.39 | False | 6x480g (1 kg = 4,98 €) | 0.8299 | 4.9800 | 0.167 |
| Harry Premiumkrüstchen 6x80g | Brot, Cerealien & Aufstriche | schleswig-holstein | 2025-08-25 | 2.39 | False | 6x480g (1 kg = 4,98 €) | 0.8299 | 4.9800 | 0.167 |
| Rauch Eistee Peach 6x1,5l | Getränke & Genussmittel | schleswig-holstein | 2025-08-25 | 10.74 | False | 6x1,50l (1 l = 7,16 €) | 1.1933 | 7.1600 | 0.167 |
| Rauch Eistee Peach 6x1,5l | Getränke & Genussmittel | bavaria | 2025-08-25 | 10.74 | False | 6x1,50l (1 l = 7,16 €) | 1.1933 | 7.1600 | 0.167 |
| Bamboo Garden Wok-Keimlinge 180g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 3.29 | False | 180g (1 kg = 9,97 €) | 18.2778 | 9.9700 | 1.833 |
| Bamboo Garden Asia Wok-Gemüse Süss-sauer mit Ananas 180g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 3.29 | False | 180g (1 kg = 9,97 €) | 18.2778 | 9.9700 | 1.833 |
| Feinkost Dittmann Pepper Balls Classic mit Frischkäse 160g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 5.29 | False | 160g (1 kg = 18,24 €) | 33.0625 | 18.2400 | 1.813 |
| SOTO Bio Mini Frühlingsrollen China Style vegan 200g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 2.99 | False | 4x200g (1 kg = 14,95 €) | 3.7375 | 14.9500 | 0.25 |
| SOTO Bio Mini Frühlingsrollen China Style vegan 200g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 2.99 | False | 4x200g (1 kg = 14,95 €) | 3.7375 | 14.9500 | 0.25 |
| Marziale Mini Sacher Törtchen 4x25g | Brot, Cerealien & Aufstriche | bavaria | 2025-08-31 | 4.29 | False | 4x100g (1 kg = 42,90 €) | 10.725 | 42.9000 | 0.25 |
| ja! Exotischer Fruchtcocktail 4x113g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 1.79 | False | 4x280g (1 kg = 6,39 €) | 1.5982 | 6.3900 | 0.25 |
| ja! Exotischer Fruchtcocktail 4x113g | Fertiggerichte & Konserven | bavaria | 2025-08-28 | 1.79 | False | 4x280g (1 kg = 6,39 €) | 1.5982 | 6.3900 | 0.25 |
| ja! Exotischer Fruchtcocktail 4x113g | Fertiggerichte & Konserven | bavaria | 2025-09-03 | 1.79 | False | 4x280g (1 kg = 6,39 €) | 1.5982 | 6.3900 | 0.25 |
| ja! Exotischer Fruchtcocktail 4x113g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-26 | 1.79 | False | 4x280g (1 kg = 6,39 €) | 1.5982 | 6.3900 | 0.25 |
| ja! Joghurt Griechischer Art Natur 4x150g | Käse, Eier & Molkerei | bavaria | 2025-08-25 | 1.49 | False | 4x600g (1 kg = 2,48 €) | 0.6208 | 2.4800 | 0.25 |
| ja! Joghurt Griechischer Art Natur 4x150g | Käse, Eier & Molkerei | schleswig-holstein | 2025-08-25 | 1.49 | False | 4x600g (1 kg = 2,48 €) | 0.6208 | 2.4800 | 0.25 |
| Feinkost Dittmann Tomaten halbgetrocknet 190g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 4.49 | False | 190g (1 kg = 13,61 €) | 23.6316 | 13.6100 | 1.736 |
| ja! Erbsen extra fein 3x140g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 1.59 | False | 3x420g (1 kg = 3,79 €) | 1.2619 | 3.7900 | 0.333 |
| ja! Erbsen extra fein 3x140g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 1.59 | False | 3x420g (1 kg = 3,79 €) | 1.2619 | 3.7900 | 0.333 |
| ja! Erbsen extra fein mit Möhren sehr fein 3x200g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 1.59 | False | 3x390g (1 kg = 4,08 €) | 1.359 | 4.0800 | 0.333 |
| ja! Erbsen extra fein mit Möhren sehr fein 3x200g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 1.59 | False | 3x390g (1 kg = 4,08 €) | 1.359 | 4.0800 | 0.333 |
| ja! Sonnen-Mais natursüß 3x140g | Fertiggerichte & Konserven | schleswig-holstein | 2025-08-25 | 1.99 | False | 3x420g (1 kg = 4,74 €) | 1.5794 | 4.7400 | 0.333 |
| ja! Sonnen-Mais natursüß 3x140g | Fertiggerichte & Konserven | bavaria | 2025-08-25 | 1.99 | False | 3x420g (1 kg = 4,74 €) | 1.5794 | 4.7400 | 0.333 |
