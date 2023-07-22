"""Module to interface with Raumfeld smart speakers."""
import asyncio
import json
import re
import sys
import threading
from time import sleep

import aiohttp
import requests
import xmltodict

from . import auxilliary as aux
from . import upnp
from . import webservice as ws
from .common import log_critical, log_debug, log_error, log_info, log_warn, logger
from .constants import (
    BROWSE_CHILDREN,
    CID_SEARCH_ALLTRACKS,
    DEFAULT_PORT_WEBSERVICE,
    DELAY_FAST_UPDATE_CHECKS,
    DELAY_REQUEST_FAILURE_LONG_POLLING,
    MAX_RETRIES,
    PREFERRED_TIMEOUT_LONG_POLLING,
    REQUIRED_METADATA,
    SOUND_SUCCESS,
    SPOTIFY_ACTIVE,
    TIMEOUT_LONG_POLLING,
    TIMEOUT_WEBSERVICE_ACTION,
    TRANSPORT_STATE_TRANSITIONING,
    TRIGGER_UPDATE_DEVICES,
    TRIGGER_UPDATE_HOST_INFO,
    TRIGGER_UPDATE_SYSTEM_STATE,
    TRIGGER_UPDATE_ZONE_CONFIG,
    TYPE_MEDIA_SERVER,
    TYPE_RAUMFELD_DEVICE,
    USER_AGENT_RAUMFELD,
    USER_AGENT_RAUMFELD_OIDS,
)


