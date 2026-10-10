# Tests

## Running

```bash
pip install pytest-homeassistant-custom-component paramiko
pytest
```

Home Assistant does not run on Windows (`import fcntl`), so run the suite on
Linux, macOS or WSL. `pytest.ini` sets `asyncio_mode = auto`, which the
HA-level tests need.

## What's here

- `test_parsers.py` - regression tests for every `_parse_*` method in
  `zyxel_ssh_api.py`, run against real CLI output captured from a physical
  NWA50AX (see `fixtures/`). These exist so a firmware update, or a future
  change to the parsing code, can be checked without needing physical access
  to the AP.
- `test_config_flow.py` - the config flow stores and uses the SSH port.
- `test_init.py` - full entry setup with the real parsing pipeline, every
  SSH command answered from one fixture directory: which entities exist
  (6GHz only on tri-band APs) and what they report.
- `fixtures/nwa130be_v740/` - real output from a tri-band NWA130BE on
  firmware `7.40(ACIL.1)`. MAC/IP addresses and SSID names are anonymized and
  the station list is cut down to 6 clients (2.4/5/6GHz, one MLO client);
  everything else is as captured.
- `fixtures/v712/` - real, unedited `show ...` command output captured on
  firmware `7.12(ABYW.0)`. One file per command (SSID-specific commands get
  one file per SSID). If you're on a different firmware and hit a parsing
  issue, capturing your own output the same way and adding it as a new
  `fixtures/v<version>/` directory is the most useful thing you can
  contribute - see the module docstring in `zyxel_ssh_api.py` for the list of
  commands used.

## Adding a new firmware version

1. SSH into the AP and run each command listed in `zyxel_ssh_api.py`'s module
   docstring, saving the raw output.
2. Create `tests/fixtures/v<version>/` with one `.txt` file per command
   (see `v712/` for the naming convention).
3. Duplicate `test_parsers.py`'s test functions for the new version (or
   parametrize over both), asserting the values you'd expect from your
   capture.
4. If a test fails, that's exactly the point - it means this firmware changed
   something in the output format, and you've found it via a regression test
   instead of a live production failure.
