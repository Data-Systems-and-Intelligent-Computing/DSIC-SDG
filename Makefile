.PHONY: help h1-validate h1-summary h1-discover-webapi h1-fetch-free-webapi h1-fetch-free-publications h1-profile-coverage h1-apply-coverage h1-example h1-compare h2-run h3-fetch h3-run h3-releases h4-run h4-publish h5-run h5-iceberg h6-run h6-apply h6b-run h6c-run h7-run h7-apply h7b-run h7b-apply h7c-run h8-run h8-apply h8b-run h8c-run h9-run h9-apply h9b-run h9c-run h10-measure h10-run h10b-prepare h10b-cleanup h10b-measure h10b-run h11-prepare h11-baseline h11-measure h11-run h12-measure h12-run h13-rerun h13-run h13c-run h14-collect h14-run h14c-run h15-run h15-figures article-bundle manuscript raw-backup stack-up stack-down stack-freeze stack-remote-sync stack-remote-up stack-remote-status stack-remote-verify stack-remote-freeze stack-remote-down test

PYTHON ?= python3
H1 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h1.cli
H2 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h2.cli
H3 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h3.cli
H4 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h4.cli
H5 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h5.cli
H6 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h6.cli
H6B = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h6b.cli
H6C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h6c.cli
H7 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h7.cli
H7B = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h7b.cli
H7C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h7c.cli
H8 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h8.cli
H8B = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h8b.cli
H8C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h8c.cli
H9 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h9.cli
H9B = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h9b.cli
H9C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h9c.cli
H10 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h10.cli
H10_RUN ?= h10a-20260911
H10B = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h10b.cli
H10B_RUN ?= h10b-20260912
H10B_CLEANUP ?= 20260912
H11 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h11.cli
H11_RUN ?= h11-20260913
H12 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h12.cli
H12_RUN ?= h12-20260913
H13 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h13.cli
H13C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h13c.cli
H14 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h14.cli
H14C = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h14c.cli
H15 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h15.cli
H14_RUN ?= h14-20260913
H13_SCENARIOS ?= sweep_001
ARTICLE = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.article.cli
COMPOSE ?= docker-compose --env-file infra/docker/versions.env
STACK_HOST ?= sigerciv@34.101.84.199
STACK_DIR ?= /home/sigerciv/DSIC-SDG
STACK_BRANCH ?= main
REMOTE_COMPOSE = ssh $(STACK_HOST) 'cd $(STACK_DIR) && docker compose --env-file infra/docker/versions.env'

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
	@echo "make h3-fetch     Download the free WebAPI snapshot used by the H3 release supplement"
	@echo "make h3-run       Compare national and province cells across both channels"
	@echo "make h3-releases  Compare WebAPI, TPB 2024, and TPB 2025 release cells"
	@echo "make h4-run       Ingest manifested H3 outputs and apply shared classification rules"
	@echo "make h4-publish   Publish the H4 batch to the running MinIO warehouse"
	@echo "make h5-run       Freeze revision traces and decide Gate G1"
	@echo "make h5-iceberg   Write and read the H5 trace table through Iceberg"
	@echo "make h6-run       Validate the explicit-vintage schema against H5 traces"
	@echo "make h6-apply     Create and verify the H6 Iceberg tables"
	@echo "make h6b-run      Freeze and validate the B2 source-trust score"
	@echo "make h6c-run      Map and validate cell-to-source-record lineage"
	@echo "make h7-run       Apply the B0 overwrite baseline logically"
	@echo "make h7-apply     Create and verify the B0 Iceberg table"
	@echo "make h7b-run      Materialize the B2 single-source selection logically"
	@echo "make h7b-apply    Create and verify the B2 Iceberg table"
	@echo "make h7c-run      Extend treatment lineage and verify listed related work"
	@echo "make h8-run       Materialize the B1 full-snapshot workload logically"
	@echo "make h8-apply     Create and verify three retained B1 Iceberg snapshots"
	@echo "make h8b-run      Build deterministic nested injected-revision workloads"
	@echo "make h8c-run      Close implemented-treatment lineage and audit reproducibility"
	@echo "make h9-run       Materialize the B3 vintage-aware incremental treatment logically"
	@echo "make h9-apply     Create and verify the B3 Iceberg store and serving tables"
	@echo "make h9b-run      Execute the H8B validation routes on all four treatments logically"
	@echo "make h9c-run      Audit B3 impact and reproducibility and close four-treatment lineage"
	@echo "make h10-measure  Purge, rebuild, and measure treatment storage and recall on the stack host"
	@echo "make h10-run      Validate and aggregate the committed H10 raw measurement"
	@echo "make h10b-prepare Build the physical payload of the frozen H10B revision scenarios"
	@echo "make h10b-cleanup Remove the orphan objects earlier runs left in the experiment tables"
	@echo "make h10b-measure Inject one revision physically per treatment and time it on the stack host"
	@echo "make h10b-run     Validate and aggregate the committed H10B raw measurement"
	@echo "make h11-prepare  Project the frozen panel and rebuild the frozen main sweep payload"
	@echo "make h11-baseline Rebuild the four treatments on the frozen province panel"
	@echo "make h11-measure  Run the frozen main sweep on the stack host"
	@echo "make h11-run      Aggregate, audit and analyze the main sweep measurement"
	@echo "make h12-measure  Apply the four real releases per treatment and time them"
	@echo "make h12-run      Aggregate and audit the real-revision measurement"
	@echo "make h13-rerun    Measure the doubtful points again on the stack host"
	@echo "make h13-run      Pool the extra repetitions and report what still holds"
	@echo "make h13c-run     Audit reproducibility on the panel and analyse the failures"
	@echo "make h14-collect  Capture query plans, session logs and read statistics"
	@echo "make h14-run      Aggregate the plans and the measured read sizes"
	@echo "make h14c-run     Decompose the break-even result and price the failures"
	@echo "make h15-run      Compose the result tables and the figure data"
	@echo "make h15-figures  Render the figures as PGFPlots sources and compile them"
	@echo "make article-bundle  Collect checksum-verified article tables and key numbers"
	@echo "make raw-backup   Archive data/raw with a checksum list into backups/"
	@echo "make stack-up     Bring up MinIO, the Iceberg REST catalog, and Spark"
	@echo "make stack-remote-up  Sync and start the stack on STACK_HOST"
	@echo "make stack-remote-status  Show the remote stack status"
	@echo "make stack-remote-verify  Check HTTP endpoints and the Spark catalog path"
	@echo "make stack-down   Stop the stack and keep the warehouse volume"
	@echo "make stack-freeze Record the resolved image digests"
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

