---
title: ST-WebAgentBench Leaderboard
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.6.0
app_file: app.py
pinned: true
license: mit
tags:
  - leaderboard
  - benchmark
  - web-agents
  - safety
  - ICLR
datasets:
  - ST-WebAgentBench/st-webagentbench
short_description: "Safety & Trustworthiness Leaderboard for Web Agents"
---

# ST-WebAgentBench Leaderboard

**Evaluating Safety & Trustworthiness in Web Agents — ICLR 2026**

375 tasks | 3,005 policies | 6 safety dimensions | 3 web applications

## Key Metrics

| Metric | Definition |
|--------|-----------|
| **CuP** (primary) | Task completed AND zero policy violations |
| **CR** | Task completed (ignoring safety) |
| **Gap%** | The "safety tax": how much CR drops when enforcing policies |
| **Risk Ratio** | Per-dimension violation rate |
| **all-pass@k** | Reliability: CuP=1 across ALL k independent runs |

## How to Submit

1. Run the full benchmark on all 375 tasks
2. Generate your submission:

```bash
python -m stwebagentbench.leaderboard.submit \
    --results-dir data/STWebAgentBenchEnv/browsergym \
    --agent-id "your-agent" \
    --model-name "gpt-4o" \
    --team "Your Team" \
    --code-url "https://github.com/your/repo" \
    --contact-email "you@example.com" \
    --output submission.json
```

3. Upload `submission.json` on the **Submit** tab

## Links

- [Paper (arXiv)](https://arxiv.org/abs/2410.06703)
- [Dataset (HuggingFace)](https://huggingface.co/datasets/ST-WebAgentBench/st-webagentbench)
- [GitHub Repository](https://github.com/segev-shlomov/ST-WebAgentBench)
- [Project Website](https://sites.google.com/view/st-webagentbench/home)

## Citation

```bibtex
@article{levy2024st,
  title={St-webagentbench: A benchmark for evaluating safety and trustworthiness in web agents},
  author={Levy, Ido and Wiesel, Ben and Marreed, Sami and Oved, Alon and Yaeli, Avi and Shlomov, Segev},
  journal={arXiv preprint arXiv:2410.06703},
  year={2024}
}
```
