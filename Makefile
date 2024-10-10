install:
	@echo "--- 🚀 Installing project dependencies ---"
	pip install -e ./browsergym/stwebagentbench

demo:
	@echo "--- 🚀 Running demo agent ---"
	(python st_bench_example.py)

demo-loop:
	@echo "--- 🚀 Running demo agent loop for 2 tasks ---"
	(python st_bench_example_loop.py)

analyze:
	@echo "--- 🚀 Running analysis on results ---"
	(python stwebagentbench/result_analysis/analyze.py)

test-evaluations:
	@echo "--- 🧪 Running tests ---"
	pytest