h3-run:
	$(H3) run

h3-fetch:
	$(H1) fetch-free-webapi \
		--selection config/h3/webapi_selection.csv \
		--raw-dir data/raw/h3/webapi \
		--manifest-output data/manifests/h3-free-webapi-data.json \
		--since-year 2015 \
		--workers 4

h3-releases:
	$(H3) releases

h4-run:
	$(H4)

h4-publish:
	bash scripts/h4_publish.sh

h5-run:
	$(H5)

h5-iceberg:
	bash scripts/h5_iceberg.sh

h6-run:
	$(H6)

h6-apply:
	bash scripts/h6_apply.sh

h6b-run:
	$(H6B)

h6c-run:
	$(H6C)

h7-run:
	$(H7)

h7-apply: h7-run
	bash scripts/h7_apply.sh

h7b-run:
	$(H7B)

h7b-apply: h7b-run
	bash scripts/h7b_apply.sh

h7c-run:
	$(H7C)

h8-run:
	$(H8)

h8-apply: h8-run
	bash scripts/h8_apply.sh

h8b-run:
	$(H8B)

h8c-run:
	$(H8C)

h9-run:
	$(H9)

h9-apply: h9-run
	bash scripts/h9_apply.sh

h9b-run:
	$(H9B)

h9c-run:
	$(H9C)

