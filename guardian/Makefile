PY      ?= conda run -n pr_agent python
SAMPLE  ?= $(CURDIR)/.sample-context
PUBLIC  ?= $(CURDIR)/.public-context

.PHONY: help env test lint check doctor sample demo eval eval-public eval-demo eval-all clean

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

eval: sample     ## retrieval quality on the sample context (CI gate)
	GUARDIAN_CONTEXT=$(SAMPLE) ./bin/guardian eval tests/eval/sample_cases.json --min-recall 0.75

eval-public:     ## retrieval quality on pinned public repos (requests, axios, spring-petclinic)
	$(PY) tests/eval/build_public_context.py tests/eval/public_cases.json $(PUBLIC)
	GUARDIAN_CONTEXT=$(PUBLIC) ./bin/guardian eval tests/eval/public_cases.json

DEMO    ?= $(CURDIR)/.demo-context
eval-demo:       ## retrieval quality on the demo repos (locopy, datacompy) with guardian/data policies
	$(PY) tests/eval/build_public_context.py tests/eval/demo_cases.json $(DEMO)
	GUARDIAN_CONTEXT=$(DEMO) ./bin/guardian eval tests/eval/demo_cases.json

ALL     ?= $(CURDIR)/.all-context
eval-all:        ## retrieval quality across all 7 repos in guardian/data (41 tickets)
	$(PY) tests/eval/build_public_context.py tests/eval/all_repos_cases.json $(ALL)
	GUARDIAN_CONTEXT=$(ALL) ./bin/guardian eval tests/eval/all_repos_cases.json

clean:
	rm -rf $(SAMPLE) $(PUBLIC) $(DEMO) $(ALL) .pytest_cache .ruff_cache lib/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
