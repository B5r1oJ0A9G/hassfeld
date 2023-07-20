
hassfeld
========

|Language grade Python|

hassfeld is a module primarily aimed to integrated Teufel Smart Speaker (aka Raumfeld Multiroom) into https://www.home-assistant.io/. However, the design is not tailored to Home Assistant and can be used as a module to any Pyhton program to control the Teufel Smart Speaker. The module also provides corresponding asyncio methods.

Look how it is to use with asyncrhonous I/O::

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

The use with blocking I/O was supported too but is currently broken::

    import hassfeld
    raumfeld_host = "teufel-host.example.com"
    zone = [ "Living room", "Kitchen" ]
    raumfeld = hassfeld.RaumfeldHost(raumfeld_host)
    raumfeld.start_update_thread()
    raumfeld.search_and_zone_play(zone, 'raumfeld:any contains "Like a Rolling Stone"')


Features
--------

- Management and snapshot of zones.
- Search and play songs.

Install hassfeld by running::

    python3 -m pip install hassfeld

Contribute
----------

- Issue Tracker: https://github.com/B5r1oJ0A9G/hassfeld/issues
- Source Code: https://github.com/B5r1oJ0A9G/hassfeld

License
-------

The project is licensed under the GNU General Public License v3 (GPLv3).


.. |Language grade Python| image:: https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/github-code-scanning/codeql/badge.svg?branch=master
   :target: https://github.com/B5r1oJ0A9G/hassfeld/actions/workflows/github-code-scanning/codeql