h10-measure:
	bash scripts/h10_measure.sh . $(H10_RUN)

h10-run:
	$(H10) --raw-dir results/raw/h10/$(H10_RUN)

h10b-prepare:
	$(H10B) prepare

h10b-cleanup:
	bash scripts/h10b_cleanup_orphans.sh . $(H10B_CLEANUP)

h10b-measure:
	bash scripts/h10b_measure.sh . $(H10B_RUN)

h10b-run:
	$(H10B) aggregate --raw-dir results/raw/h10b/$(H10B_RUN)

h11-prepare:
	$(H11) prepare

h11-baseline:
	bash scripts/h11_baseline.sh .

h11-measure:
	bash scripts/h11_measure.sh . $(H11_RUN)

h11-run:
	$(H11) aggregate --raw-dir results/raw/h11/$(H11_RUN)

h12-measure:
	bash scripts/h12_measure.sh . $(H12_RUN)

h12-run:
	$(H12) aggregate --raw-dir results/raw/h12/$(H12_RUN)

h13-rerun:
	H11_LIMIT_SCENARIOS=$(H13_SCENARIOS) H11_LIMIT_REPETITIONS=3 bash scripts/h11_measure.sh . h13-h11-sweep001
	H12_LIMIT_REPETITIONS=3 bash scripts/h12_measure.sh . h13-h12

h13-run:
	$(H13)

h13c-run:
	$(H13C)

h14-collect:
	bash scripts/h14_collect.sh . $(H14_RUN)

h14-run:
	$(H14) --raw-dir results/raw/h14/$(H14_RUN)

h14c-run:
	$(H14C)

h15-run:
	$(H15)

h15-figures:
	PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h15.render

article-bundle:
	$(ARTICLE)

manuscript:
	cd papers/vintage_reconciliation/manuscript && \
	pdflatex -interaction=nonstopmode -halt-on-error main.tex && \
	bibtex main && \
	pdflatex -interaction=nonstopmode -halt-on-error main.tex && \
	pdflatex -interaction=nonstopmode -halt-on-error main.tex

raw-backup:
	bash scripts/backup_raw.sh .

stack-up:
	$(COMPOSE) up -d
	$(COMPOSE) ps

stack-down:
	$(COMPOSE) down

stack-freeze:
	@$(COMPOSE) config --images | sort -u | while read image; do \
		docker image inspect "$$image" --format '{{index .RepoDigests 0}}' 2>/dev/null || echo "$$image NOT_PULLED"; \
	done | tee infra/docker/image-digests.txt

stack-remote-sync:
	ssh $(STACK_HOST) 'cd $(STACK_DIR) && git pull --ff-only origin $(STACK_BRANCH)'

stack-remote-up: stack-remote-sync
	$(REMOTE_COMPOSE) up -d --wait
	$(REMOTE_COMPOSE) ps

stack-remote-status:
	$(REMOTE_COMPOSE) ps

stack-remote-verify:
	ssh $(STACK_HOST) 'set -e; \
		curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null; \
		curl -fsS http://127.0.0.1:8181/v1/config >/dev/null; \
		curl -fsS http://127.0.0.1:8888/api >/dev/null; \
		cd $(STACK_DIR); \
		docker compose --env-file infra/docker/versions.env exec -T spark \
		/opt/spark/bin/spark-sql -e "SHOW NAMESPACES IN kkciv"'

stack-remote-freeze:
	$(REMOTE_COMPOSE) config --images | sort -u | while read image; do \
		ssh -n $(STACK_HOST) "docker image inspect '$$image' --format '{{index .RepoDigests 0}}'"; \
	done | tee infra/docker/image-digests.txt

stack-remote-down:
	$(REMOTE_COMPOSE) down

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit -v
