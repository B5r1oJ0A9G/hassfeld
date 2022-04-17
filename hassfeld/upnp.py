"""Methods implementing UPnP requests."""
import asyncio
import sys

from aiohttp import client_exceptions
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.aiohttp import AiohttpRequester, AiohttpSessionRequester

from .common import log_error, log_info
from .constants import (BROWSE_CHILDREN, RESPONSE_KEY_CURRENT_MUTE,
                        RESPONSE_KEY_CURRENT_VOLUME, RESPONSE_KEY_RESULT,
                        SERVICE_AV_TRANSPORT, SERVICE_CONTENT_DIRECTORY,
                        SERVICE_ID_SETUP_SERVICE, SERVICE_RENDERING_CONTROL,
                        SOUND_FAILURE, SOUND_SUCCESS, TIMEOUT_UPNP)


def exception_handler(function):
    """Handling exceptions as decorator."""

    async def new_function(*args, **kwargs):
        name = function.__name__
        try:
            result = await function(*args, **kwargs)
            return result
        except asyncio.exceptions.TimeoutError:
            log_info("Function '%s' timed out." % name)
        except client_exceptions.ClientConnectorError:
            log_error(sys.exc_info()[1])
            return None
        except:
            exc_info = "%s%s" % (sys.exc_info()[0], sys.exc_info()[1])
            log_error("Unexpected error with %s: %s" % (name, exc_info))

    return new_function


async def get_dlna_action(location, service, action, http_headers=None, session=None):
    """Return DLNA action pased on passed parameters"""
    if session:
        requester = AiohttpSessionRequester(
            timeout=TIMEOUT_UPNP, http_headers=http_headers, session=session
        )
    else:
        requester = AiohttpRequester(timeout=TIMEOUT_UPNP, http_headers=http_headers)

    factory = UpnpFactory(requester)
    device = await factory.async_create_device(location)
    service = device.service(service)
    action = service.action(action)
    return action


@exception_handler
async def async_get_mute(session, location, channel="Master", instance_id=0):
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id, Channel=channel)
    if RESPONSE_KEY_CURRENT_MUTE in response:
        return response[RESPONSE_KEY_CURRENT_MUTE]
    return None


@exception_handler
async def async_get_media_info(session, location, instance_id=0):
    """Return media information."""
    action_name = "GetMediaInfo"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id)
    response["CurrentURIMetaData"] = upnp_action.argument(
        "CurrentURIMetaData"
    ).raw_upnp_value
    return response


@exception_handler
async def async_get_transport_info(session, location, instance_id=0):
    """Return transport information."""
    action_name = "GetTransportInfo"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_get_volume(session, location, channel="Master", instance_id=0):
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id, Channel=channel)
    if RESPONSE_KEY_CURRENT_VOLUME in response:
        return response[RESPONSE_KEY_CURRENT_VOLUME]
    return None


@exception_handler
async def async_get_position_info(session, location, instance_id=0):
    """Return position information."""
    action_name = "GetPositionInfo"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id)
    response["TrackMetaData"] = upnp_action.argument("TrackMetaData").raw_upnp_value
    return response


@exception_handler
async def async_get_transport_settings(session, location, instance_id=0):
    """Return transport settings."""
    action_name = "GetTransportSettings"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    response = await upnp_action.async_call(InstanceID=instance_id)
    return response


@exception_handler
async def async_browse(
    session,
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
        location,
        SERVICE_CONTENT_DIRECTORY,
        action_name,
        http_headers=http_headers,
        session=session,
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
        response[RESPONSE_KEY_RESULT] = upnp_action.argument(
            RESPONSE_KEY_RESULT
        ).raw_upnp_value
        return response[RESPONSE_KEY_RESULT]
    return None


@exception_handler
async def async_search(
    session,
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
        location, SERVICE_CONTENT_DIRECTORY, action_name, session=session
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
async def async_set_room_volume(session, location, room, desired_volume, instance_id=0):
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Room=room, DesiredVolume=desired_volume
    )


async def async_set_mute(
    session,
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Channel=channel, DesiredMute=desired_mute
    )


@exception_handler
async def async_set_volume(
    session, location, desired_volume, channel="Master", instance_id=0
):
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    await upnp_action.async_call(
        InstanceID=instance_id, Channel=channel, DesiredVolume=desired_volume
    )


async def async_change_volume(session, location, amount, instance_id=0):
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
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id, Amount=amount)


