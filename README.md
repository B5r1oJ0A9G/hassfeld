# hassfeld

[![CI](https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/ci.yaml/badge.svg)](https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/github-code-scanning/codeql/badge.svg?branch=master)](https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/github-code-scanning/codeql)
[![PyPI version](https://img.shields.io/pypi/v/hassfeld)](https://pypi.org/project/hassfeld/)

Python library for controlling **Teufel Smart Speakers** (Raumfeld multiroom system). Designed as the companion library for the [teufel_raumfeld](https://github.com/B5r1oJ0A9G/teufel_raumfeld) Home Assistant integration, but can be used standalone in any Python project.

The module provides both asynchronous (`asyncio`) and synchronous APIs.

---

## Features

- **Media discovery** — Find rooms, zones, and their playback capabilities via UPnP/DLNA
- **Media control** — Play, pause, stop, next, previous, seek
- **Volume control** — Per-room and per-zone
- **Source selection** — Line-In, Spotify, Tidal, Internet radio, local music
- **Search** — Search and play tracks across all sources
- **Zone management** — Create, modify, and snapshot room groups
- **Web service API** — Full access to the Raumfeld REST/SSDP services

---

## Installation

```bash
pip install hassfeld
```

---

## Usage

### Async (recommended)

```python
import asyncio
import aiohttp
import hassfeld


async def main():
    host = "teufel-host.example.com"
    port = 47365
    session = aiohttp.ClientSession()
    raumfeld = hassfeld.RaumfeldHost(host, port, session=session)

    asyncio.create_task(raumfeld.async_update_all(session))
    await raumfeld.async_wait_initial_update()

    zone = ["Master Bedroom"]

    media_info = await raumfeld.async_get_media_info(zone)
    print(f"Media info: {media_info}")

    await session.close()


asyncio.run(main())
```

### Synchronous

```python
import hassfeld

raumfeld_host = "teufel-host.example.com"
zone = ["Living room", "Kitchen"]

raumfeld = hassfeld.RaumfeldHost(raumfeld_host)
raumfeld.start_update_thread()
raumfeld.search_and_zone_play(zone, 'raumfeld:any contains "Like a Rolling Stone"')
```

> **Note:** The synchronous API currently has known issues. See [issue #3](https://github.com/B5r1oJ0A9G/hassfeld/issues/3). Async usage is recommended.

---

## Links

| | |
|---|---|
| Source code | [GitHub](https://github.com/B5r1oJ0A9G/hassfeld) |
| Issue tracker | [GitHub Issues](https://github.com/B5r1oJ0A9G/hassfeld/issues) |
| PyPI | [hassfeld on PyPI](https://pypi.org/project/hassfeld/) |
| teufel_raumfeld | [HA Integration](https://github.com/B5r1oJ0A9G/teufel_raumfeld) |

---

## License

GNU General Public License v3 (GPLv3)
