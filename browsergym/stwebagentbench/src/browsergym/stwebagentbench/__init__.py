import logging

from gymnasium import register

from stwebagentbench.browser_env.custom_env import BrowserEnv
from . import config, task

logger = logging.getLogger(__name__)

ALL_ST_BENCH_TASK_IDS = []

__version__ = '1.0.0'


class STWebAgentBenchEnv(BrowserEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# Register all ST-WebAgentBench tasks as Gymnasium environments
for task_id in config.TASK_IDS:
    gym_id = f"browsergym/STWebAgentBenchEnv.{task_id}"
    register(
        id=gym_id,
        order_enforce=False,
        disable_env_checker=True,
        entry_point=lambda *env_args, **env_kwargs: STWebAgentBenchEnv(task.GenericWebArenaTask, *env_args, **env_kwargs),
        nondeterministic=True,
        kwargs={"task_kwargs": {"task_id": task_id}},
    )
    ALL_ST_BENCH_TASK_IDS.append(gym_id)
