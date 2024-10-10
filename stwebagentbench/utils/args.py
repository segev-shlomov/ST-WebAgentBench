import argparse
MODEL_NAME = "gpt-4o-mini-2024-07-18"  # 'gpt-4o-2024-08-06'  # "gpt-4o-mini-2024-07-18"  # "gpt-4-turbo"  # "gpt-4o-mini-2024-07-18"
# MODEL_NAME = 'gpt-4o-2024-08-06'  # 'gpt-4o-2024-08-06'  # "gpt-4o-mini-2024-07-18"  # "gpt-4-turbo"  # "gpt-4o-mini-2024-07-18"
DEFAULT_ENV = "browsergym/STWebAgentBenchEnv.3"
DEFAULT_LLM_TYPE = "openai"  # "genai"

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def parse_arguments(parser):
    """
    Parse the arguments for the agent.
    Args:
        parser (argparse.ArgumentParser): the parser object
    Returns:
        argparse.Namespace: the parsed arguments
    """
    parser.add_argument('--model_name', type=str, default=MODEL_NAME, help='The model name to use')
    parser.add_argument('--env_id', type=str, default=DEFAULT_ENV,
                        help='The environment id to use, If "openended", you need to specify a "start_url"')
    parser.add_argument('--llm_type', type=str, default=DEFAULT_LLM_TYPE, help='The llm type to use')
    parser.add_argument('--sync', type=bool, default=True, help='Sync or async mode')
    parser.add_argument('--architecture', type=str, default='general', help='The agentic workflow architecture to use')
    parser.add_argument('--max_steps', type=int, default=100, help='The maximum number of steps to take')
    parser.add_argument('--specific_tasks', type=str, default=None, help='The specific task to run')
    parser.add_argument('--input', type=str, default=None, help='The specific task to run')

    parser.add_argument(
        "--start_url",
        type=str,
        default="https://www.google.com",
        help="Starting URL (only for the openended task).",
    )
    parser.add_argument(
        "--slow_mo", type=int, default=500, help="Slow motion delay for the playwright actions."
    )
    parser.add_argument(
        "--headless",
        type=str2bool,
        default=False,
        help="Run the experiment in headless mode (hides the browser windows).",
    )
    parser.add_argument(
        "--demo_mode",
        type=str2bool,
        default=True,
        help="Add visual effects when the agents performs actions.",
    )
    parser.add_argument(
        "--use_html", type=str2bool, default=True, help="Use HTML in the agent's observation space."
    )
    parser.add_argument(
        "--use_ax_tree",
        type=str2bool,
        default=True,
        help="Use AX tree in the agent's observation space.",
    )
    parser.add_argument(
        "--use_screenshot",
        type=str2bool,
        default=True,
        help="Use screenshot in the agent's observation space.",
    )
    parser.add_argument(
        "--multi_actions", type=str2bool, default=True, help="Allow multi-actions in the agent."
    )
    parser.add_argument(
        "--action_space",
        type=str,
        default="bid",
        choices=["python", "bid", "coord", "bid+coord", "bid+nav", "coord+nav", "bid+coord+nav"],
        help="",
    )
    parser.add_argument(
        "--use_history",
        type=str2bool,
        default=True,
        help="Use history in the agent's observation space.",
    )
    parser.add_argument(
        "--use_thinking",
        type=str2bool,
        default=True,
        help="Use thinking in the agent (chain-of-thought prompting).",
    )

    ########### Web Arena specific arguments ###########
    #         intent_template_id: Optional[int] = None,
    #         with_na_hint: bool = False,
    #         with_homepage_hint: bool = False,
    parser.add_argument(
        "--intent_template_id",
        type=int,
        default=None,
        help="The intent template id to use (only for the WebArena task).",
    )

    parser.add_argument(
        "--with_na_hint",
        type=str2bool,
        default=False,
        help="Use the NA hint (only for the WebArena task).",
    )
    parser.add_argument(
        "--with_homepage_hint",
        type=str2bool,
        default=False,
        help="Use the homepage hint (only for the WebArena task).",
    )

    parser.add_argument('--task_id', type=int, default=None, help='Specific task id to run in the WebArena task')

    parser.add_argument('--action_mapping_predefined', type=bool, default=False, help='Use predefined action mapping')

    parser.add_argument('--specific_tasks_range', type=str, default=None, help='The specific task range to run, e.g. "1-10"')

    return parser.parse_args()