class RaumfeldHost:
    """Class representing a Raumfeld host"""

    callback = None

    def __init__(self, host, port=DEFAULT_PORT_WEBSERVICE, session=None):
        """Initialize raumfeld host."""
        self.host = host
        self.port = str(port)
        self.location = "http://" + self.host + ":" + self.port
        self.snap = {}
        self._loop = None

        if not session:
            log_debug("Creating session for aiohttp requests.")
            self._aiohttp_session = aiohttp.ClientSession()
        else:
            self._aiohttp_session = session
            log_debug("Session for aiohttp requests was passed.")

        # up-to-date data from Raumfeld web service
        self.wsd = {
            "devices": {},
            "host_info": {},
            "system_state": {},
            "zone_config": {},
        }

        # up-to-date data derived from "self.wsd".
        self.resolve = {
            "devudn_to_name": {},
            "room_to_udn": {},
            "udn_to_devloc": {},
            "udn_to_room": {},
            "roomudn_to_powerstate": {},
            "roomudn_to_rendudn": {},
            "zoneudn_to_roomudnlst": {},
            "zone_to_rooms": {},
        }

        self.lists = {
            "locations": [],
            "raumfeld_device_udns": [],
            "rooms": [],
            "spotify_renderer": [],
            "zones": [],
        }

        self._init_done = {
            "devices": False,
            "host_info": False,
            "system_state": False,
            "zone_config": False,
        }

        # up-to-date data derived from "self.wsd".
        self.media_server_udn = ""
        self.update_available = False

    def set_logging_level(self, level):
        """set logging level of hassfeld."""
        logger.setLevel(level)

    async def async_host_is_valid(self):
        """Check whether host is a valid raumfeld host."""
        url = self.location + "/getHostInfo"
        timeout = aiohttp.ClientTimeout(total=3)
        session = aiohttp.ClientSession(timeout=timeout)

        try:
            response = await session.get(url)
            response_xml = await response.read()
            await session.close()
        except:
            await session.close()
            return False

        host_info = xmltodict.parse(response_xml)
        return bool("hostName" in host_info["hostInfo"])

    async def async_wait_initial_update(self):
        while False in self._init_done.values():
            await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)

    #
    # Functions for backgorund data updates from Raumfeld host.
    #

    def start_update_thread(self):
        """Start dedicated thread for web service data updates."""
        # Background thread updating "self.wsd".
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

        asyncio.run_coroutine_threadsafe(self.async_update_all(), self._loop)

        # Wait for first data as background updates are asynchronous.
        while False in self._init_done.values():
            sleep(DELAY_FAST_UPDATE_CHECKS)

    async def async_update_all(self, session=None):
        """Execut all update loops in a group."""
        if not session:
            log_debug("Creating session for webservice requests.")
            aiohttp_session = aiohttp.ClientSession()
        else:
            aiohttp_session = session
            log_debug("Session for webservice requests was passed.")
        try:
            await asyncio.gather(
                self.async_update_gethostinfo(aiohttp_session),
                self.async_update_getzones(aiohttp_session),
                self.async_update_listdevices(aiohttp_session),
                self.async_update_systemstatechannel(aiohttp_session),
            )
        except aiohttp.client_exceptions.ServerDisconnectedError:
            log_error("Updae loop interrupted because server disconnected")

    async def async_update_gethostinfo(self, session):
        """Update loop for host information."""
        url = self.location + "/getHostInfo"
        await self.__long_polling(session, url, self.__update_host_info)
        log_critical("Long-polling endless-loop for updating host information exited")

    async def async_update_getzones(self, session):
        """Update loop for zone information."""
        url = self.location + "/getZones"
        await self.__long_polling(session, url, self.__update_zone_config)
        log_critical("Long-polling endless-loop for updating zone configuration exited")

    async def async_update_listdevices(self, session):
        """Update loop for device information."""
        url = self.location + "/listDevices"
        await self.__long_polling(session, url, self.__update_devices)
        log_critical("Long-polling endless-loop for updating devices exited")

    async def async_update_systemstatechannel(self, session):
        """Update loop for software update information."""
        url = self.location + "/SystemStateChannel"
        await self.__long_polling(session, url, self.__update_system_state)
        log_critical("Long-polling endless-loop for updating system state exited")

    async def __long_polling(self, session, url, _callback):
        """Long-polling of web service interface."""
        update_id = None
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_LONG_POLLING)
        prefer_wait = "wait=" + str(PREFERRED_TIMEOUT_LONG_POLLING)
        headers = {"Prefer": prefer_wait}
        while True:
            if update_id:
                headers["updateID"] = update_id
            try:
                async with session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    if response.status == 200:
                        update_id = response.headers["updateID"]
                        _callback(await response.read())
                    elif response.status != 304:
                        await asyncio.sleep(DELAY_REQUEST_FAILURE_LONG_POLLING)
                        continue
            except asyncio.exceptions.TimeoutError:
                log_info("Long-polling timed out")
            except asyncio.exceptions.CancelledError:
                log_warn("Long-polling canceled")
                raise
            except aiohttp.client_exceptions.ServerDisconnectedError:
                log_error("Long-polling service disconnected")
                raise
            except:
                exc_info = "%s%s" % (sys.exc_info()[0], sys.exc_info()[1])
                log_critical("Long-polling failed with error: %s" % exc_info)
            await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)

    #
    # Callback functions for long polling.
    #

    def __update_host_info(self, content_xml):
        """Update internal data strucrure with host information."""
        gethostinfo = xmltodict.parse(content_xml)
        self.wsd["host_info"] = gethostinfo["hostInfo"]

        self._init_done["host_info"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_HOST_INFO)

    def __update_zone_config(self, content_xml):
        """Update internal data strucrure with zone information."""
        self.lists["rooms"] = []
        self.lists["zones"] = []
        self.resolve["roomudn_to_powerstate"] = {}
        self.resolve["room_to_udn"] = {}
        self.resolve["udn_to_room"] = {}
        self.resolve["zoneudn_to_roomudnlst"] = {}

        getzones = xmltodict.parse(content_xml, force_list=("zone", "room", "renderer"))
        self.wsd["zone_config"] = getzones["zoneConfig"]

        if "zones" in self.wsd["zone_config"]:
            for zone_itm in self.wsd["zone_config"]["zones"]["zone"]:
                zone_rooms = []
                zone_udn = zone_itm["@udn"]
                self.resolve["zoneudn_to_roomudnlst"][zone_udn] = []

                for room_itm in zone_itm["room"]:
                    room_name = room_itm["@name"]
                    room_udn = room_itm["@udn"]
                    renderer_udn = room_itm["renderer"][0]["@udn"]
                    zone_rooms.append(room_name)
                    self.lists["rooms"].append(room_name)
                    if "@powerState" in room_itm:
                        self.resolve["roomudn_to_powerstate"][room_udn] = room_itm[
                            "@powerState"
                        ]
                    else:
                        log_warn(
                            "No 'powerState' attribute provided for room: %s"
                            % room_name
                        )
                        self.resolve["roomudn_to_powerstate"][room_udn] = None
                    self.resolve["room_to_udn"][room_name] = room_udn
                    self.resolve["udn_to_room"][room_udn] = room_name
                    self.resolve["zoneudn_to_roomudnlst"][zone_udn].append(room_udn)
                    self.resolve["roomudn_to_rendudn"][room_udn] = renderer_udn

                self.lists["zones"].append(sorted(zone_rooms))

        if "unassignedRooms" in self.wsd["zone_config"]:
            for room in self.wsd["zone_config"]["unassignedRooms"]["room"]:
                room_name = room["@name"]
                room_udn = room["@udn"]
                renderer_udn = room["renderer"][0]["@udn"]
                if "@powerState" in room:
                    self.resolve["roomudn_to_powerstate"][room_udn] = room[
                        "@powerState"
                    ]
                else:
                    log_warn(
                        "No 'powerState' attribute provided for room: %s" % room_name
                    )
                    self.resolve["roomudn_to_powerstate"][room_udn] = None
                self.resolve["room_to_udn"][room_name] = room_udn
                self.resolve["udn_to_room"][room_udn] = room_name
                self.lists["rooms"].append(room_name)
                self.resolve["roomudn_to_rendudn"][room_udn] = renderer_udn
                if "@spotifyConnect" in room["renderer"][0]:
                    if room["renderer"][0]["@spotifyConnect"] == SPOTIFY_ACTIVE:
                        self.lists["spotify_renderer"].append(renderer_udn)

        self._init_done["zone_config"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_ZONE_CONFIG)

    def __update_devices(self, content_xml):
        """Update internal data strucrure with device information."""
        self.lists["locations"] = []
        self.lists["raumfeld_device_udns"] = []
        self.resolve["devudn_to_name"] = {}
        self.resolve["udn_to_devloc"] = {}

        listdevices = xmltodict.parse(content_xml, force_list=("device"))
        self.wsd["devices"] = listdevices["devices"]["device"]

        for device_itm in self.wsd["devices"]:
            device_loc = device_itm["@location"]
            device_type = device_itm["@type"]
            device_udn = device_itm["@udn"]
            if "#text" in device_itm:
                device_name = device_itm["#text"]
            else:
                log_warn("Missing '#text' key for device with UDN: %s" % device_udn)
            self.lists["locations"].append(device_loc)
            self.resolve["devudn_to_name"][device_udn] = device_name
            self.resolve["udn_to_devloc"][device_udn] = device_loc

            if device_type == TYPE_MEDIA_SERVER:
                self.media_server_udn = device_udn

            if device_type == TYPE_RAUMFELD_DEVICE:
                self.lists["raumfeld_device_udns"].append(device_udn)

        self._init_done["devices"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_DEVICES)

    def __update_system_state(self, content_xml):
        """Update internal data strucrure with software update information."""
        systemstatechannel = xmltodict.parse(content_xml)
        self.wsd["system_state"] = systemstatechannel["systemState"]

        update_available = self.wsd["system_state"]["updateAvailable"]["@value"]

        self.update_available = aux.str_to_bool(update_available)

        self._init_done["system_state"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_SYSTEM_STATE)

    #
    #  Helper functions
    #

    def get_zones(self):
        """Get zones from RaumfeldHost class.

        Returns list of sorted lists of rooms per zone. E.g.:
        [
            ['Badezimmer DG', 'Badezimmer OG', 'Schlafzimmer', 'Werkraum'],
            ['Wohnzimmer'],
            ["Filmraum", 'Küche']
        ]
        """
        zone_lst = [sorted(x) for x in self.lists["zones"]]
        return zone_lst

    def get_rooms(self):
        """Return list of rooms."""
        room_lst = self.lists["rooms"]
        return room_lst

    def get_raumfeld_device_udns(self):
        """Return list of unified device names."""
        devudn_lst = self.lists["raumfeld_device_udns"]
        return devudn_lst

    def device_udn_to_name(self, device_udn):
        """Convert device udn to device name."""
        device_name = self.resolve["devudn_to_name"][device_udn]
        return device_name

    def device_udn_to_location(self, device_udn):
        """Convert device udn to device location."""
        device_location = self.resolve["udn_to_devloc"][device_udn]
        return device_location

    def get_host_room(self):
        """Return room of raumfeld host."""
        return self.wsd["host_info"]["roomName"]

    def get_host_name(self):
        """Return raumfeld host's host name."""
        return self.wsd["host_info"]["hostName"]

    def roomlst_to_udnlst(self, room_lst):
        """Convert list of room names to list of unique device names."""
        udn_lst = []
        for room in room_lst:
            room_udn = self.resolve["room_to_udn"][room]
            udn_lst.append(room_udn)
        return udn_lst

    def roomlst_to_zoneudn(self, room_lst):
        """Convert list of rooms to zone UDN."""
        udn_lst = self.roomlst_to_udnlst(room_lst)
        zone_udn = self.roomudnlst_to_zoneudn(udn_lst)
        return zone_udn

    def roomudnlst_to_zoneudn(self, udn_lst):
        """Convert list of room UDN to zone UDN."""
        match = None
        zone_udnlst = self.resolve["zoneudn_to_roomudnlst"].keys()
        for zone_udn in zone_udnlst:
            if zone_udn in self.resolve["zoneudn_to_roomudnlst"]:
                zoneroom_udnlst = self.resolve["zoneudn_to_roomudnlst"][zone_udn]
                if aux.lists_have_same_values(zoneroom_udnlst, udn_lst):
                    match = zone_udn
                    break
        return match

    async def __async_wait_zone_creation(self, old_zone_udn, new_zone_room_lst):
        """Wait for zone creation published and recevied."""
        max_attempts = int(TIMEOUT_WEBSERVICE_ACTION / DELAY_FAST_UPDATE_CHECKS)
        for i in range(0, max_attempts):
            new_zone_udn = self.roomudnlst_to_zoneudn(new_zone_room_lst)
            if new_zone_udn is None:
                await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)
            elif new_zone_udn == old_zone_udn:
                await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)
            elif new_zone_udn not in self.resolve["udn_to_devloc"]:
                await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)
            else:
                break

    def zone_is_valid(self, room_lst):
        """Check whether passed zone is valid."""
        zone = sorted(room_lst)
        return bool(zone in self.lists["zones"])

    def room_is_valid(self, room):
        """Check whether passed room is valid."""
        return bool(room in self.lists["rooms"])

    def rooms_are_valid(self, room_lst):
        """Check whether passed rooms are valid."""
        for room in room_lst:
            if not self.room_is_valid(room):
                return False
        return True

    def room_is_spotify_single_room(self, room):
        """Check whether passed room is in spotify single-room mode."""
        room_udn = self.resolve["room_to_udn"][room]
        if room_udn in self.resolve["roomudn_to_rendudn"]:
            rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
            return bool(rend_udn in self.lists["spotify_renderer"])
        return False

    def location_is_valid(self, location):
        """Check whether passed location is valid."""
        return bool(location in self.lists["locations"])

    def get_room_power_state(self, room):
        """Get current power state of a room."""
        if self.room_is_valid(room):
            room_udn = self.resolve["room_to_udn"][room]
            power_state = self.resolve["roomudn_to_powerstate"][room_udn]
        else:
            power_state = None
        return power_state

    #
    # Raumfeld manipulation methods
    #

    async def async_create_zone(self, room_lst):
        """Create a new zone based on list of rooms.

        Parameters:
        room_lst -- List of rooms defining a zone.
        """
        udn_lst = self.roomlst_to_udnlst(room_lst)
        old_zone_udn = self.roomudnlst_to_zoneudn(udn_lst)
        await ws.async_connect_rooms_to_zone(
            self._aiohttp_session, self.location, room_udns=udn_lst
        )
        # Zone creation may take some time before taking effect.
        await self.__async_wait_zone_creation(old_zone_udn, room_lst)

    def add_room_to_zone(self, room, room_lst):
        """Adds a room to a zone."""
        return asyncio.run(self.async_add_room_to_zone(room, room_lst))

    async def async_add_room_to_zone(self, room, room_lst):
        """Adds a room to a zone."""
        room_udn = self.resolve["room_to_udn"][room]
        udn_lst = self.roomlst_to_udnlst(room_lst)
        zone_udn = self.roomudnlst_to_zoneudn(udn_lst)
        await ws.async_connect_room_to_zone(
            self._aiohttp_session, self.location, zone_udn, room_udn
        )

    def drop_room_from_zone(self, room, room_lst):
        """Removes a room from a zone."""
        return asyncio.run(self.async_drop_room_from_zone(room, room_lst))

    async def async_drop_room_from_zone(self, room, room_lst=None):
        """Removes a room from a zone. if room_lst is provided, it must exist in that zone"""
        room_udn = self.resolve["room_to_udn"][room]
        if room_lst is None:
            await ws.async_drop_room_job(self._aiohttp_session, self.location, room_udn)
        else:
            for room_name in room_lst:
                if room_name == room:
                    await ws.async_drop_room_job(
                        self._aiohttp_session, self.location, room_udn
                    )

    def set_zone_room_volume(self, zone_room_lst, volume, room_lst=None):
        """Sets volume of rooms in a zone to same level."""
        return asyncio.run(
            self.async_set_zone_room_volume(zone_room_lst, volume, room_lst)
        )

    async def async_set_zone_room_volume(self, zone_room_lst, volume, room_lst=None):
        """Sets volume of rooms in a zone to same level.

        Parameters:
        zone_room_lst -- List of rooms defining a zone
        volume -- Volume to to set for rooms.

        Optional parameters:
        room_lst -- List of rooms to change volume for. If absent, defaults to
        all rooms.
        """
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)

        if room_lst is None:
            room_udnlst = self.roomlst_to_udnlst(zone_room_lst)
        else:
            room_udnlst = self.roomlst_to_udnlst(room_lst)

        if zone_udn:
            for room_udn in room_udnlst:
                zone_loc = self.resolve["udn_to_devloc"][zone_udn]
                await upnp.async_set_room_volume(
                    self._aiohttp_session, zone_loc, room_udn, volume, instance_id=0
                )

    def set_zone_mute(self, zone_room_lst, mute=True):
        """Mute zone."""
        return asyncio.run(self.async_set_zone_mute(zone_room_lst, mute))

    async def async_set_zone_mute(self, zone_room_lst, mute=True):
        """Mute zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_set_mute(self._aiohttp_session, zone_loc, mute)

    def get_zone_mute(self, zone_room_lst):
        """Get mute status of zone."""
        return asyncio.run(self.async_get_zone_mute(zone_room_lst))

    async def async_get_zone_mute(self, zone_room_lst):
        """Get mute status of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        mute = await upnp.async_get_mute(self._aiohttp_session, zone_loc)
        return mute

    def set_zone_volume(self, zone_room_lst, volume):
        """Set volume to absolute level."""
        return asyncio.run(self.async_set_zone_volume(zone_room_lst, volume))

    async def async_set_zone_volume(self, zone_room_lst, volume):
        """Set volume to absolute level."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_set_volume(self._aiohttp_session, zone_loc, volume)

    def change_zone_volume(self, zone_room_lst, amount):
        """Change the volume of zone up or down."""
        return asyncio.run(self.async_change_zone_volume(zone_room_lst, amount))

    async def async_change_zone_volume(self, zone_room_lst, amount):
        """Change the volume of zone up or down."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_change_volume(self._aiohttp_session, zone_loc, amount)

    def zone_stop(self, zone_room_lst):
        """Stop playing media on zone."""
        return asyncio.run(self.async_zone_stop(zone_room_lst))

    async def async_zone_stop(self, zone_room_lst):
        """Stop playing media on zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_stop(self._aiohttp_session, zone_loc)

    def zone_play(self, zone_room_lst):
        """Play media on zone."""
        return asyncio.run(self.async_zone_play(zone_room_lst))

    async def async_zone_play(self, zone_room_lst):
        """Play media on zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_play(self._aiohttp_session, zone_loc)

    def zone_pause(self, zone_room_lst):
        """Pause playing media on zone."""
        return asyncio.run(self.async_zone_pause(zone_room_lst))

    async def async_zone_pause(self, zone_room_lst):
        """Pause playing media on zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_pause(self._aiohttp_session, zone_loc)

    def zone_seek(self, zone_room_lst, target):
        """Seek to position on zone."""
        return asyncio.run(self.async_zone_seek(zone_room_lst, target))

    async def async_zone_seek(self, zone_room_lst, target):
        """Seek to position on zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_seek(self._aiohttp_session, zone_loc, "ABS_TIME", target)

    def zone_next_track(self, zone_room_lst):
        """Play next track of zone."""
        return asyncio.run(self.async_zone_next_track(zone_room_lst))

    async def async_zone_next_track(self, zone_room_lst):
        """Play next track of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_next_track(self._aiohttp_session, zone_loc)

    def zone_previous_track(self, zone_room_lst):
        """Play previous track of zone."""
        return asyncio.run(self.async_zone_previous_track(zone_room_lst))

    async def async_zone_previous_track(self, zone_room_lst):
        """Play previous track of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_previous_track(self._aiohttp_session, zone_loc)

    def browse_media_server(self, object_id, browse_flag):
        """Browse media on the media server."""
        return asyncio.run(self.async_browse_media_server(object_id, browse_flag))

    async def async_browse_media_server(self, object_id, browse_flag):
        """Browse media on the media server."""
        http_headers = None

        if browse_flag == BROWSE_CHILDREN:
            if object_id in USER_AGENT_RAUMFELD_OIDS:
                http_headers = {"User-Agent": USER_AGENT_RAUMFELD}

        media_server_loc = self.resolve["udn_to_devloc"][self.media_server_udn]
        return await upnp.async_browse(
            self._aiohttp_session,
            media_server_loc,
            object_id,
            browse_flag,
            http_headers=http_headers,
        )

    def search_media_server(
        self,
        container_id=0,
        search_criteria="",
        filter_criteria="*",
        starting_index=0,
        requested_count=0,
        sort_criteria="",
    ):
        """Search the media server."""
        return asyncio.run(
            self.async_search_media_server(
                container_id,
                search_criteria,
                filter_criteria,
                starting_index,
                requested_count,
                sort_criteria,
            )
        )

    async def async_search_media_server(
        self,
        container_id=0,
        search_criteria="",
        filter_criteria="*",
        starting_index=0,
        requested_count=0,
        sort_criteria="",
    ):
        """Search the media server.

        Parameters:
        search_criteria='raumfeld:any contains "No son of mine"
        """
        media_server_loc = self.resolve["udn_to_devloc"][self.media_server_udn]
        response = await upnp.async_search(
            self._aiohttp_session,
            media_server_loc,
            container_id,
            search_criteria,
            filter_criteria,
            starting_index,
            requested_count,
            sort_criteria,
        )
        return response

    def search_for_play(self, container_id, search_criteria):
        """Search for media and return uri and meta data."""
        return asyncio.run(self.async_search_for_play(container_id, search_criteria))

    async def async_search_for_play(self, container_id, search_criteria):
        """Search for media and return uri and meta data."""
        requested_count = 1
        sort_criteria = "+upnp:artist,-dc:date,+dc:title"
        metadata_xml = await self.async_search_media_server(
            container_id,
            search_criteria,
            requested_count=(requested_count),
            sort_criteria=sort_criteria,
        )
        metadata = xmltodict.parse(metadata_xml)

        if "item" in metadata["DIDL-Lite"]:
            uri = metadata["DIDL-Lite"]["item"]["res"]["#text"]
        else:
            uri = None

        return uri, metadata_xml

    def set_av_transport_uri(
        self, zone_room_lst, current_uri, current_uri_metadata=None
    ):
        """Set the URI of the track to play and it's meta data in a zone."""
        return asyncio.run(
            self.async_set_av_transport_uri(
                zone_room_lst, current_uri, current_uri_metadata
            )
        )

    async def async_set_av_transport_uri(
        self, zone_room_lst, current_uri, current_uri_metadata=None
    ):
        """Set the URI of the track to play and it's meta data in a zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        if current_uri_metadata is None:
            current_uri_metadata = xmltodict.unparse(REQUIRED_METADATA)
        await upnp.async_set_av_transport_uri(
            self._aiohttp_session,
            zone_loc,
            current_uri,
            current_uri_metadata,
            instance_id=0,
        )

    def search_and_zone_play(
        self, zone_room_lst, search_criteria, container_id=CID_SEARCH_ALLTRACKS
    ):
        """Search for track and play first found."""
        return asyncio.run(
            self.async_search_and_zone_play(
                zone_room_lst, search_criteria, container_id
            )
        )

    async def async_search_and_zone_play(
        self, zone_room_lst, search_criteria, container_id=CID_SEARCH_ALLTRACKS
    ):
        """Search for track and play first found."""
        uri, uri_metadata = await self.async_search_for_play(
            container_id, search_criteria
        )
        await self.async_set_av_transport_uri(zone_room_lst, uri, uri_metadata)

    def get_media_info(self, zone_room_lst):
        """Get media information of zone."""
        return asyncio.run(self.async_get_media_info(zone_room_lst))

    async def async_get_media_info(self, zone_room_lst):
        """Get media information of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return await upnp.async_get_media_info(self._aiohttp_session, zone_loc)

    def get_play_mode(self, zone_room_lst):
        """Get play mode of zone."""
        return asyncio.run(self.async_get_play_mode(zone_room_lst))

    async def async_get_play_mode(self, zone_room_lst):
        """Get play mode of zone."""
        transport_info = await self.async_get_transport_settings(zone_room_lst)
        if transport_info:
            return transport_info["PlayMode"]

    def get_transport_info(self, zone_room_lst):
        """Get transport information of zone."""
        return asyncio.run(self.async_get_transport_info(zone_room_lst))

    async def async_get_transport_info(self, zone_room_lst):
        """Get transport information of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return await upnp.async_get_transport_info(self._aiohttp_session, zone_loc)

    def get_zone_volume(self, zone_room_lst):
        """Get volume of zone."""
        return asyncio.run(self.async_get_zone_volume(zone_room_lst))

    async def async_get_zone_volume(self, zone_room_lst):
        """Get volume of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return await upnp.async_get_volume(self._aiohttp_session, zone_loc)

    def get_position_info(self, zone_room_lst):
        """Get play information from zone."""
        return asyncio.run(self.async_get_position_info(zone_room_lst))

    async def async_get_position_info(self, zone_room_lst):
        """Get play information from zone."""
        response = False
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        if zone_udn is not None:
            zone_loc = self.resolve["udn_to_devloc"][zone_udn]
            response = await upnp.async_get_position_info(
                self._aiohttp_session, zone_loc
            )
        return response

    def get_zone_position(self, zone_room_lst):
        """Get play position from zone."""
        return asyncio.run(self.async_get_zone_position(zone_room_lst))

    async def async_get_zone_position(self, zone_room_lst):
        """Get play position from zone."""
        position_info = await self.async_get_position_info(zone_room_lst)
        return position_info["AbsTime"]

    def get_transport_settings(self, zone_room_lst):
        """Get transport settings from zone."""
        return asyncio.run(self.async_get_transport_settings(zone_room_lst))

    async def async_get_transport_settings(self, zone_room_lst):
        """Get transport settings from zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return await upnp.async_get_transport_settings(self._aiohttp_session, zone_loc)

    def set_play_mode(self, zone_room_lst, play_mode):
        """Set play mode of zone."""
        return asyncio.run(self.async_set_play_mode(zone_room_lst, play_mode))

    async def async_set_play_mode(self, zone_room_lst, play_mode):
        """Set play mode of zone."""
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        await upnp.async_set_play_mode(self._aiohttp_session, zone_loc, play_mode)

    def room_play_system_sound(self, room, sound=SOUND_SUCCESS):
        """Play system sound on a room."""
        return asyncio.run(self.async_room_play_system_sound(room, sound))

    async def async_room_play_system_sound(self, room, sound=SOUND_SUCCESS):
        """Play system sound on a room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_play_system_sound(self._aiohttp_session, rend_loc, sound)

    def save_zone(self, zone_room_lst, repl_snap=False):
        """Create backup of media state for later restore."""
        return asyncio.run(self.async_save_zone(zone_room_lst, repl_snap))

    async def async_save_zone(self, zone_room_lst, repl_snap=False):
        """Create backup of media state for later restore."""
        media_info = await self.async_get_media_info(zone_room_lst)
        position_info = await self.async_get_position_info(zone_room_lst)
        volume = await self.async_get_zone_volume(zone_room_lst)
        mute = await self.async_get_zone_mute(zone_room_lst)
        key = repr(zone_room_lst)
        track = position_info["Track"]
        fii_par = "fii=" + str(track - 1)
        if key not in self.snap or repl_snap:
            self.snap[key] = {}
            self.snap[key]["uri"] = media_info["CurrentURI"]
            self.snap[key]["metadata"] = media_info["CurrentURIMetaData"]
            self.snap[key]["abs_time"] = position_info["AbsTime"]
            self.snap[key]["fii_par"] = fii_par
            self.snap[key]["volume"] = volume
            self.snap[key]["mute"] = mute
            log_debug("Creating snapshot: 'snap[%s]' = '%s'" % (key, self.snap[key]))

    def restore_zone(self, zone_room_lst, del_snap=True):
        """restore media state from previous snapshot."""
        return asyncio.run(self.async_restore_zone(zone_room_lst, del_snap))

    async def async_restore_zone(self, zone_room_lst, del_snap=True):
        """restore media state from previous snapshot."""
        key = repr(zone_room_lst)
        retries = 0
        if key in self.snap:
            orig_uri = self.snap[key]["uri"]
            fii_par = self.snap[key]["fii_par"]
            uri = re.sub("fii=[0-9]+", fii_par, orig_uri)
            metadata = self.snap[key]["metadata"]
            abs_time = self.snap[key]["abs_time"]
            volume = self.snap[key]["volume"]
            mute = self.snap[key]["mute"]
            await self.async_set_zone_volume(zone_room_lst, 0)
            await self.async_set_zone_mute(zone_room_lst, mute)
            await self.async_set_av_transport_uri(zone_room_lst, uri, metadata)
            while retries < MAX_RETRIES:
                transport_info = await self.async_get_transport_info(zone_room_lst)
                transport_state = transport_info["CurrentTransportState"]
                if transport_state != TRANSPORT_STATE_TRANSITIONING:
                    break
                await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)
                retries += 1
            await self.async_zone_seek(zone_room_lst, abs_time)
            await self.async_set_zone_volume(zone_room_lst, volume)
            if del_snap:
                self.snap.pop(key, None)

    async def async_enter_automatic_standby(self, room):
        """Put room speakers into automatic stand-by."""
        room_udn = self.resolve["room_to_udn"][room]
        await ws.async_enter_automatic_standby(
            self._aiohttp_session, self.location, room_udn
        )

    async def async_enter_manual_standby(self, room):
        """Put room speakers into manual stand-by (turn off)."""
        room_udn = self.resolve["room_to_udn"][room]
        await ws.async_enter_manual_standby(
            self._aiohttp_session, self.location, room_udn
        )

    async def async_leave_standby(self, room):
        """Weak room speakers up from stand-by."""
        room_udn = self.resolve["room_to_udn"][room]
        await ws.async_leave_standby(self._aiohttp_session, self.location, room_udn)

    # Spotify single-room methods

    def room_play(self, room):
        """Play media on room."""
        return asyncio.run(self.async_room_play(room))

    async def async_room_play(self, room):
        """Play media on room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_play(self._aiohttp_session, rend_loc)

    def room_pause(self, room):
        """Pause media on room."""
        return asyncio.run(self.async_room_pause(room))

    async def async_room_pause(self, room):
        """Pause media on room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_pause(self._aiohttp_session, rend_loc)

    def get_room_transport_info(self, room):
        """Get transport information of room."""
        return asyncio.run(self.async_get_room_transport_info(room))

    async def async_get_room_transport_info(self, room):
        """Get transport information of room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        return await upnp.async_get_transport_info(self._aiohttp_session, rend_loc)

    def room_next_track(self, room):
        """Play next track of room."""
        return asyncio.run(self.async_room_next_track(room))

    async def async_room_next_track(self, room):
        """Play next track of room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_next_track(self._aiohttp_session, rend_loc)

    def room_previous_track(self, room):
        """Play previous track of room."""
        return asyncio.run(self.async_room_previous_track(room))

    async def async_room_previous_track(self, room):
        """Play previous track of room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_previous_track(self._aiohttp_session, rend_loc)

    def get_room_volume(self, room):
        """Get volume of room."""
        return asyncio.run(self.async_get_room_volume(room))

    async def async_get_room_volume(self, room):
        """Get volume of room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        return await upnp.async_get_volume(self._aiohttp_session, rend_loc)

    def set_room_volume(self, room, volume):
        """Set volume of room."""
        return asyncio.run(self.async_set_room_volume(room, volume))

    async def async_set_room_volume(self, room, volume):
        """Set volume of room."""
        room_udn = self.resolve["room_to_udn"][room]
        rend_udn = self.resolve["roomudn_to_rendudn"][room_udn]
        rend_loc = self.resolve["udn_to_devloc"][rend_udn]
        await upnp.async_set_volume(self._aiohttp_session, rend_loc, volume)

    # Speaker methods
    def get_device_renderer(self, udn):
        """Return renderer UDN of speaker UDN."""
        return asyncio.run(self.async_get_device_renderer(udn))

    async def async_get_device_renderer(self, udn):
        """Return renderer UDN of speaker UDN."""
        location = self.device_udn_to_location(udn)
        return await upnp.async_get_device(self._aiohttp_session, location, "renderer")

    def get_device_info(self, udn):
        """Return software version of device."""
        return asyncio.run(self.async_get_device_info(udn))

    async def async_get_device_info(self, udn):
        """Return software version of device."""
        location = self.device_udn_to_location(udn)
        return await upnp.async_get_info(self._aiohttp_session, location)

    def get_device_manufacturer(self, udn):
        """Return manufacturer of device."""
        return asyncio.run(self.async_get_device_manufacturer(udn))

    async def async_get_device_manufacturer(self, udn):
        """Return manufacturer of device."""
        location = self.device_udn_to_location(udn)
        return await upnp.async_get_manufacturer(self._aiohttp_session, location)

    def get_device_model_name(self, udn):
        """Return model name of device."""
        return asyncio.run(self.async_get_device_model_name(udn))

    async def async_get_device_model_name(self, udn):
        """Return model name of device."""
        location = self.device_udn_to_location(udn)
        return await upnp.async_get_model_name(self._aiohttp_session, location)

    def get_device_update_info(self, udn):
        """Return information of available software update."""
        return asyncio.run(self.async_get_device_update_info(udn))

    async def async_get_device_update_info(self, udn):
        """Return information of available software update."""
        location = self.device_udn_to_location(udn)
        return await upnp.async_get_update_info(self._aiohttp_session, location)

    def get_device_update_info_version(self, udn):
        """Return version of available software update."""
        return asyncio.run(self.async_get_device_update_info_version(udn))

    async def async_get_device_update_info_version(self, udn):
        """Return version of available software update."""
        response = await self.async_get_device_update_info(udn)

        if response:
            if "Version" in response:
                return response["Version"]
