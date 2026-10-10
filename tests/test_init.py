"""Setup tests: the real parsing pipeline fed with captured CLI output.

Only the SSH transport (`_async_execute_session_direct`) and the connection
test are replaced - every command an entry sends is answered from the
fixture directory of one firmware, so entity creation runs against exactly
what that AP returned.
"""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_zyxel.const import DOMAIN
from custom_components.ha_zyxel.zyxel_ssh_api import ZyxelSSHAPI

pytestmark = pytest.mark.usefixtures("auto_enable_custom_integrations")

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_transport(firmware: str):
    """Answer each CLI command with fixtures/<firmware>/<command>.txt ('' if absent)."""

    async def _execute(self, commands, settle_delays=None, capture=True):
        outputs = []
        for cmd in commands:
            path = FIXTURES / firmware / f"{cmd.replace(' ', '_').replace('-', '_').lower()}.txt"
            outputs.append(path.read_text() if path.exists() else "")
        return outputs

    return _execute


async def _setup(hass, firmware: str, data: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="10.0.20.2",
        data=data or {"host": "10.0.20.2", "port": 2387, "username": "admin", "password": "pw"},
    )
    entry.add_to_hass(hass)
    with patch.object(ZyxelSSHAPI, "async_connect", AsyncMock(return_value=True)), patch.object(
        ZyxelSSHAPI, "_async_execute_session_direct", _fixture_transport(firmware)
    ), patch("custom_components.ha_zyxel.asyncio.sleep", AsyncMock()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _state(hass, entry, platform: str, suffix: str):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{suffix}")
    return hass.states.get(entity_id) if entity_id else None


async def test_setup_passes_configured_port_to_api(hass):
    with patch("custom_components.ha_zyxel.ZyxelSSHAPI", wraps=ZyxelSSHAPI) as api_cls:
        await _setup(hass, "nwa130be_v740")
    api_cls.assert_called_once_with("10.0.20.2", "admin", "pw", port=2387)


async def test_setup_without_stored_port_falls_back_to_22(hass):
    with patch("custom_components.ha_zyxel.ZyxelSSHAPI", wraps=ZyxelSSHAPI) as api_cls:
        await _setup(hass, "v712", data={"host": "10.0.20.2", "username": "admin", "password": "pw"})
    api_cls.assert_called_once_with("10.0.20.2", "admin", "pw", port=22)


async def test_nwa130be_gets_6ghz_radio_and_client_entities(hass):
    entry = await _setup(hass, "nwa130be_v740")

    assert _state(hass, entry, "sensor", "slot3_status").state == "Active"
    assert _state(hass, entry, "sensor", "clients_6ghz").state == "2"
    assert _state(hass, entry, "switch", "radio_6g").state == "on"


async def test_nwa130be_band_counters_do_not_overlap(hass):
    entry = await _setup(hass, "nwa130be_v740")

    assert _state(hass, entry, "sensor", "clients").state == "6"
    assert _state(hass, entry, "sensor", "clients_24ghz").state == "2"
    assert _state(hass, entry, "sensor", "clients_5ghz").state == "2"


async def test_nwa130be_existing_radio_entities_keep_working(hass):
    entry = await _setup(hass, "nwa130be_v740")

    radio_5g = _state(hass, entry, "sensor", "slot2_status")
    assert radio_5g.state == "Active"
    assert radio_5g.attributes["ssids"] == "Wiz_SSID_1, Wiz_SSID_5, Wiz_SSID_4"
    assert _state(hass, entry, "switch", "radio_24g").state == "on"


async def test_nwa130be_client_list_carries_mlo(hass):
    entry = await _setup(hass, "nwa130be_v740")

    client_list = _state(hass, entry, "sensor", "clients").attributes["client_list"]
    assert [c["mlo"] for c in client_list] == [False, True, False, False, False, False]


async def test_nwa130be_port_status_exposes_second_port(hass):
    entry = await _setup(hass, "nwa130be_v740")

    port = _state(hass, entry, "sensor", "port_status")
    assert port.state == "2500M/Full"
    assert [(p["port"], p["status"]) for p in port.attributes["ports"]] == [
        (1, "2500M/Full"),
        (2, "Down"),
    ]


async def test_dual_band_ap_gets_no_6ghz_entities(hass):
    entry = await _setup(hass, "v712")

    assert _state(hass, entry, "sensor", "slot2_status").state == "Active"
    assert _state(hass, entry, "sensor", "slot3_status") is None
    assert _state(hass, entry, "sensor", "clients_6ghz") is None
    assert _state(hass, entry, "switch", "radio_6g") is None
