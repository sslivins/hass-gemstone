# hass-gemstone

Home Assistant custom integration for **Gemstone Lights** permanent
Christmas-light controllers.

This integration is a thin wrapper around
[`pygemstone`](https://github.com/sslivins/pygemstone)
([PyPI](https://pypi.org/project/pygemstone/)), which talks to
Gemstone's AWS-Amplify cloud on your behalf.

> **Status: alpha.** Power on/off, brightness, and pattern selection
> work end-to-end. Real-time push (AppSync) is not used — the
> Gemstone iOS app itself doesn't open it either, so the integration
> polls instead.

## Requirements

- Home Assistant 2026.5 or newer
- A working Gemstone Lights mobile-app account (email + password)
- A Gemstone controller already paired with the app

## Installation (HACS)

This integration is not yet in the default HACS list. To install it now:

1. In HACS, choose **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/sslivins/hass-gemstone` as an **Integration**.
3. Install **Gemstone Lights**.
4. Restart Home Assistant.
5. **Settings → Devices & Services → Add Integration → Gemstone Lights**,
   sign in with your Gemstone app credentials.

## What it does

Discovers every Gemstone controller across every home group on your
account, polls each one every 30 seconds, and exposes:

- **`light.<name>`** — power on/off + brightness 0–255. Brightness is
  applied to the currently-playing pattern (the colour scheme of that
  pattern is preserved).
- **`select.<name>_pattern`** — pick which of your saved patterns to
  play. Options are pulled from your folders at startup.

After every command the integration immediately re-polls the
controller, so the UI reflects the new state within a second or two.

## What it does *not* do (yet)

- **RGB colour control.** Colour is determined by the active pattern.
  Set up the colour palettes you like in the Gemstone app and pick
  them via the `select` entity.
- **Animation / speed / direction tweaks.** Patterns are played as
  authored.
- **Timers, autopilot events, downloadable patterns.** All exposed by
  `pygemstone` but not yet surfaced as HA entities.
- **Push updates.** The Gemstone backend has an AppSync GraphQL
  endpoint, but the official iOS app never opens it; we poll for the
  same reason it does.

## Credentials

Your Gemstone password is stored only in the Home Assistant config
entry (encrypted at rest like every other HA credential). It is never
written to logs by this integration.

## Development

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1   # Windows PowerShell
pip install -e ".[tests]"
ruff check custom_components/gemstone tests
mypy custom_components/gemstone
pytest
```

## License

MIT — see [LICENSE](LICENSE).
