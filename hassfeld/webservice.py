"""Interfacing with Raumfeld web service"""

import xmltodict


async def async_connect_room_to_zone(session, location, zone_udn=None, room_udn=None):
    """Puts the room with the given room_udn in the zone with the zone_udn.

    Optional parameters:
    zone_udn -- The udn of the zone to connect the room to. If zone udn is
    empty or there is no zone with this udn yet, then a new zone is
    created.
    room_udn -- The udn of the room that has to be put into that zone. If
    empty, all available rooms (rooms that have active renderers) are put
    into the zone.
    """
    params = {}

    if zone_udn:
        params["zoneUDN"] = zone_udn

    if room_udn:
        params["roomUDN"] = room_udn

    url = location + "/connectRoomToZone"

    await session.get(url, params=params)


async def async_connect_rooms_to_zone(session, location, zone_udn=None, room_udns=None):
    """Puts the rooms with the given roomUDNs in the zone with the zoneUDN.

    Optional parameters:
    zone_udn -- The udn of the zone to connect the rooms to. If zone udn is
    empty or there is no zone with this udn yet, then a new zone is
    created.
    room_udns -- A list of UDNs of the rooms that have to be put into that
    zone. If empty, all available rooms (rooms that have active renderers)
    are put into the zone and activated.
    """
    params = {}

    if zone_udn:
        params["zoneUDN"] = zone_udn

    if room_udns:
        params["roomUDNs"] = ",".join(room_udns)

    url = location + "/connectRoomsToZone"

    await session.get(url, params=params)


async def async_drop_room_job(session, location, room_udn):
    """Drops the room with the given roomUDN from the zone it is in.

    Parameter:
    room_udn -- The udn of the room that has to be dropped.
    """
    params = {"roomUDN": room_udn}
    url = location + "/dropRoomJob"
    await session.get(url, params=params)


async def async_enter_automatic_standby(session, location, room_udn):
    """Calls RPC to put a room into automatic standby.

    Parameter:
    room_udn -- udn of the desired room.
    """
    params = {"roomUDN": room_udn}
    url = location + "/enterAutomaticStandby"
    await session.get(url, params=params)


async def async_enter_manual_standby(session, location, room_udn):
    """Calls RPC to put a room into manual standby.

    Parameter:
    room_udn -- udn of the desired room.
    """
    params = {"roomUDN": room_udn}
    url = location + "/enterManualStandby"
    await session.get(url, params=params)


async def async_leave_standby(session, location, room_udn):
    """Calls RPC to let a room leave manual or automatic standby.

    Parameter:
    room_udn -- udn of the desired room.
    """
    params = {"roomUDN": room_udn}
    url = location + "/leaveStandby"
    await session.get(url, params=params)


async def async_ping(session, location):
    """Just a heart beat tester

    Returns a dictionary containing hardware model and number.
    """
    url = location + "/Ping"
    response = await session.get(url)
    pong = xmltodict.parse(await response.text())

    if "response" in pong:
        return pong["response"]
