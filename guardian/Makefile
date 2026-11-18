PY      ?= conda run -n pr_agent python
SAMPLE  ?= $(CURDIR)/.sample-context

.PHONY: help env test lint check doctor sample demo clean

help:            ## list targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

env:             ## create or update the pr_agent conda env
	conda env update -f environment.yml --prune

lint:            ## ruff
	$(PY) -m ruff check lib tests

test:            ## unit + integration tests
	$(PY) -m pytest

check: lint test ## everything CI runs

doctor:          ## is context/ ready for a demo?
	./bin/guardian doctor

sample:          ## build the offline sample context
	rm -rf $(SAMPLE) && $(PY) tests/sample_context.py $(SAMPLE)

demo: sample     ## blueprint a ticket against the sample context
	GUARDIAN_CONTEXT=$(SAMPLE) ./bin/guardian blueprint "Mask customer account numbers before they reach the payment logs"

clean:
	rm -rf $(SAMPLE) .pytest_cache .ruff_cache lib/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
