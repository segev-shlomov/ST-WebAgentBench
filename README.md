# ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents for Enterprise Scenarios
<p>
    <br>
    <b>ST-WebAgentBench </b> benchmark provides a standlone web evaluation environment for evaluating the safety and trusworthiness of  Web Agents in meeting organizational and user policy requirements.  It is based on <a href="https://github.com/ServiceNow/BrowserGym">BrowserGym</a>, a conversational gym environment for  evaluation web agents.  Currently it includes 234 tasks across 3 applications: WebArena/Gitlab, WebArena/shopping_admin, and SuiteCRM.
</p>



<p align="center">
<a href="https://www.python.org/downloads/release/python-3120/"><img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12"></a>
</p>

<p align="center">
<a href="https://sites.google.com/view/st-webagentbench/home">Website</a> •
<a href="https://arxiv.org/pdf/2410.06703">Paper</a> •
</p>

# Getting Started

## Prerequisites

1. Python 3.12.  You can download from [here](https://www.python.org/downloads/release/python-3120/)
2. WebArena environment for Gitlab, shopping_admin.  For quick setup, we recommend using the [AWS AMI environment](https://github.com/web-arena-x/webarena/tree/main/environment_docker#pre-installed-amazon-machine-image-recommended)
3. SuiteCRM environment - please follow the setup instructions under [./suitecrm_setup](./suitecrm_setup) folder. 

## Setup credentials  
1. Copy `.env.example` into `.env`.
2. Fill URLs of apps based on **Setup apps** part.

## Install project requirements
1. Run the following command

``make install``


# Usage

## Run the benchmark against a demo web agent

1. To see how a sample demo agent can be evaluated on a sample task from SuiteCRM, run the following: 

> Running Demo agent on single task on suitecrm

```make demo```

> Running a loop over a range of tasks  

``make demo-loop``


## Aggregating metrics for the entire benchmark

Running the benchmark creates individual task results under the TBD folder
To summarize results and compute metrics across all tasks, run the following:

``make analyze``
 
# Citation

If you use our environment or data, please cite our paper:
@article{levy2024stwebagentbenchbenchmarkevaluatingsafety,
      title={ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents}, 
      author={Ido Levy and Ben Wiesel and Sami Marreed and Alon Oved and Avi Yaeli and Segev Shlomov},
      year={2024},
      eprint={2410.06703},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2410.06703}, 
}
