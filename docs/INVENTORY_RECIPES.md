# Recipes and inventory

Recipes are owner-scoped canonical records. A recipe can be created manually,
imported from pasted text, fetched from a public URL through the existing
untrusted web boundary, or extracted from an owner-checked PDF upload.

Import saves recipe structure only. It does not add stock, mark purchases, or
change the grocery queue. `missing_ingredients` and the read-only
`recipe_missing_by_name` chat action compare recipe requirements
with current pantry/fridge/freezer stock using the deterministic unit planner;
`queue_missing` explicitly adds only required shortages to Grocery. Optional
ingredients are reported but are not queued.

Grocery means items still needed to buy. Pantry, Fridge, and Freezer mean stock
already owned. Cooking is the separate mutation that consumes verified stock.
Imported text and web/PDF content is untrusted data and cannot grant inventory
authority.
