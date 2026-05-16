"""Common test fixtures for hass-gemstone."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pygemstone import DeviceState, Folder, FolderPattern, HomeGroup, Pattern


# pytest-homeassistant-custom-component auto-enables custom integrations via this
# fixture name (must be present even if it does nothing extra).
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # type: ignore[no-untyped-def]
    """Automatically enable loading of custom_components in every test."""
    yield


def _pattern_raw(pid: str, name: str, brightness: int) -> dict[str, Any]:
    return {
        "id": pid,
        "name": name,
        "colors": [0xFFFF0000, 0xFFFFFFFF, 0xFF00FF00],
        "animation": "motionless",
        "brightness": brightness,
        "speed": 128,
        "direction": 0,
        "backgroundColor": 0,
        "referencePatternId": None,
    }


def _folder_raw(folder_id: str, name: str, gemstone_managed: bool = False) -> dict[str, Any]:
    return {
        "folderId": folder_id,
        "name": name,
        "icon": "🎄",
        "ownerId": "user-1",
        "gemstoneManaged": gemstone_managed,
        "hidden": False,
    }


def _folder_pattern_raw(
    fp_id: str, folder_id: str, pattern_raw: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": fp_id,
        "folderId": folder_id,
        "ownerId": "user-1",
        "patternData": pattern_raw,
        "isFavorite": False,
        "hidden": False,
        "gemstoneManaged": False,
    }


@pytest.fixture
def gemstone_pattern() -> Pattern:
    """Currently-playing pattern (brightness 200) -- lives in the Christmas folder."""
    return Pattern.from_api(_pattern_raw("pat-1", "Christmas Classic", 200))


@pytest.fixture
def gemstone_pattern_alt() -> Pattern:
    """Another saved pattern -- lives in the Halloween folder."""
    return Pattern.from_api(_pattern_raw("pat-2", "Halloween", 180))


@pytest.fixture
def gemstone_pattern_halloween_2() -> Pattern:
    """Second Halloween pattern, so the folder has more than one option."""
    return Pattern.from_api(_pattern_raw("pat-3", "Spooky", 200))


@pytest.fixture
def device_state(gemstone_pattern: Pattern) -> DeviceState:
    return DeviceState(
        device_id="h2-1074-y3w9",
        on_state=True,
        pattern=gemstone_pattern,
        raw={"id": "h2-1074-y3w9", "onState": True, "pattern": gemstone_pattern.raw},
    )


@pytest.fixture
def homegroup() -> HomeGroup:
    return HomeGroup(id="hg-1", name="My Home", role="owner")


@pytest.fixture
def mock_device(device_state: DeviceState) -> MagicMock:
    """Build a fake pygemstone.Device for tests."""
    dev = MagicMock(name="Device")
    dev.id = "h2-1074-y3w9"
    dev.name = "BDL-Gemstone"
    dev.firmware = "1.1.0"
    dev.homegroup_id = "hg-1"
    dev.refresh = AsyncMock(return_value=device_state)
    dev.turn_on = AsyncMock(return_value="tx-on")
    dev.turn_off = AsyncMock(return_value="tx-off")
    dev.play_pattern = AsyncMock(return_value="tx-pat")
    return dev


@pytest.fixture
def folders() -> list[Folder]:
    """Two folders so the dropdown has something interesting to switch between."""
    return [
        Folder.from_api(_folder_raw("fld-xmas", "Christmas")),
        Folder.from_api(_folder_raw("fld-hween", "Halloween")),
    ]


@pytest.fixture
def folder_patterns(
    gemstone_pattern: Pattern,
    gemstone_pattern_alt: Pattern,
    gemstone_pattern_halloween_2: Pattern,
) -> list[FolderPattern]:
    """List returned by client.folder_patterns(page=1)."""
    return [
        FolderPattern.from_api(
            _folder_pattern_raw("fp-1", "fld-xmas", gemstone_pattern.raw)
        ),
        FolderPattern.from_api(
            _folder_pattern_raw("fp-2", "fld-hween", gemstone_pattern_alt.raw)
        ),
        FolderPattern.from_api(
            _folder_pattern_raw(
                "fp-3", "fld-hween", gemstone_pattern_halloween_2.raw
            )
        ),
    ]


@pytest.fixture
def mock_client(
    mock_device: MagicMock,
    homegroup: HomeGroup,
    folders: list[Folder],
    folder_patterns: list[FolderPattern],
) -> Generator[MagicMock]:
    """Patch GemstoneClient everywhere the integration imports it."""
    instance = MagicMock(name="GemstoneClient")
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    instance.login = AsyncMock(return_value=None)
    instance.homegroups = AsyncMock(return_value=[homegroup])
    instance.devices = AsyncMock(return_value=[mock_device])
    instance.folders = AsyncMock(return_value=folders)

    async def _folder_patterns(page: int = 1) -> list[FolderPattern]:
        # Page 1 returns the catalogue, page 2+ returns empty (terminator).
        return folder_patterns if page == 1 else []

    instance.folder_patterns = AsyncMock(side_effect=_folder_patterns)

    with (
        patch(
            "custom_components.gemstone.GemstoneClient",
            return_value=instance,
        ) as init_patch,
        patch(
            "custom_components.gemstone.config_flow.GemstoneClient",
            return_value=instance,
        ) as flow_patch,
    ):
        instance._init_patch = init_patch
        instance._flow_patch = flow_patch
        yield instance
