<div align="center">
  <img src="assets/figures/logo.png" alt="ST-WebAgentBench Logo" width="180" style="margin-bottom: 20px;">
<!--   <h1>ST-WebAgentBench</h1> -->
  <p><strong>A Benchmark for Evaluating Safety &amp; Trustworthiness in Web Agents</strong></p>
  <div>
    <!-- Python Badge -->
    <a href="https://www.python.org/downloads/release/python-3120/">
      <img src="https://img.shields.io/badge/Python-3.12-%233776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=306998" alt="Python 3.12"/>
    </a>
    &nbsp;
    <!-- Website Badge -->
    <a href="https://sites.google.com/view/st-webagentbench/home">
      <img src="https://img.shields.io/badge/Website-Live-%238E44AD?style=for-the-badge&logo=googlechrome&logoColor=white&labelColor=663399" alt="Project Website"/>
    </a>
    &nbsp;
    <!-- arXiv Badge -->
    <a href="https://arxiv.org/abs/2410.06703">
      <img src="https://img.shields.io/badge/arXiv-2410.06703-%23B31B1B?style=for-the-badge&logo=arxiv&logoColor=white&labelColor=8A1111" alt="arXiv Paper"/>
    </a>
    <br>
    <!-- Hugging Face Badge -->
    <a href="https://huggingface.co/datasets/dolev31/st-webagentbench">
      <img src="https://img.shields.io/badge/HuggingFace-Dataset-%23FFD43B?style=for-the-badge&logo=huggingface&logoColor=black&labelColor=FFA500" alt="Hugging Face Dataset"/>
    </a>
    &nbsp;
    <!-- GitHub Badge -->
    <a href="https://github.com/segev-shlomov/ST-WebAgentBench">
      <img src="https://img.shields.io/badge/GitHub-Repository-%23181717?style=for-the-badge&logo=github&logoColor=white&labelColor=0D1117" alt="GitHub Repository"/>
    </a>
  </div>
</div>
<!-- You can add your additional content below this line -->

---

## 📋 Table of Contents

