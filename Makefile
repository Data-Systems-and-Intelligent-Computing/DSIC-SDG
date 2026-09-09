.PHONY: help h1-validate h1-summary h1-discover-webapi h1-fetch-free-webapi h1-fetch-free-publications h1-profile-coverage h1-apply-coverage h1-example h1-compare h2-run h3-fetch h3-run h3-releases stack-up stack-down stack-freeze stack-remote-sync stack-remote-up stack-remote-status stack-remote-verify stack-remote-freeze stack-remote-down test

PYTHON ?= python3
H1 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h1.cli
H2 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h2.cli
H3 = PYTHONPATH=src $(PYTHON) -m kkciv_vintage.h3.cli
COMPOSE ?= docker-compose --env-file infra/docker/versions.env
STACK_HOST ?= sigerciv@34.128.67.92
STACK_DIR ?= /home/sigerciv/penelitian-kk-h3-runtime
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
	ssh $(STACK_HOST) 'mkdir -p $(STACK_DIR)/data $(STACK_DIR)/results'
	COPYFILE_DISABLE=1 tar -czf - docker-compose.yml infra/docker/versions.env infra/spark/spark-defaults.conf | \
		ssh $(STACK_HOST) 'tar -xzf - -C $(STACK_DIR)'

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
