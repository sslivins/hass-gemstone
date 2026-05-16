"""Test the select platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gemstone.const import DOMAIN

DEVICE_ID = "h2-1074-y3w9"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _select_entity_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(SELECT_DOMAIN, DOMAIN, f"{DEVICE_ID}_pattern")
    assert eid is not None
    return eid


async def test_select_options_include_all_patterns(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    state = hass.states.get(_select_entity_id(hass))
    assert state is not None
    options = state.attributes["options"]
    assert sorted(options) == ["Christmas Classic", "Halloween"]


async def test_select_current_option_matches_active_pattern(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    state = hass.states.get(_select_entity_id(hass))
    assert state is not None
    assert state.state == "Christmas Classic"


async def test_select_option_calls_play_pattern(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    await _setup(hass)
    eid = _select_entity_id(hass)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eid, ATTR_OPTION: "Halloween"},
        blocking=True,
    )
    mock_device.play_pattern.assert_awaited_once()
    played = mock_device.play_pattern.call_args.args[0]
    assert played.name == "Halloween"


async def test_select_option_optimistically_updates_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    """After selecting a pattern, state must reflect the new pick immediately.

    Regression test: the cloud's currentlyPlaying endpoint lags 30-60s
    behind the device, so a post-action refresh used to return the
    previous pattern and snap the dropdown back. The fix is an
    optimistic local update -- no extra refresh.
    """
    await _setup(hass)
    eid = _select_entity_id(hass)
    assert hass.states.get(eid).state == "Christmas Classic"
    mock_device.refresh.reset_mock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eid, ATTR_OPTION: "Halloween"},
        blocking=True,
    )
    assert hass.states.get(eid).state == "Halloween"
    mock_device.refresh.assert_not_awaited()