@exception_handler
async def async_stop(session, location, instance_id=0):
    """Stop playing media."""
    action_name = "Stop"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_play(session, location, speed="1", instance_id=0):
    """Play media."""
    action_name = "Play"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id, Speed=speed)


@exception_handler
async def async_pause(session, location, instance_id=0):
    """Paus playing media."""
    action_name = "Pause"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id)


# TODO: default to unit="ABS_TIME"
@exception_handler
async def async_seek(session, location, unit, target, instance_id=0):
    """Seek to position."""
    action_name = "Seek"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id, Unit=unit, Target=target)


@exception_handler
async def async_next_track(session, location, instance_id=0):
    """Play next track."""
    action_name = "Next"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_previous_track(session, location, instance_id=0):
    """Play previous track."""
    action_name = "Previous"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id)


@exception_handler
async def async_set_av_transport_uri(
    session, location, current_uri, current_uri_meta_data="", instance_id=0
):
    """Set media to play."""
    action_name = "SetAVTransportURI"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(
        InstanceID=instance_id,
        CurrentURI=current_uri,
        CurrentURIMetaData=current_uri_meta_data,
    )


@exception_handler
async def async_set_play_mode(session, location, play_mode, instance_id=0):
    """Set play mode."""
    action_name = "SetPlayMode"
    upnp_action = await get_dlna_action(
        location, SERVICE_AV_TRANSPORT, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id, NewPlayMode=play_mode)


@exception_handler
async def async_get_update_info(session, location):
    """Return software update information."""
    action_name = "GetUpdateInfo"
    upnp_action = await get_dlna_action(
        location, SERVICE_ID_SETUP_SERVICE, action_name, session=session
    )
    response = await upnp_action.async_call()
    return response


@exception_handler
async def async_get_info(session, location):
    """Return softwre version."""
    action_name = "GetInfo"
    upnp_action = await get_dlna_action(
        location, SERVICE_ID_SETUP_SERVICE, action_name, session=session
    )
    response = await upnp_action.async_call()
    return response["SoftwareVersion"]


@exception_handler
async def async_get_device(session, location, service):
    """Return unique device name."""
    action_name = "GetDevice"
    upnp_action = await get_dlna_action(
        location, SERVICE_ID_SETUP_SERVICE, action_name, session=session
    )
    response = await upnp_action.async_call(Service=service)
    return response["UniqueDeviceName"]


@exception_handler
async def async_get_manufacturer(session, location):
    """Return manufacturer name."""
    requester = AiohttpSessionRequester(timeout=TIMEOUT_UPNP, session=session)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device(location)
    return device.manufacturer


@exception_handler
async def async_get_model_name(session, location):
    """Return model name."""
    requester = AiohttpSessionRequester(timeout=TIMEOUT_UPNP, session=session)
    factory = UpnpFactory(requester)
    device = await factory.async_create_device(location)
    return device.model_name


@exception_handler
async def async_play_system_sound(
    session, location, sound=SOUND_SUCCESS, instance_id=0
):
    """Plays a one out of two available system sounds.

    Devices have to be online. The sound gets mixed into potentially played
    media.

    Applies to:
    Digital Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    sound -- Valid values are "Success" and "Failure".
    instance_id --
    """
    if sound != SOUND_SUCCESS:
        sound = SOUND_FAILURE

    action_name = "PlaySystemSound"
    upnp_action = await get_dlna_action(
        location, SERVICE_RENDERING_CONTROL, action_name, session=session
    )
    await upnp_action.async_call(InstanceID=instance_id, Sound=sound)
