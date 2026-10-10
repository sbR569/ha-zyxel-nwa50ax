"""Pytest configuration.

Makes `custom_components` importable as a package root, so tests can do
`from ha_zyxel.zyxel_ssh_api import ZyxelSSHAPI` etc.

This requires Home Assistant to be importable (e.g. `pip install
homeassistant` or `pip install pytest-homeassistant-custom-component`),
since importing the `ha_zyxel` package runs its `__init__.py` like any other
Home Assistant custom component - this is the standard, expected setup for
testing a HA custom integration, not a limitation specific to this project.

The HA-level tests (test_config_flow.py, test_init.py) need
`pytest-homeassistant-custom-component`: they load the integration the way
HA does, as `custom_components.ha_zyxel`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))


@pytest.fixture
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA's loader find custom_components/ha_zyxel (opt-in per test module)."""
    yield
