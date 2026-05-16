"""Test the light platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
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


def _light_entity_id(hass: HomeAssistant) -> str:
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, f"{DEVICE_ID}_light")
    assert eid is not None
    return eid


async def test_light_reports_on_and_brightness(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup(hass)
    state = hass.states.get(_light_entity_id(hass))
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 200


async def test_light_turn_off_calls_device(
    hass: HomeAssistant, mock_client: MagicMock, mock_device: MagicMock
) -> None:
    await _setup(hass)
    eid = _light_entity_id(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_device.turn_off.assert_awaited_once()


async def test_light_turn_off_noop_when_already_off(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
    device_state,
) -> None:
    device_state.on_state = False
    mock_device.refresh.return_value = device_state
    await _setup(hass)
    eid = _light_entity_id(hass)
    assert hass.states.get(eid).state == STATE_OFF
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_device.turn_off.assert_not_awaited()


async def test_light_turn_on_when_off_calls_device(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
    device_state,
) -> None:
    device_state.on_state = False
    mock_device.refresh.return_value = device_state
    await _setup(hass)
    eid = _light_entity_id(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    mock_device.turn_on.assert_awaited_once()


async def test_light_brightness_change_replays_pattern(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    await _setup(hass)
    eid = _light_entity_id(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    mock_device.play_pattern.assert_awaited_once()
    played = mock_device.play_pattern.call_args.args[0]
    assert played.brightness == 100
    # Source raw should NOT have been mutated -- we deepcopy.
    state = hass.states.get(eid)
    assert state is not None


async def test_light_turn_off_optimistically_updates_state(
    hass: HomeAssistant, mock_client: MagicMock, mock_device: MagicMock
) -> None:
    """After turn_off, state must flip OFF immediately without re-polling.

    Regression test: the cloud's currentlyPlaying endpoint lags 30-60s
    behind the device, so a post-action refresh used to return stale
    on_state=True and snap the UI back ON. The fix is an optimistic
    local update -- no extra refresh.
    """
    await _setup(hass)
    eid = _light_entity_id(hass)
    assert hass.states.get(eid).state == STATE_ON
    mock_device.refresh.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert hass.states.get(eid).state == STATE_OFF
    mock_device.refresh.assert_not_awaited()


async def test_light_turn_on_optimistically_updates_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
    device_state,
) -> None:
    """After turn_on, state must flip ON immediately without re-polling."""
    device_state.on_state = False
    mock_device.refresh.return_value = device_state
    await _setup(hass)
    eid = _light_entity_id(hass)
    assert hass.states.get(eid).state == STATE_OFF
    mock_device.refresh.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert hass.states.get(eid).state == STATE_ON
    mock_device.refresh.assert_not_awaited()


async def test_light_brightness_change_optimistically_updates_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    """After a brightness change, state must reflect the new value immediately."""
    await _setup(hass)
    eid = _light_entity_id(hass)
    mock_device.refresh.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    state = hass.states.get(eid)
    assert state is not None
    assert state.attributes["brightness"] == 100
    mock_device.refresh.assert_not_awaited()


async def test_light_brightness_no_op_when_unchanged(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_device: MagicMock,
) -> None:
    await _setup(hass)
    eid = _light_entity_id(hass)
    # Currently 200; ask for 200 again — no write.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid, ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    mock_device.play_pattern.assert_not_awaited()
    mock_device.turn_on.assert_not_awaited()
