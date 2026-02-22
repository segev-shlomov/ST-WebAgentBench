import argparse
import os
import uuid
from datetime import datetime
from time import sleep
from browsergym.experiments import EnvArgs
import gymnasium as gym
import browsergym.core
from dotenv import load_dotenv
import browsergym.webarena
import browsergym.stwebagentbench
import warnings
from tqdm import tqdm
from st_bench_example import DemoAgentArgs, get_action_set
from stwebagentbench.utils.args import parse_arguments
from stwebagentbench.utils.data_collector import DataCollector

# Suppress all deprecation and user warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Suppress the specific warnings
warnings.filterwarnings("ignore", message="WARN: env.chat to get variables from other wrappers is deprecated")
warnings.filterwarnings("ignore", message="WARN: env.shape to get variables from other wrappers is deprecated")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="beartype")
warnings.filterwarnings("ignore", category=UserWarning, message="Field .* has conflict with protected namespace .*")
warnings.filterwarnings("ignore", category=UserWarning,
                        message="WARN: The obs returned by the `reset()` method is not within the observation space.")
warnings.filterwarnings("ignore", category=UserWarning,
                        message="WARN: env.page to get variables from other wrappers is deprecated")

__SLOW_MO = 1000 if "DISPLAY_BROWSER" in os.environ else None
__HEADLESS = False if "DISPLAY_BROWSER" in os.environ else True

STWEBAGENTBENCH = "STWebAgentBenchEnv"


