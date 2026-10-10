"""Config flow tests: the SSH port is configurable (default 22)."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ha_zyxel.const import DOMAIN

pytestmark = pytest.mark.usefixtures("auto_enable_custom_integrations")

USER_INPUT = {"host": "10.0.20.2", "username": "admin", "password": "pw"}


async def _submit_user_step(hass, user_input):
    with patch("custom_components.ha_zyxel.config_flow.ZyxelSSHAPI") as api_cls, patch(
        "custom_components.ha_zyxel.async_setup_entry", return_value=True
    ):
        api_cls.return_value.async_connect = AsyncMock(return_value=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    return result, api_cls


async def test_user_flow_uses_custom_ssh_port(hass):
    result, api_cls = await _submit_user_step(hass, {**USER_INPUT, "port": 2387})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["port"] == 2387
    api_cls.assert_called_once_with("10.0.20.2", "admin", "pw", port=2387)


async def test_user_flow_defaults_to_port_22(hass):
    result, api_cls = await _submit_user_step(hass, USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["port"] == 22
    api_cls.assert_called_once_with("10.0.20.2", "admin", "pw", port=22)
