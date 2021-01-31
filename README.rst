
hassfeld
========

hassfeld is a module primarily aimed to integrated Teufel smart speaker (aka Raumfeld Multiroom) into https://www.home-assistant.io/.

Look how it is to use::

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


