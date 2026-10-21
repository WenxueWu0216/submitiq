# SubmitIQ developer commands. `make setup && make eval && make demo` runs fully offline.
VENV ?= .venv
PY ?= $(VENV)/bin/python
PIPELINE ?= final
SPLIT ?= test
BACKEND ?= replay

.PHONY: setup data test eval eval-dev eval-all gate demo seed serve synth eval-live export-reviewed clean

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt
	@command -v tesseract >/dev/null || echo "WARNING: tesseract not found (brew install tesseract / apt-get install tesseract-ocr). Scanned pages will not be read."
	@echo "setup complete"

data:            ## regenerate the synthetic dataset (deterministic)
	$(PY) data/generate.py

test:
	$(PY) -m pytest

eval:            ## headline eval: final pipeline, test split, replay backend
	$(PY) -m evals.run --pipeline $(PIPELINE) --split $(SPLIT) --backend $(BACKEND)

eval-dev:
	$(PY) -m evals.run --pipeline $(PIPELINE) --split dev --backend $(BACKEND)

eval-all:        ## every pipeline variant on both splits (feeds docs/experiment_log.md)
	$(PY) scripts/run_all_evals.py --backend $(BACKEND)

gate:            ## what CI runs: eval on all 120 and compare with evals/baseline.json
	$(PY) -m evals.run --pipeline $(PIPELINE) --split all --backend replay --out evals/results/scratch --quiet
	$(PY) -m evals.gate $$(ls -t evals/results/scratch/*_$(PIPELINE)_all_replay.json | head -1)

demo:            ## run one submission end-to-end and print the triage summary
	$(PY) -m submitiq.demo

seed:            ## load 12 demo packages into the service database
	$(PY) scripts/seed_demo.py

export-reviewed: ## approved reviews -> data/reviewed/ eval cases (then: make eval SPLIT=reviewed)
	$(PY) scripts/export_corrections.py

serve:           ## review UI on http://localhost:8000
	$(PY) -m uvicorn service.app:app --reload --port 8000

synth:           ## CDK synth (no AWS account needed)
	cd infra && npx --yes aws-cdk@2 synth --quiet

eval-live:       ## real model run; records replay fixtures. Needs ANTHROPIC_API_KEY (or BACKEND=bedrock)
	SUBMITIQ_RECORD=1 $(PY) scripts/run_all_evals.py --backend $(if $(filter replay,$(BACKEND)),anthropic,$(BACKEND))

clean:
	rm -rf .cache evals/results/scratch infra/cdk.out
