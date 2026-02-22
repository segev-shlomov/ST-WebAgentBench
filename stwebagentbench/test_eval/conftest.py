"""Shared test configuration — mocks heavy browsergym/webarena imports.

This conftest runs before any test module collection. It patches sys.modules so
that ``from stwebagentbench.browser_env.custom_env import ActionTrace`` (and
similar imports) resolve to lightweight stubs instead of pulling in the full
browsergym dependency chain, which fails on Python 3.9.
"""

import sys
from typing import Any, Dict, List, Optional, TypedDict, Union
from unittest.mock import MagicMock

import numpy as np
import numpy.typing as npt

# ---------------------------------------------------------------------------
# Lightweight stubs for the types used throughout the evaluator code
# ---------------------------------------------------------------------------

Observation = Union[str, npt.NDArray[np.uint8]]


class StateInfo(TypedDict):
    observation: Dict[str, Observation]
    info: Dict[str, Any]


class ActionTrace(dict):
    """Minimal stand-in for ``stwebagentbench.browser_env.custom_env.ActionTrace``."""
    pass


# ---------------------------------------------------------------------------
# Wire up sys.modules with per-submodule mocks
# ---------------------------------------------------------------------------

_custom_env_mock = MagicMock()
_custom_env_mock.ActionTrace = ActionTrace

_constants_mock = MagicMock()
_constants_mock.ANSWER_ACTION = "answer"

_utils_mock = MagicMock()
_utils_mock.StateInfo = StateInfo

_env_config_mock = MagicMock()
_env_config_mock.ACCOUNTS = {"shopping_site_admin": {"username": "admin", "password": "admin"}}
_env_config_mock.GITLAB = "http://gitlab.example.com"
_env_config_mock.MAP = "http://map.example.com"
_env_config_mock.REDDIT = "http://reddit.example.com"
_env_config_mock.SHOPPING = "http://shopping.example.com"
_env_config_mock.SHOPPING_ADMIN = "http://shopping-admin.example.com"
_env_config_mock.WIKIPEDIA = "http://wikipedia.example.com"

_browser_env_pkg = MagicMock()
_browser_env_pkg.custom_env = _custom_env_mock
_browser_env_pkg.constants = _constants_mock
_browser_env_pkg.utils = _utils_mock
_browser_env_pkg.env_config = _env_config_mock
_browser_env_pkg.StateInfo = StateInfo

_module_mocks = {
    'stwebagentbench.browser_env': _browser_env_pkg,
    'stwebagentbench.browser_env.constants': _constants_mock,
    'stwebagentbench.browser_env.custom_env': _custom_env_mock,
    'stwebagentbench.browser_env.utils': _utils_mock,
    'stwebagentbench.browser_env.env_config': _env_config_mock,
    'webarena': MagicMock(),
    'webarena.browser_env': MagicMock(),
    'stwebagentbench.llms': MagicMock(),
    'stwebagentbench.llms.providers': MagicMock(),
    'stwebagentbench.llms.providers.openai_utils': MagicMock(),
}

for mod_name, mock_obj in _module_mocks.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj
