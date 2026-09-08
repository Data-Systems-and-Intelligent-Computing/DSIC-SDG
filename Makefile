.PHONY: help h1-validate h1-summary h1-example h1-compare test

PYTHON ?= python3
H1 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h1.cli

help:
	@echo "KK-CIV vintage reconciliation research workspace"
	@echo "make h1-validate  Validate the shared source and indicator inventory"
	@echo "make h1-summary   Show H1 coverage by domain and verification status"
	@echo "make h1-example   Compare the two committed example source snapshots"
	@echo "make test         Run the unit tests"

h1-validate:
	$(H1) validate

h1-summary:
	$(H1) summary

h1-example:
	$(H1) compare \
		--input examples/h1/source_webapi.csv examples/h1/source_tpb_publication.csv \
		--output results/processed/h1-example-comparison.csv

h1-compare:
	@test -n "$(INPUTS)" || (echo "Usage: make h1-compare INPUTS='file1.csv file2.csv' [OUTPUT=path.csv]"; exit 2)
	$(H1) compare --input $(INPUTS) --output $(or $(OUTPUT),results/processed/h1-comparison.csv)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit -v
