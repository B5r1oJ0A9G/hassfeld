"""Methods implementing UPnP requests."""
import sys
from typing import Mapping, Optional, Tuple, Union

import aiohttp
import async_timeout
from async_upnp_client import UpnpFactory
from async_upnp_client.aiohttp import AiohttpRequester

from .common import log_error
from .constants import (BROWSE_CHILDREN, RESPONSE_KEY_CURRENT_MUTE,
                        RESPONSE_KEY_CURRENT_VOLUME, RESPONSE_KEY_RESULT,
                        SERVICE_AV_TRANSPORT, SERVICE_CONTENT_DIRECTORY,
                        SERVICE_RENDERING_CONTROL)


def exception_handler(function):
    """Handling exceptions as decorator."""

    def new_function(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
            return result
        except:
            exc_info = "%s%s" % (sys.exc_info()[0], sys.exc_info()[1])
            name = function.__name__
            log_error("Unexpected error with %s: %s" % (name, exc_info))

    return new_function


# FIXME: make this work-around obsolete
class CustomAiohttpRequester(AiohttpRequester):
    """Just to overlay async_do_http_request with http_header support"""

    def __init__(self, timeout: int = 5, http_headers=None) -> None:
        """Initialize."""
        self.http_headers = http_headers
        super().__init__(timeout)

    async def async_do_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str] = None,
        body_type: str = "text",
    ) -> Tuple[int, Mapping, Union[str, bytes, None]]:
        """Do a HTTP request."""
        # pylint: disable=too-many-arguments
        if self.http_headers:
            if headers:
                headers = {**headers, **self.http_headers}
            else:
                headers = self.http_headers

        async with async_timeout.timeout(self._timeout):
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=headers, data=body
                ) as response:
                    status = response.status
                    resp_headers: Mapping = response.headers or {}

                    resp_body: Union[str, bytes, None] = None
                    if body_type == "text":
                        resp_body = await response.text()
                    elif body_type == "raw":
                        resp_body = await response.read()
                    elif body_type == "ignore":
                        resp_body = None

        return status, resp_headers, resp_body


async def get_dlna_action(location, service, action, http_headers=None):
    """Return DLNA action pased on passed parameters"""
    requester = CustomAiohttpRequester(http_headers=http_headers)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device(location)
    service = device.service(service)
    action = service.action(action)
    return action


@exception_handler
async def async_get_mute(location, channel="Master", instance_id=0):
    """Returns a bolean of the mute status of a rendering service.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    instance_id --
    channel --
    """
    action_name = "GetMute"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    response = await upnp_action.async_call(InstanceID=instance_id, Channel=channel)
    if RESPONSE_KEY_CURRENT_MUTE in response:
        return response[RESPONSE_KEY_CURRENT_MUTE]
    return None


@exception_handler
async def async_get_media_info(location, instance_id=0):
    """Return media information."""
    action_name = "GetMediaInfo"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_get_transport_info(location, instance_id=0):
    """Return transport information."""
    action_name = "GetTransportInfo"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_get_volume(location, channel="Master", instance_id=0):
    """Returns the highest volume of rooms in a zone rendering service.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device
    in a room.
    channel --
    instance_id --
    """
    action_name = "GetVolume"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    response = await upnp_action.async_call(InstanceID=instance_id, Channel=channel)
    if RESPONSE_KEY_CURRENT_VOLUME in response:
        return response[RESPONSE_KEY_CURRENT_VOLUME]
    return None


@exception_handler
async def async_get_position_info(location, instance_id=0):
    """Return position information."""
    action_name = "GetPositionInfo"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_get_transport_settings(location, instance_id=0):
    """Return transport settings."""
    action_name = "GetTransportSettings"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_browse(
    location,
    object_id=0,
    browse_flag=BROWSE_CHILDREN,
    filter_criteria="*",
    starting_index=0,
    requested_count=0,
    sort_criteria="",
    http_headers=None,
):
    """Browse media."""
    action_name = "Browse"
    upnp_action = await get_dlna_action(
        location, SERVICE_CONTENT_DIRECTORY, action_name, http_headers=http_headers
    )
    response = await upnp_action.async_call(
        ObjectID=object_id,
        BrowseFlag=browse_flag,
        Filter=filter_criteria,
        StartingIndex=starting_index,
        RequestedCount=requested_count,
        SortCriteria=sort_criteria,
    )
    if RESPONSE_KEY_RESULT in response:
        return response[RESPONSE_KEY_RESULT]
    return None


