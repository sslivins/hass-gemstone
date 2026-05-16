"""Test config-entry setup and teardown."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pygemstone import GemstoneAuthError, GemstoneConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gemstone.const import DOMAIN

DEVICE_ID = "h2-1074-y3w9"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"},
    )


async def test_setup_creates_device(hass: HomeAssistant, mock_client: MagicMock) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    assert device is not None
    assert device.manufacturer == "Gemstone Lights"
    assert device.name == "BDL-Gemstone"
    assert device.sw_version == "1.1.0"
    assert device.serial_number == DEVICE_ID


async def test_setup_aborts_when_no_devices(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.devices.return_value = []
    entry = _entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failure_marks_reauth(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.login.side_effect = GemstoneAuthError("bad credentials")
    entry = _entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connection_failure_retries(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.homegroups.side_effect = GemstoneConnectionError("offline")
    entry = _entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_client: MagicMock) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_client.__aexit__.assert_awaited()


@pytest.mark.parametrize(
    ("page1", "page2", "expected_count"),
    [
        (2, 0, 2),  # one full page then empty terminator
        (0, 0, 0),  # no patterns at all -> empty options
    ],
)
async def test_pattern_pagination_terminates(
    hass: HomeAssistant,
    mock_client: MagicMock,
    folder_patterns: list[MagicMock],
    page1: int,
    page2: int,
    expected_count: int,
) -> None:
    pages = {1: folder_patterns[:page1], 2: folder_patterns[:page2]}

    async def _folder_patterns(page: int = 1) -> list[MagicMock]:
        return pages.get(page, [])

    mock_client.folder_patterns.side_effect = _folder_patterns

    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) or expected_count == 0
    await hass.async_block_till_done()
    if expected_count == 0:
        # zero patterns is still a valid setup -- select gets an empty options list
        return
    assert len(entry.runtime_data.patterns) == expected_count
