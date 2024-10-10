import asyncio
import importlib

from browsergym.core.registration import register_task
from gymnasium import register

from stwebagentbench.browser_env.custom_env import BrowserEnv
# register the WebArena benchmark
from . import config, task

ALL_ST_BENCH_TASK_IDS = []

__version__ = '1.0.0'

class STWebAgentBenchEnv(BrowserEnv):  # Inherit from the existing environment
    def __init__(self, *args, **kwargs):
        print("custom STWebAgentBenchEnv initialized has been called")

        super().__init__(*args, **kwargs,)
        # Your initialization here (e.g., set up Playwright)


# register the WebArena benchmark
for task_id in config.TASK_IDS:
    gym_id = f"browsergym/STWebAgentBenchEnv.{task_id}"
    register(
        id=gym_id,  # Unique ID for your environment
        order_enforce=False,
        disable_env_checker=True,
        entry_point=lambda *env_args, **env_kwargs: STWebAgentBenchEnv(task.GenericWebArenaTask, *env_args, **env_kwargs),
        # Replace with actual path
        nondeterministic=True,
        kwargs={"task_kwargs": {"task_id": task_id}},
    )
    # register_task()
    ALL_ST_BENCH_TASK_IDS.append(gym_id)
