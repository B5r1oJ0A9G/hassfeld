"""Methods implementing UPnP requests."""
import upnpclient

from .constants import (
    BROWSE_CHILDREN
)

def get_mute(location, channel="Master", instance_id=0):
    """Returns a bolean of the mute status of a rendering service.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    instance_id --
    channel --
    """
    device = upnpclient.Device(location)
    response = device.RenderingControl.GetMute(InstanceID=instance_id, Channel=channel)
    return response['CurrentMute']

def set_mute(location, desired_mute=True, channel="Master", instance_id=0,):
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
    if desired_mute == True:
        desired_mute = '1'
    else:
        desired_mute = '0'

    device = upnpclient.Device(location)
    device.RenderingControl.SetMute(InstanceID=instance_id, Channel=channel, DesiredMute=desired_mute)

def get_room_volume(location, room, instance_id=0):
    """Returns the integer for the volume of a rendering service in a room.

    Applies to Virtual Media Player.

    Parameters:
    location -- URL to the device description XML of the rendering device
    in a room.
    room -- The unique device number of the room (UUID). The device must be
    member of the room.
    instance_id --
    """
    device = upnpclient.Device(location)
    response = device.RenderingControl.GetRoomVolume(InstanceID=instance_id, Room=room)
    return response['CurrentVolume']

def set_room_volume(location, room, desired_volume, instance_id=0):
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
    device = upnpclient.Device(location)
    device.RenderingControl.SetRoomVolume(InstanceID=instance_id, Room=room, DesiredVolume=desired_volume)

def get_room_mute(location, room, instance_id=0):
    """Returns the mute status of a rendering service in a room.

    Applies to Virtual Media Player.

    Parameters:
    location -- URL to the device description XML of the rendering device
    in a room.
    room -- The unique device number of the room (UUID). The device must be
    member of the room.
    instance_id --
    """
    device = upnpclient.Device(location)
    response = device.RenderingControl.GetRoomMute(InstanceID=instance_id, Room=room)
    return response['CurrentMute']

def set_room_mute(location, room, desired_mute=True, instance_id=0):
    """Sets the mute status of a rendering service in a room.

    Applies to Virtual Media Player.

    Parameters:
    location -- URL to the device description XML of the rendering device.
    room -- The unique device number of the room (UUID). The device must be
    member of the room.
    desired_mute --- Bolean value of True activaes the mute status and a
    value of False deactivates the mute status.
    instance_id --
    """
    if desired_mute == True:
        desired_mute = '1'
    else:
        desired_mute = '0'

    device = upnpclient.Device(location)
    device.RenderingControl.SetRoomMute(InstanceID=instance_id, Room=room, DesiredMute=desired_mute)

def change_volume(location, amount, instance_id=0):
    """Changes the volume of all rooms in a zone up or down.

    Applies to:
    Digital Media Player
    Virtual Media Player

    Parameters:
    location -- URL to the device description XML of the rendering device.
    amount -- Amount of volume change.
    instance_id --
    """
    device = upnpclient.Device(location)
    device.RenderingControl.ChangeVolume(InstanceID=instance_id, Amount=amount)

def get_volume(location, channel="Master", instance_id=0):
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
    device = upnpclient.Device(location)
    response = device.RenderingControl.GetVolume(InstanceID=instance_id, Channel=channel)
    return response['CurrentVolume']

def set_volume(location, desired_volume, channel="Master", instance_id=0):
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
    device = upnpclient.Device(location)
    device.RenderingControl.SetVolume(InstanceID=instance_id, Channel=channel, DesiredVolume=desired_volume)

def play_system_sound(location, sound="Success", instance_id=0):
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
    if sound != "Success":
        sound = "Failure"

    device = upnpclient.Device(location)
    device.RenderingControl.PlaySystemSound(InstanceID=instance_id, Sound=sound)

def set_av_transport_uri(location, current_uri, current_uri_meta_data="", instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.SetAVTransportURI(InstanceID=instance_id, CurrentURI=current_uri, CurrentURIMetaData=current_uri_meta_data)

def stop(location, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Stop(InstanceID=instance_id)

def set_play_mode(location, play_mode, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.SetPlayMode(InstanceID=instance_id, NewPlayMode=play_mode)

def get_transport_settings(location, instance_id=0):
    device = upnpclient.Device(location)
    transport_settings = device.AVTransport.GetTransportSettings(InstanceID=instance_id)
    return transport_settings

def play(location, speed="1", instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Play(InstanceID=instance_id, Speed=speed)

def pause(location, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Pause(InstanceID=instance_id)

def seek(location, unit, target, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Seek(InstanceID=instance_id, Unit=unit, Target=target)

def browse(location, object_id=0, browse_flag=BROWSE_CHILDREN, filter='*', starting_index=0, requested_count=0, sort_criteria=''):
    device = upnpclient.Device(location)
    response = device.ContentDirectory.Browse(ObjectID=object_id, BrowseFlag=browse_flag, Filter=filter, StartingIndex=starting_index, RequestedCount=requested_count, SortCriteria=sort_criteria)
    return response['Result']

def search(location, container_id=0, search_criteria='', filter='*', starting_index=0, requested_count=0, sort_criteria=''):
    device = upnpclient.Device(location)
    response = device.ContentDirectory.Search(ContainerID=container_id, SearchCriteria=search_criteria, Filter=filter, StartingIndex=starting_index, RequestedCount=requested_count, SortCriteria=sort_criteria)
    return response['Result']

def get_media_info(location, instance_id=0):
    device = upnpclient.Device(location)
    response = device.AVTransport.GetMediaInfo(InstanceID=instance_id)
    return response

def get_transport_info(location, instance_id=0):
    device = upnpclient.Device(location)
    response = device.AVTransport.GetTransportInfo(InstanceID=instance_id)
    return response

def get_position_info(location, instance_id=0):
    device = upnpclient.Device(location)
    response = device.AVTransport.GetPositionInfo(InstanceID=instance_id)
    return response

def get_search_capabilities(location):
    device = upnpclient.Device(location)
    response = device.ContentDirectory.GetSearchCapabilities()
    return response

def next(location, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Next(InstanceID=instance_id)

def previous(location, instance_id=0):
    device = upnpclient.Device(location)
    device.AVTransport.Previous(InstanceID=instance_id)

