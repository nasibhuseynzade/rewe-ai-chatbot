{{ config(severity = 'warn') }}
-- Barcodes failing the GS1 check digit. A few are expected (source errors);
-- many would mean the GTIN normalisation in stg_prices is wrong.
select gtin, ean_raw, name
from {{ ref('dim_product') }}
where not is_valid_gtin