@exception_handler
async def async_search(
    location,
    container_id=0,
    search_criteria="",
    filter_criteria="*",
    starting_index=0,
    requested_count=0,
    sort_criteria="",
):
    """Search media."""
    action_name = "Search"
    upnp_action = await get_dlna_action(
        location, SERVICE_CONTENT_DIRECTORY, action_name
    )
    response = await upnp_action.async_call(
        ContainerID=container_id,
        SearchCriteria=search_criteria,
        Filter=filter_criteria,
        StartingIndex=starting_index,
        RequestedCount=requested_count,
        SortCriteria=sort_criteria,
    )
    if RESPONSE_KEY_RESULT in response:
        return response[RESPONSE_KEY_RESULT]
    return None


@exception_handler
async def async_set_room_volume(location, room, desired_volume, instance_id=0):
    """Sets the volume of a rendering service in a room.

    Applies to Virtual Media Player.

    Parameters:
    location -- URL to the device description XML of the rendering device.
    room -- The unique device number of the room (UUID). The device must be
    member of the room.
    desired_volume -- Desired volume for the room.
    instance_id --
    value of False deactivates the mute status.
    """
    action_name = "SetRoomVolume"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Room=room, DesiredVolume=desired_volume
    )


async def async_set_mute(
    location,
    desired_mute=True,
    channel="Master",
    instance_id=0,
):
    """Sets the mute status of a rendering service.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    instance_id
    channel --
    desired_mute --- Bolean value of True activaes the mute status and a
    value of False deactivates the mute status.
    """
    action_name = "SetMute"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Channel=channel, DesiredMute=desired_mute
    )


@exception_handler
async def async_set_volume(location, desired_volume, channel="Master", instance_id=0):
    """Returns the highest volume of rooms in a zone rendering service.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    desired_volume -- Desired volume for the zone. Relations between rooms
    are kept.
    channel --
    instance_id --
    """
    action_name = "SetVolume"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Channel=channel, DesiredVolume=desired_volume
    )


async def async_change_volume(location, amount, instance_id=0):
    """Changes the volume of all rooms in a zone up or down.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    amount -- Amount of volume change.
    instance_id --
    """
    action_name = "ChangeVolume"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name
    )
    await upnp_action.async_call(InstanceID=instance_id, Amount=amount)


@exception_handler
async def async_stop(location, instance_id=0):
    """Stop playing media."""
    action_name = "Stop"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_play(location, speed="1", instance_id=0):
    """Play media."""
    action_name = "Play"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id, Speed=speed)


@exception_handler
async def async_pause(location, instance_id=0):
    """Paus playing media."""
    action_name = "Pause"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id)


# TODO: default to unit="ABS_TIME"
@exception_handler
async def async_seek(location, unit, target, instance_id=0):
    """Seek to position."""
    action_name = "Seek"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id, Unit=unit, Target=target)


@exception_handler
async def async_next_track(location, instance_id=0):
    """Play next track."""
    action_name = "Next"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_previous_track(location, instance_id=0):
    """Play previous track."""
    action_name = "Previous"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_set_av_transport_uri(
    location, current_uri, current_uri_meta_data="", instance_id=0
):
    """Set media to play."""
    action_name = "SetAVTransportURI"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(
        InstanceID=instance_id,
        CurrentURI=current_uri,
        CurrentURIMetaData=current_uri_meta_data,
    )


@exception_handler
async def async_set_play_mode(location, play_mode, instance_id=0):
    """Set play mode."""
    action_name = "SetPlayMode"
    upnp_action = await get_dlna_action(location, SERVICE_AV_TRANSPORT, action_name)
    await upnp_action.async_call(InstanceID=instance_id, NewPlayMode=play_mode)
