install:
	@echo "--- Installing project dependencies ---"
	pip install -e ./browsergym/stwebagentbench

setup:
	@echo "--- Full project setup ---"
	pip install -r requirements.txt
	pip install playwright==1.52.0
	python -m playwright install chromium
	pip install -e ./browsergym/stwebagentbench
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example — please add your API keys"; fi

demo:
	@echo "--- Running demo agent ---"
	python st_bench_example.py

demo-loop:
	@echo "--- Running demo agent loop for 2 tasks ---"
	python st_bench_example_loop.py

analyze:
	@echo "--- Running analysis on results ---"
	python stwebagentbench/result_analysis/analyze.py

submit:
	@echo "--- Generating leaderboard submission ---"
	python -m stwebagentbench.leaderboard.submit \
		--results-dir data/STWebAgentBenchEnv/browsergym \
		--agent-id $(AGENT_ID) \
		--model-name $(MODEL_NAME) \
		--team $(TEAM) \
		--code-url $(CODE_URL) \
		--contact-email $(CONTACT_EMAIL) \
		--output submission.json

validate-submission:
	@echo "--- Validating submission ---"
	python -m stwebagentbench.leaderboard.submit \
		--results-dir data/STWebAgentBenchEnv/browsergym \
		--agent-id $(AGENT_ID) \
		--model-name $(MODEL_NAME) \
		--team $(TEAM) \
		--code-url $(CODE_URL) \
		--contact-email $(CONTACT_EMAIL) \
		--validate-only

test-evaluations:
	@echo "--- Running tests ---"
	PYTHONPATH=. pytest
