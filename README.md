# ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents for Enterprise Scenarios

<p>
    <br>
    <b>ST-WebAgentBench</b> provides a standalone web evaluation environment for assessing the safety and trustworthiness of Web Agents in meeting organizational and user policy requirements. It is built on <a href="https://github.com/ServiceNow/BrowserGym">BrowserGym</a>, a conversational gym environment for evaluating web agents. Currently, it includes 234 tasks across 3 applications: WebArena/Gitlab, WebArena/shopping_admin, and SuiteCRM.
</p>

<p align="center">
<a href="https://www.python.org/downloads/release/python-3120/"><img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12"></a>
</p>

<p align="center">
<a href="https://sites.google.com/view/st-webagentbench/home">Website</a> •
<a href="https://arxiv.org/pdf/2410.06703">Paper</a>
</p>

# Getting Started

## Prerequisites

1. UV Python project manager: https://docs.astral.sh/uv/getting-started/installation/#installation-methods
2. (Optional) WebArena environment for Gitlab and shopping_admin. For quick setup, we recommend using the [AWS AMI environment](https://github.com/web-arena-x/webarena/tree/main/environment_docker#pre-installed-amazon-machine-image-recommended)
3. SuiteCRM environment - please follow the setup instructions in the [./suitecrm_setup](./suitecrm_setup) folder.

## Setup Credentials  
1. Copy `.env.example` to `.env`
2. Update `.env` with your `OPENAI_API_KEY`
3. Fill in the URLs of applications based on the **Prerequisites** section.

## Install Project Requirements
1. Create a Python virtual environment and activate it:
```
uv venv
source .venv/bin/activate
```

2. Install the `stwebagentbench` Python library:
```bash
uv pip install -e ./browsergym/stwebagentbench
```

3. Install and update Playwright:
```bash
uv pip install playwright==1.52.0
uv run -m playwright install chromium
```

# Usage

## Run the Benchmark Against a Demo Web Agent

1. To see how a sample demo agent can be evaluated on a task from SuiteCRM, run:

```bash
uv run st_bench_example.py
```

2. To run the benchmark on multiple tasks:

```bash
uv run st_bench_example_loop.py
```

## Aggregating Metrics for the Entire Benchmark

Running the benchmark creates individual task results under the `./data` folder.
To summarize results and compute metrics across all tasks, run:

```bash
uv run stwebagentbench/result_analysis/analyze.py
```

> Note: This should only be run after executing the loop example.

# Citation

If you use our environment or data, please cite our paper:
```
@article{levy2024stwebagentbenchbenchmarkevaluatingsafety,
      title={ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents}, 
      author={Ido Levy and Ben Wiesel and Sami Marreed and Alon Oved and Avi Yaeli and Segev Shlomov},
      year={2024},
      eprint={2410.06703},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2410.06703}, 
}
```