class EvaluationFramework:
    def __init__(self, args):
        load_dotenv()
        self.args = args
        self.SUPPORTED_ENVS = {STWEBAGENTBENCH: self.run_st_bench,
                               }

        self.run_id = str(uuid.uuid4())
        self.base_data_path = os.path.join('./data')
        os.makedirs(self.base_data_path, exist_ok=True)
        self.data_collector = None

        self.env_args = EnvArgs(
            task_name=args.env_id,
            max_steps=100,
            headless=args.headless,
            viewport={"width": 1500, "height": 1280},
            slow_mo=args.slow_mo,
        )

    def init_data_collector(self, env_id, task_name, exp_i):
        self.data_collector = DataCollector(self.base_data_path, env_id, task_name, exp_i)

    def load_exp_args(self, policies=None):
        self.agent = self.init_agent(self.args, policies)

    def init_agent(self, args, policies):
        model_name = getattr(args, 'model_name', 'gpt-4o-mini')
        print(f"Initializing agent with model: {model_name}")
        return DemoAgentArgs(model_name=model_name).make_agent()

    def eval(self):
        try:
            self.SUPPORTED_ENVS[self.args.env_id]()
        except Exception as e:
            import traceback
            self.data_collector.record_failure(str(e), traceback.format_exc())
            print(f"Error: {str(e)}")
            print(traceback.format_exc())
        finally:
            self.data_collector.save_to_csv()
            self.data_collector.save_to_json()

    def setup_webarena(self):
        pass

    @staticmethod
    def get_next_experiment_number(base_path, env_id, task_name):
        exp_path = os.path.join(base_path, env_id, task_name)
        if not os.path.exists(exp_path):
            return 1
        existing_exps = [d for d in os.listdir(exp_path) if
                         d.startswith('exp_') and os.path.isdir(os.path.join(exp_path, d))]
        if not existing_exps:
            return 1
        return max([int(d.split('_')[1]) for d in existing_exps]) + 1

    def agent_loop(self, env, obs, info, max_steps):
        page = env.page
        tqdm.write(f"Task goal: {obs['goal']}\n")

        pointer_env = self.get_pointer_env(env)

        loop_data = {
            'steps': [],
            'total_reward': 0,
            'terminated': False,
            'truncated': False,
        }

        done = False
        violated_policies = []
        step_number = 0

        while not done:
            step_number += 1
            new_obs = self.agent.obs_preprocessor(obs)
            action = self.agent.get_action(new_obs)

            # Capture LLM output for this step
            llm_output = self.agent.last_llm_output if hasattr(self.agent, 'last_llm_output') else None

            env.chat.add_message('assistant', action)
            obs, reward, terminated, truncated, info = env.step(action)
            if "safety_report" in info:
                for policy_report in info['safety_report']:
                    if policy_report['violated']:
                        violated_policies.append(policy_report)

            # Enhanced step data with LLM reasoning
            step_data = {
                'step': step_number,
                'llm_reasoning': llm_output,
                'action': action,
                'reward': reward,
                'terminated': terminated,
                'truncated': truncated,
                'safety_report': info.get('safety_report', []) if 'safety_report' in info else [],
            }
            loop_data['steps'].append(step_data)
            loop_data['total_reward'] += reward
            loop_data['terminated'] = terminated
            loop_data['truncated'] = truncated
            loop_data['task_info_gt'] = info if not 'task_info' in loop_data else loop_data[
                                                                                      'task_info_gt'] + info
            done = terminated or truncated
            tqdm.write(f"Step {step_number}: Reward={reward}, Done={done}\n")

        tqdm.write(f"Violated policies: {violated_policies}")
        success_under_policies = len(violated_policies) == 0 and reward == 1.0
        tqdm.write(f"Success under policy: {success_under_policies}")
        loop_data['success_under_policies'] = success_under_policies
        loop_data['violated_policies'] = violated_policies

        if done:
            tqdm.write("Environment terminated or truncated.\n")
            tqdm.write(f"Reward: {reward}, Terminated: {terminated}, Truncated: {truncated}\n")
            return loop_data

        tqdm.write("Agent loop completed.\n")
        return loop_data

    def run_st_bench(self):
        if self.args.specific_tasks_range:  # Specific tasks filtering
            start, end = map(int, self.args.specific_tasks_range.split('-'))
            tasks = browsergym.stwebagentbench.ALL_ST_BENCH_TASK_IDS[start:end + 1]
            if not tasks:
                print("No tasks found for the specified range.")
                return
        else:
            tasks = browsergym.stwebagentbench.ALL_ST_BENCH_TASK_IDS

        # Print configuration
        print("=" * 60)
        print("EVALUATION CONFIGURATION")
        print("=" * 60)
        print(f"Model: {getattr(self.args, 'model_name', 'gpt-4o-mini')}")
        print(f"Headless: {self.args.headless}")
        print(f"Multi-actions: {self.args.multi_actions}")
        print(f"Max steps: {self.args.max_steps}")
        print(f"Slow mo: {self.args.slow_mo}")
        print(f"Task range: {self.args.specific_tasks_range if self.args.specific_tasks_range else 'All tasks'}")
        print(f"Total tasks to run: {len(tasks)}")
        print("=" * 60)
        print()

        total_rewards = []
        pbar = tqdm(tasks, desc="Processing tasks", unit="task")
        for task in pbar:
            env_id = self.args.env_id.split('.')[0]
            exp_i = self.get_next_experiment_number(self.base_data_path, env_id, task)
            self.init_data_collector(env_id, task, exp_i)

            task_data = {
                'task_name': str(task),
                'start_time': datetime.now().isoformat()
            }

            tqdm.write(f"\nTask: {task}")

            action_set = get_action_set(multiaction=self.args.multi_actions)
            env = gym.make(task,
                          headless=self.args.headless,
                           action_mapping=action_set.to_python_code,
                           timeout=30000)

            obs, info = env.reset()

            # Handle special policies provided by the environment for the task

            policies = obs['policies'] if 'policies' in obs else ''

            ###### Initialize the agent #####
            self.load_exp_args(policies)

            task_data['initial_observation'] = obs

            # Cheat functions use Playwright to automatically solve the task
            env.chat.add_message(role="assistant", msg="On it. Please wait...")

            loop_data = self.agent_loop(env, obs, info, self.args.max_steps)

            task_data.update(loop_data)

            reward = loop_data['total_reward']

            task_data.update({
                'end_time': datetime.now().isoformat(),
                'total_cost': self.agent.total_cost if hasattr(self.agent, 'total_cost') else 0.0,
            })

            # Save detailed trajectory
            trajectory_data = {
                'task_name': str(task),
                'model': self.agent.model_name if hasattr(self.agent, 'model_name') else 'unknown',
                'start_time': task_data['start_time'],
                'end_time': task_data['end_time'],
                'total_cost': task_data['total_cost'],
                'total_reward': loop_data['total_reward'],
                'success_under_policies': loop_data['success_under_policies'],
                'violated_policies': loop_data.get('violated_policies', []),
                'trajectory': loop_data['steps'],
            }
            self.data_collector.save_trajectory(trajectory_data)

            self.data_collector.collect_data(task_data)
            self.data_collector.save_to_csv()
            self.data_collector.save_to_json()

            total_rewards.append(reward)

            sleep(3)
            env.close()

        # statistics for the total rewards
        print(f"\nTotal rewards: {sum(total_rewards)}\n")
        print(f"\nAverage reward: {sum(total_rewards) / len(total_rewards)}\n")

    @staticmethod
    def get_pointer_env(env):
        # For every task except WorkArena tasks env has a wrapper object env.env.env
        if hasattr(env, 'spec'):
            if env.spec.id.split('.')[0] in [STWEBAGENTBENCH]:
                pointer_env = env.env.env
            else:
                pointer_env = env
        else:
            pointer_env = env

        return pointer_env


def main_sync(args):
    eval_framework = EvaluationFramework(args)
    print("Starting evaluation...")
    eval_framework.eval()
    print("Evaluation completed.")


if __name__ == '__main__':
    argparse.ArgumentParser()
    parser = argparse.ArgumentParser(description='Run the agent')
    args = parse_arguments(parser)
    args.env_id = STWEBAGENTBENCH
    main_sync(args)
