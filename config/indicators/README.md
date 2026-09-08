# H1 indicator inventory

Each domain researcher owns one CSV file in this directory. The rows are candidates transcribed
from Table 9 of the proposal, not proof that the corresponding data exist.

Before changing `verification_status` to `verified`, fill all applicable locator fields:

- `webapi_domain_id` and `webapi_variable_id` for WebAPI data;
- `sirusa_indicator_id` for metadata;
- `tpb_publication_year` and `tpb_table_or_page` for the annual TPB publication;
- `producer` from the table or dataset, not merely the site or publication publisher;
- the observed geographic and time coverage in `verified_geographies`, `period_start`, and
  `period_end`.

Allowed status values are `proposal_only`, `partial`, `verified`, `unavailable`, and `blocked`.
Run `make h1-validate` before merging an inventory update.
