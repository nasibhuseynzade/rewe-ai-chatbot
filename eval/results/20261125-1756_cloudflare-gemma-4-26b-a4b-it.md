# Evaluation: cloudflare-gemma-4-26b-a4b-it

- Date: 2026-11-25 18:06
- Passed: **32/35** (91%)
- Right tool: 29/30 · Right numbers: 22/24
- Errors (provider failed): 1
- Average latency: 15.9 s · Average tokens per question: 7075 in + 683 out

| case | result | tools called | problem |
|---|---|---|---|
| price_nutella_750_de | PASS | search_products |  |
| price_kerrygold_en | PASS | search_products |  |
| price_milk_tr | PASS | search_products |  |
| price_oatly_en | PASS | search_products |  |
| change_nutella_450_de | PASS | search_products, get_price_change |  |
| change_activia_tr | FAIL | search_products, get_price_change | numbers: missing 2.69 |
| change_kuvertuere_en | PASS | search_products, get_price_change |  |
| change_toilet_paper_tr | PASS | search_products, get_price_change |  |
| index_all_bavaria_de | PASS | get_category_index |  |
| index_top_category_bavaria_en | FAIL | - | all providers failed: cloudflare: HTTP 429: AiError: AiError: Capacity temporarily exceeded, please try again. (20c6fdd4-1ea0-483a-bfb9-6dedee21a7b7) |
| index_top_category_sh_tr | PASS | rank_categories_by_inflation |  |
| index_coffee_de | PASS | get_category_index |  |
| index_produce_en | PASS | get_category_index |  |
| index_regions_tr | PASS | get_category_index, get_category_index |  |
| index_dairy_sh_de | PASS | get_category_index |  |
| rank_increase_en | PASS | rank_price_changes |  |
| rank_decrease_de | PASS | rank_price_changes |  |
| rank_sweets_tr | PASS | rank_price_changes |  |
| shrink_any_tr | PASS | find_shrinkflation |  |
| shrink_coffee_en | PASS | find_shrinkflation |  |
| shrink_somat_de | PASS | search_products, get_price_history, find_shrinkflation |  |
| region_overall_en | PASS | compare_regions |  |
| region_biggest_gap_tr | PASS | compare_regions |  |
| region_nutella_de | PASS | search_products |  |
| sales_share_dec24_de | PASS | get_sales_stats |  |
| sales_discount_dec24_en | FAIL | describe_table, run_sql, run_sql, run_sql, run_sql | tools: called ['describe_table', 'run_sql', 'run_sql', 'run_sql', 'run_sql'], wanted one of ['get_sales_stats']; numbers: missing 32.82 |
| sales_top_category_tr | PASS | describe_table, run_sql |  |
| sql_product_count_en | PASS | describe_table, run_sql |  |
| sql_pet_products_de | PASS | describe_table, run_sql |  |
| sql_top_brand_tr | PASS | describe_table, run_sql |  |
| scope_today_tr | PASS | search_products |  |
| scope_berlin_en | PASS | - |  |
| scope_lidl_de | PASS | - |  |
| scope_poem_en | PASS | - |  |
| scope_weather_de | PASS | - |  |