- [🎯 Overview](#-overview)  
- [🚀 Features](#-features)  
- [📊 Metrics](#-metrics)  
- [⚙️ Installation](#%EF%B8%8F-installation) 
- [🚦 Quick Start](#-quick-start)  
- [🔧 Usage](#-usage)  
- [🤝 Contributing](#-contributing)  
- [📚 Citation](#-citation)  
- [🔗 References](#-references)  

---

## 🎯 Overview

**ST-WebAgentBench** provides a **standalone**, **policy-enriched** evaluation suite for web agents, built on [BrowserGym](https://github.com/ServiceNow/BrowserGym).  
It covers **222** realistic enterprise tasks across three applications:

| Application                   | # Tasks | Avg Policies/task |
| ----------------------------- |:-------:|:-----------------:|
| **WebArena / GitLab**         |   47    |       **4.0**     |
| **WebArena / ShoppingAdmin**  |    8    |       **3.0**     |
| **SuiteCRM**                  |  **167**|       **2.6**     |

Each task is paired with **646** policy instances spanning six dimensions:

<div align="center">
  <img src="assets/figures/policy_dimensions.png" alt="Policy Dimensions"/>
</div>


---

## 🚀 Features

- **Multi-App & Realistic Tasks**  
  End-to-end workflows in GitLab, ShoppingAdmin, and CRM—mirroring real enterprise scenarios with dynamic UIs.

- **Policy-Aware Evaluation**  
  Six orthogonal safety/trust dimensions (User-Consent, Boundary, Strict Execution, Hierarchy, Robustness, Error Handling) ensure agents **“do it right”**, not just finish tasks.

- **Human-in-the-Loop Hooks**  
  Agents can defer or request confirmation (e.g., “Are you sure you want to delete?”) to test safe fallback behaviors.

- **Rich Observation & Action Space**  
  Leverages BrowserGym’s DOM, screenshot, and AXTree views, plus custom **`ask_user`** actions.

- **Extensible & Open-Source**  
  YAML-based policy templates and modular evaluators allow easy addition of new tasks, policies, or entire applications.

---

## 📊 Metrics

| Metric         | Definition                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------ |
| **CR**         | **Completion Rate** — raw task success                                                     |
| **CuP**        | **Completion under Policy** — success **with zero** policy violations                       |
| **pCuP**       | **Partial CuP** — partial success under policy                                             |
| **Risk Ratio** | Avg. violations per policy dimension (normalized by # policies in that dimension)          |

> **Key Insight:** Agents lose up to **38%** of their raw successes when enforcing policies (CR → CuP), revealing hidden safety gaps.

---

## ⚙️ Installation

1. Install UV Python project manager: https://docs.astral.sh/uv/getting-started/installation/#installation-methods
2. **Create & activate virtual environment**
```
uv venv
source .venv/bin/activate
```
3. **Install the `stwebagentbench` Python library**  
```bash
uv pip install -e ./browsergym/stwebagentbench
```
4. **Install and update Playwright**
```bash
uv pip install playwright==1.52.0
uv run -m playwright install chromium
```
5. **Provision web apps**

   * **GitLab & ShoppingAdmin** via [WebArena AWS AMI](https://github.com/web-arena-x/webarena/tree/main/environment_docker#pre-installed-amazon-machine-image-recommended)
   * **SuiteCRM**: see [`suitecrm_setup/README.md`](suitecrm_setup/README.md)

6. **Configure credentials**

   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY and service URLs
   ```

---

## 🚦 Quick Start

### Running a Single Demo Task

Test with a single SuiteCRM task:

```bash
python st_bench_example.py
```

### Running the Full Benchmark

**1. Run predictions for a specific model:**

```bash
# Using OpenAI models
python st_bench_example_loop.py --model_name openai/gpt-4o-mini --headless true

# Using OpenRouter models (e.g., Gemini, Claude, etc.)
python st_bench_example_loop.py --model_name google/gemini-2.0-flash-001 --headless true

# Run specific task range
python st_bench_example_loop.py --model_name openai/gpt-4o-mini --specific_tasks_range "0-10" --headless true

# Disable multi-actions mode
python st_bench_example_loop.py --model_name openai/gpt-4o-mini --multi_actions false --headless true
```

**Available command-line options:**
- `--model_name`: Model identifier (prefix with `openai/` for OpenAI models, otherwise uses OpenRouter)
- `--headless`: Run browser in headless mode (`true` or `false`, default: `true`)
- `--specific_tasks_range`: Run specific task range (e.g., `"0-10"` or `"52-235"`)
- `--multi_actions`: Enable/disable multi-action mode (`true` or `false`, default: `true`)
- `--max_steps`: Maximum steps per task (default: `100`)

**2. Evaluate results and compute metrics:**

After running predictions, evaluate the results:

```bash
python stwebagentbench/result_analysis/analyze.py
```

This generates:
- `STBenchDemo_agent_full_res.csv`: Detailed per-task results with policy violations
- `STBenchDemo_agent_res_summary.csv`: Aggregated metrics including:
  - **Completion Rate (CR)**: Percentage of tasks successfully completed
  - **CuP (Completion under Policy)**: Percentage of tasks completed without policy violations
  - **Risk Ratio**: Policy violation rates by category (boundary, consent, exact_task)

**Understanding the output:**

The evaluation will show:
```
Semi Completion Rate: 0.421
Semi CUP Rate: 0.193
Completion Rate: 0.421
CUP Rate: 0.193
```

Key insight: The gap between **Completion Rate** and **CuP** reveals how many task successes violated safety policies.

---

## 🔧 Usage

### Python API

```python
import gym
import browsergym.stwebagentbench  # registers environments

env = gym.make("browsergym/STWebAgentBenchEnv.0", headless=True)
obs, info = env.reset()
done = False

while not done:
    action = your_agent.get_action(obs)  # replace with agent logic
    obs, reward, terminated, truncated, info = env.step(action)
    done = terminated or truncated

# Check policy compliance
violated_policies = info.get('safety_report', [])
success_under_policy = reward == 1.0 and len(violated_policies) == 0
```

### Key Components

* **obs** includes:
  - Page DOM and accessibility tree
  - Screenshots
  - Active policy definitions
  - Chat history with user

* **action_space** supports:
  - Standard browser actions (click, fill, scroll, etc.)
  - `send_msg_to_user()` for requesting user consent
  - `answer()` to signal task completion

* **info** contains:
  - `safety_report`: List of policy violations
  - Task-specific metadata

### API Keys Setup

For OpenAI models:
```bash
# In .env file
OPENAI_API_KEY=your_openai_key_here
```

For OpenRouter models (Gemini, Claude, Llama, etc.):
```bash
# In .env file
OPENROUTER_API_KEY=your_openrouter_key_here
```

---

## 🤝 Contributing

We welcome contributions!
The benchmark is designed to be extensible, allowing you to add new tasks, policies, or even entire applications.

---

## 📚 Citation

```bibtex
@inproceedings{Levy2025STWebAgentBench,
  title     = {{ST-WebAgentBench}: A Benchmark for Evaluating Safety & Trustworthiness in Web Agents},
  author    = {Levy, Ido and Wiesel, Ben and Marreed, Sami and Oved, Alon and Yaeli, Avi and Shlomov, Segev},
  booktitle = {ArXiv},
  year      = {2025},
  note      = {arXiv:2410.06703}
}
```

---

## 🔗 References

1. **Zhou et al. (2024)** — *WebArena: A Realistic Web Environment for Building Autonomous Agents*. ICLR.
2. **De Chezelles et al. (2024)** — *BrowserGym: A Conversational Gym for Web Agent Evaluation*. TMLR.

---