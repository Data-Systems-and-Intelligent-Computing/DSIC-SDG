.PHONY: help h1-validate h1-summary h1-discover-webapi h1-fetch-free-webapi h1-fetch-free-publications h1-profile-coverage h1-apply-coverage h1-example h1-compare h2-run test

PYTHON ?= python3
H1 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h1.cli
H2 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h2.cli

help:
	@echo "KK-CIV vintage reconciliation research workspace"
	@echo "make h1-validate  Validate the shared source and indicator inventory"
	@echo "make h1-summary   Show H1 coverage by domain and verification status"
	@echo "make h1-discover-webapi  Fetch and match the BPS central variable catalog"
	@echo "make h1-fetch-free-webapi  Download the curated free WebAPI tables since 2015"
	@echo "make h1-fetch-free-publications  Download the free TPB 2024 and 2025 PDFs"
	@echo "make h1-profile-coverage  Profile the fetched payloads into a coverage report"
	@echo "make h1-apply-coverage    Write the derived decisions into the indicator inventory"
	@echo "make h1-example   Compare the two committed example source snapshots"
	@echo "make h2-run       Normalize and compare the five-domain H2 pilot"
	@echo "make test         Run the unit tests"

h1-validate:
	$(H1) validate

h1-summary:
	$(H1) summary

h1-discover-webapi:
	$(H1) discover-webapi

h1-fetch-free-webapi:
	$(H1) fetch-free-webapi

h1-fetch-free-publications:
	$(H1) fetch-free-publications

h1-profile-coverage:
	$(H1) profile-coverage

h1-apply-coverage: h1-profile-coverage
	$(H1) apply-coverage
	$(H1) validate

h1-example:
	$(H1) compare \
		--input examples/h1/source_webapi.csv examples/h1/source_tpb_publication.csv \
		--output results/processed/h1-example-comparison.csv

h1-compare:
	@test -n "$(INPUTS)" || (echo "Usage: make h1-compare INPUTS='file1.csv file2.csv' [OUTPUT=path.csv]"; exit 2)
	$(H1) compare --input $(INPUTS) --output $(or $(OUTPUT),results/processed/h1-comparison.csv)

h2-run:
	$(H2) run

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit -v
