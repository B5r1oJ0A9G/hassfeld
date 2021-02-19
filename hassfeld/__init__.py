"""Module to interface with Raumfeld smart speakers"""
import asyncio
import json
import threading
from time import sleep

import aiohttp
import requests
import xmltodict

from . import auxilliary as aux
from . import upnp
from . import webservice as ws
from .constants import (BROWSE_METADATA, CID_SEARCH_ALLTRACKS,
                        DEFAULT_PORT_WEBSERVICE, DELAY_FAST_UPDATE_CHECKS,
                        DELAY_REQUEST_FAILURE_LONG_POLLING, MAX_RETRIES,
                        PREFERRED_TIMEOUT_LONG_POLLING, REQUIRED_METADATA,
                        TIMEOUT_WEBSERVICE_ACTION,
                        TRANSPORT_STATE_TRANSITIONING, TRIGGER_UPDATE_DEVICES,
                        TRIGGER_UPDATE_HOST_INFO, TRIGGER_UPDATE_SYSTEM_STATE,
                        TRIGGER_UPDATE_ZONE_CONFIG, TYPE_MEDIA_SERVER,
                        TYPE_RAUMFELD_DEVICE)


class RaumfeldHost:

    callback = None

    def __init__(self, host, port=DEFAULT_PORT_WEBSERVICE):
        self.host = host
        self.port = str(port)
        self.location = "http://" + self.host + ":" + self.port
        self.snap = {}

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
            "zoneudn_to_roomudnlst": {},
            "zone_to_rooms": {},
        }

        self.lists = {
            "raumfeld_device_udns": [],
            "rooms": [],
            "zones": [],
        }

        self.init_done = {
            "devices": False,
            "host_info": False,
            "system_state": False,
            "zone_config": False,
        }

        # up-to-date data derived from "self.wsd".
        media_server_udn = ""
        self.update_available = False

    async def async_host_is_valid(self):
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
        if "hostName" in host_info["hostInfo"]:
            return True
        else:
            return False

    #
    # Functions for backgorund data updates from Raumfeld host.
    #

    def start_update_thread(self):
        # Background thread updating "self.wsd".
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

        asyncio.run_coroutine_threadsafe(self.__async_update(), self._loop)

        # Wait for first data as background updates are asynchronous.
        while False in self.init_done.values():
            sleep(DELAY_FAST_UPDATE_CHECKS)

    async def __async_update(self):
        await asyncio.gather(
            self.async_update_gethostinfo(),
            self.async_update_getzones(),
            self.async_update_listdevices(),
            self.async_update_systemstatechannel(),
        )

    async def async_update_gethostinfo(self):
        while True:
            url = self.location + "/getHostInfo"
            await self.__long_polling(url, self.__update_host_info)

    async def async_update_getzones(self):
        while True:
            url = self.location + "/getZones"
            await self.__long_polling(url, self.__update_zone_config)

    async def async_update_listdevices(self):
        while True:
            url = self.location + "/listDevices"
            await self.__long_polling(url, self.__update_devices)

    async def async_update_systemstatechannel(self):
        while True:
            url = self.location + "/SystemStateChannel"
            await self.__long_polling(url, self.__update_system_state)

    async def __long_polling(self, url, _callback):
        update_id = None
        prefer_wait = "wait=" + str(PREFERRED_TIMEOUT_LONG_POLLING)
        headers = {"Prefer": prefer_wait}
        while True:
            if update_id:
                headers["updateID"] = update_id
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            update_id = response.headers["updateID"]
                            _callback(await response.read())
                        elif response.status != 304:
                            await asyncio.sleep(DELAY_REQUEST_FAILURE_LONG_POLLING)
                            continue
            except:
                pass
        await asyncio.sleep(DELAY_FAST_UPDATE_CHECKS)

    #
    # Callback functions for long polling.
    #

    def __update_host_info(self, content_xml):
        gethostinfo = xmltodict.parse(content_xml)
        self.wsd["host_info"] = gethostinfo["hostInfo"]

        self.init_done["host_info"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_HOST_INFO)

    def __update_zone_config(self, content_xml):
        self.lists["rooms"] = []
        self.lists["zones"] = []
        self.resolve["roomudn_to_powerstate"] = {}
        self.resolve["room_to_udn"] = {}
        self.resolve["udn_to_room"] = {}
        self.resolve["zoneudn_to_roomudnlst"] = {}

        getzones = xmltodict.parse(content_xml, force_list=("zone", "room"))
        self.wsd["zone_config"] = getzones["zoneConfig"]

        for zone_itm in self.wsd["zone_config"]["zones"]["zone"]:
            zone_rooms = []
            zone_udn = zone_itm["@udn"]
            self.resolve["zoneudn_to_roomudnlst"][zone_udn] = []

            for room_itm in zone_itm["room"]:
                room_name = room_itm["@name"]
                room_udn = room_itm["@udn"]
                zone_rooms.append(room_name)
                self.lists["rooms"].append(room_name)
                self.resolve["roomudn_to_powerstate"][room_udn] = room_itm[
                    "@powerState"
                ]
                self.resolve["room_to_udn"][room_name] = room_udn
                self.resolve["udn_to_room"][room_udn] = room_name
                self.resolve["zoneudn_to_roomudnlst"][zone_udn].append(room_udn)

            self.lists["zones"].append(sorted(zone_rooms))

        if "unassignedRooms" in self.wsd["zone_config"]:
            for room in self.wsd["zone_config"]["unassignedRooms"]["room"]:
                room_name = room["@name"]
                room_udn = room["@udn"]
                self.resolve["roomudn_to_powerstate"][room_udn] = room["@powerState"]
                self.resolve["room_to_udn"][room_name] = room_udn
                self.resolve["udn_to_room"][room_udn] = room_name
                self.lists["rooms"].append(room_name)

        self.init_done["zone_config"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_ZONE_CONFIG)

    def __update_devices(self, content_xml):
        self.lists["raumfeld_device_udns"] = []
        self.resolve["devudn_to_name"] = {}
        self.resolve["udn_to_devloc"] = {}

        listdevices = xmltodict.parse(content_xml, force_list=("device"))
        self.wsd["devices"] = listdevices["devices"]["device"]

        for device_itm in self.wsd["devices"]:
            device_loc = device_itm["@location"]
            device_type = device_itm["@type"]
            device_udn = device_itm["@udn"]
            device_name = device_itm["#text"]
            self.resolve["devudn_to_name"][device_udn] = device_name
            self.resolve["udn_to_devloc"][device_udn] = device_loc

            if device_type == TYPE_MEDIA_SERVER:
                self.media_server_udn = device_udn

            if device_type == TYPE_RAUMFELD_DEVICE:
                self.lists["raumfeld_device_udns"].append(device_udn)

        self.init_done["devices"] = True

        if self.callback is not None:
            self.callback(TRIGGER_UPDATE_DEVICES)

    def __update_system_state(self, content_xml):
        systemstatechannel = xmltodict.parse(content_xml)
        self.wsd["system_state"] = systemstatechannel["systemState"]

        update_available = self.wsd["system_state"]["updateAvailable"]["@value"]

        self.update_available = aux.str_to_bool(update_available)

        self.init_done["system_state"] = True

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
        room_lst = self.lists["rooms"]
        return room_lst

    def get_raumfeld_device_udns(self):
        devudn_lst = self.lists["raumfeld_device_udns"]
        return devudn_lst

    def device_udn_to_name(self, device_udn):
        device_name = self.resolve["devudn_to_name"][device_udn]
        return device_name

    def device_udn_to_location(self, device_udn):
        device_location = self.resolve["udn_to_devloc"][device_udn]
        return device_location

    def get_host_room(self):
        return self.wsd["host_info"]["roomName"]

    def get_host_name(self):
        return self.wsd["host_info"]["hostName"]

    def roomlst_to_udnlst(self, room_lst):
        """Convert list of room names to list of unique device names."""
        udn_lst = []
        for room in room_lst:
            room_udn = self.resolve["room_to_udn"][room]
            udn_lst.append(room_udn)
        return udn_lst

    def roomlst_to_zoneudn(self, room_lst):
        udn_lst = self.roomlst_to_udnlst(room_lst)
        zone_udn = self.roomudnlst_to_zoneudn(udn_lst)
        return zone_udn

    def roomudnlst_to_zoneudn(self, udn_lst):
        zone_udnlst = self.resolve["zoneudn_to_roomudnlst"].keys()
        for zone_udn in zone_udnlst:
            if zone_udn in self.resolve["zoneudn_to_roomudnlst"]:
                zoneroom_udnlst = self.resolve["zoneudn_to_roomudnlst"][zone_udn]
                if aux.lists_have_same_values(zoneroom_udnlst, udn_lst):
                    return zone_udn

    def __wait_zone_creation(self, old_zone_udn, new_zone_room_lst):
        """Wait for zone creation published and recevied."""
        max_attempts = int(TIMEOUT_WEBSERVICE_ACTION / DELAY_FAST_UPDATE_CHECKS)
        for i in range(0, max_attempts):
            new_zone_udn = self.roomudnlst_to_zoneudn(new_zone_room_lst)
            if new_zone_udn == None:
                sleep(DELAY_FAST_UPDATE_CHECKS)
            elif new_zone_udn == old_zone_udn:
                sleep(DELAY_FAST_UPDATE_CHECKS)
            elif new_zone_udn not in self.resolve["udn_to_devloc"]:
                sleep(DELAY_FAST_UPDATE_CHECKS)
            else:
                break

    def zone_is_valid(self, room_lst):
        zone = sorted(room_lst)
        if zone in self.lists["zones"]:
            return True
        else:
            return False

    def get_room_power_state(self, room):
        room_udn = self.resolve["room_to_udn"][room]
        power_state = self.resolve["roomudn_to_powerstate"][room_udn]
        return power_state

    #
    # Raumfeld manipulation methods
    #

    def create_zone(self, room_lst):
        """Create a new zone based on list of rooms

        Parameters:
        room_lst -- List of rooms defining a zone.
        """
        udn_lst = self.roomlst_to_udnlst(room_lst)
        old_zone_udn = self.roomudnlst_to_zoneudn(udn_lst)
        ws.connect_rooms_to_zone(self.location, room_udns=udn_lst)
        # Zone creation may take some time before taking effect.
        self.__wait_zone_creation(old_zone_udn, room_lst)

    def set_zone_room_volume(self, zone_room_lst, volume, room_lst=None):
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
                upnp.set_room_volume(zone_loc, room_udn, volume, instance_id=0)

    def set_zone_mute(self, zone_room_lst, mute=True):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.set_mute(zone_loc, mute)

    def get_zone_mute(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        mute = upnp.get_mute(zone_loc)
        return mute

    def set_zone_volume(self, zone_room_lst, volume):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.set_volume(zone_loc, volume)

    def change_zone_volume(self, zone_room_lst, amount):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.change_volume(zone_loc, amount)

    def zone_stop(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.stop(zone_loc)

    def zone_play(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.play(zone_loc)

    def zone_pause(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.pause(zone_loc)

    def zone_seek(self, zone_room_lst, target):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.seek(zone_loc, "ABS_TIME", target)

    def zone_next_track(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.next(zone_loc)

    def zone_previous_track(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.previous(zone_loc)

    def browse_media_server(self, object_id, browse_flag):
        media_server_loc = self.resolve["udn_to_devloc"][self.media_server_udn]
        return upnp.browse(media_server_loc, object_id, browse_flag)

    def search_media_server(
        self,
        container_id=0,
        search_criteria="",
        filter="*",
        starting_index=0,
        requested_count=0,
        sort_criteria="",
    ):
        """Search the media server

        Parameters:
        search_criteria='raumfeld:any contains "No son of mine"
        """
        media_server_loc = self.resolve["udn_to_devloc"][self.media_server_udn]
        response = upnp.search(
            media_server_loc,
            container_id,
            search_criteria,
            filter,
            starting_index,
            requested_count,
            sort_criteria,
        )
        return response

    def search_for_play(self, container_id, search_criteria):
        """Search for media and return uri and meta data."""
        requested_count = 1
        sort_criteria = "+upnp:artist,-dc:date,+dc:title"
        metadata_xml = self.search_media_server(
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
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        if current_uri_metadata is None:
            current_uri_metadata = xmltodict.unparse(REQUIRED_METADATA)
        upnp.set_av_transport_uri(
            zone_loc, current_uri, current_uri_metadata, instance_id=0
        )

    def search_and_zone_play(
        self, zone_room_lst, search_criteria, container_id=CID_SEARCH_ALLTRACKS
    ):
        uri, uri_metadata = self.search_for_play(container_id, search_criteria)
        self.set_av_transport_uri(zone_room_lst, uri, uri_metadata)

    def get_media_info(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return upnp.get_media_info(zone_loc)

    def get_play_mode(self, zone_room_lst):
        transport_info = self.get_transport_settings(zone_room_lst)
        return transport_info["PlayMode"]

    def get_transport_info(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return upnp.get_transport_info(zone_loc)

    def get_zone_volume(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return upnp.get_volume(zone_loc)

    def get_position_info(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        if zone_udn is not None:
            zone_loc = self.resolve["udn_to_devloc"][zone_udn]
            response = upnp.get_position_info(zone_loc)
            return response
        else:
            return False

    def get_zone_position(self, zone_room_lst):
        position_info = self.get_position_info(zone_room_lst)
        return position_info["AbsTime"]

    def get_transport_settings(self, zone_room_lst):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        return upnp.get_transport_settings(zone_loc)

    def set_play_mode(self, zone_room_lst, play_mode):
        zone_udn = self.roomlst_to_zoneudn(zone_room_lst)
        zone_loc = self.resolve["udn_to_devloc"][zone_udn]
        upnp.set_play_mode(zone_loc, play_mode)

    def save_zone(self, zone_room_lst, repl_snap=False):
        media_info = self.get_media_info(zone_room_lst)
        position_info = self.get_position_info(zone_room_lst)
        volume = self.get_zone_volume(zone_room_lst)
        mute = self.get_zone_mute(zone_room_lst)
        key = repr(zone_room_lst)
        if key not in self.snap or repl_snap:
            self.snap[key] = {}
            self.snap[key]["uri"] = media_info["CurrentURI"]
            self.snap[key]["metadata"] = media_info["CurrentURIMetaData"]
            self.snap[key]["abs_time"] = position_info["AbsTime"]
            self.snap[key]["volume"] = volume
            self.snap[key]["mute"] = mute

    def restore_zone(self, zone_room_lst, del_snap=True):
        key = repr(zone_room_lst)
        retries = 0
        if key in self.snap:
            uri = self.snap[key]["uri"]
            metadata = self.snap[key]["metadata"]
            abs_time = self.snap[key]["abs_time"]
            volume = self.snap[key]["volume"]
            mute = self.snap[key]["mute"]
            self.set_zone_volume(zone_room_lst, 0)
            self.set_zone_mute(zone_room_lst, mute)
            self.set_av_transport_uri(zone_room_lst, uri, metadata)
            while retries < MAX_RETRIES:
                transport_info = self.get_transport_info(zone_room_lst)
                transport_state = transport_info["CurrentTransportState"]
                if transport_state != TRANSPORT_STATE_TRANSITIONING:
                    break
                sleep(DELAY_FAST_UPDATE_CHECKS)
                retries += 1
            self.zone_seek(zone_room_lst, abs_time)
            self.set_zone_volume(zone_room_lst, volume)
            if del_snap:
                self.snap.pop(key, None)

    def enter_automatic_standby(self, room):
        room_udn = self.resolve["room_to_udn"][room]
        ws.enter_automatic_standby(self.location, room_udn)

    def enter_manual_standby(self, room):
        room_udn = self.resolve["room_to_udn"][room]
        ws.enter_manual_standby(self.location, room_udn)

    def leave_standby(self, room):
        room_udn = self.resolve["room_to_udn"][room]
        ws.leave_standby(self.location, room_udn)

    #
    # Home Assistent specific
    #

    def get_media_image_url(self, zone_room_lst):
        image_url = None
        media_info = self.get_media_info(zone_room_lst)
        metadata_xml = media_info["CurrentURIMetaData"]
        metadata = xmltodict.parse(metadata_xml)
        image_url = metadata["DIDL-Lite"]["container"]["upnp:albumArtURI"]
        return media_info
