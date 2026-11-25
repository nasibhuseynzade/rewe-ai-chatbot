# Evaluation: cloudflare-gemma-4-26b-a4b-it

- Date: 2026-11-25 17:49
- Passed: **28/35** (80%)
- Right tool: 27/29 · Right numbers: 20/23
- Errors (provider failed): 2
- Average latency: 6.5 s · Average tokens per question: 6592 in + 130 out

| case | result | tools called | problem |
|---|---|---|---|
| price_nutella_750_de | PASS | search_products |  |
| price_kerrygold_en | PASS | search_products |  |
| price_milk_tr | PASS | search_products |  |
| price_oatly_en | PASS | search_products |  |
| change_nutella_450_de | PASS | search_products, get_price_change |  |
| change_activia_tr | PASS | search_products, get_price_change |  |
| change_kuvertuere_en | FAIL | - | all providers failed: cloudflare: ReadTimeout |
| change_toilet_paper_tr | PASS | search_products, get_price_change |  |
| index_all_bavaria_de | PASS | get_category_index, get_category_index, run_sql, describe_table, run_sql |  |
| index_top_category_bavaria_en | PASS | rank_categories_by_inflation |  |
| index_top_category_sh_tr | PASS | rank_categories_by_inflation |  |
| index_coffee_de | PASS | get_category_index |  |
| index_produce_en | PASS | get_category_index |  |
| index_regions_tr | FAIL | - | all providers failed: cloudflare: HTTP 400: AiError: AiError: {"object":"error","message":"Assistant tool call function.arguments must be valid JSON.","type":"BadRequest","param":null,"code":400} (6ec |
| index_dairy_sh_de | PASS | get_category_index |  |
| rank_increase_en | PASS | rank_price_changes |  |
| rank_decrease_de | PASS | rank_price_changes |  |
| rank_sweets_tr | PASS | rank_price_changes |  |
| shrink_any_tr | FAIL | - | tools: called nothing, wanted one of ['find_shrinkflation']; numbers: missing 3.4; mentions: missing ['Niederegger'] |
| shrink_coffee_en | PASS | find_shrinkflation |  |
| shrink_somat_de | PASS | search_products, find_shrinkflation |  |
| region_overall_en | FAIL | get_category_index, get_category_index, run_sql, describe_table, run_sql | tools: called ['get_category_index', 'get_category_index', 'run_sql', 'describe_table', 'run_sql'], wanted one of ['compare_regions']; numbers: missing 962, 148 |
| region_biggest_gap_tr | PASS | compare_regions |  |
| region_nutella_de | PASS | search_products |  |
| sales_share_dec24_de | PASS | get_sales_stats, run_sql |  |
| sales_discount_dec24_en | PASS | get_sales_stats |  |
| sales_top_category_tr | FAIL | get_sales_stats, get_sales_stats, run_sql, run_sql | numbers: missing 13.67; mentions: missing ['Tiefkühlkost'] |
| sql_product_count_en | PASS | run_sql |  |
| sql_pet_products_de | PASS | run_sql, describe_table, run_sql |  |
| sql_top_brand_tr | FAIL | run_sql | mentions: missing ['ja!'] |
| scope_today_tr | FAIL | search_products | mentions: missing ['2025'] |
| scope_berlin_en | PASS | - |  |
| scope_lidl_de | PASS | - |  |
| scope_poem_en | PASS | - |  |
| scope_weather_de | PASS | - |  |
