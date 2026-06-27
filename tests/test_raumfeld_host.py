"""Tests for hassfeld.RaumfeldHost — pure-logic methods testable without network."""

from unittest.mock import MagicMock

import pytest
from hassfeld import RaumfeldHost
from hassfeld.constants import (
    POWER_ACTIVE,
    SPOTIFY_ACTIVE,
)


class TestRaumfeldHostProperties:
    """Tests for property-like methods that read from internal data structures."""

    def setup_method(self):
        mock_session = MagicMock()
        self.host = RaumfeldHost(host="127.0.0.1", session=mock_session)
        # Populate resolve maps and lists
        self.host.resolve = {
            "devudn_to_name": {
                "uuid:dev1": "Living Room",
                "uuid:dev2": "Kitchen",
            },
            "udn_to_devloc": {
                "uuid:dev1": "http://10.0.0.1:47365",
                "uuid:dev2": "http://10.0.0.2:47365",
            },
            "room_to_udn": {
                "Living Room": "uuid:room1",
                "Kitchen": "uuid:room2",
            },
            "roomudn_to_powerstate": {
                "uuid:room1": POWER_ACTIVE,
            },
            "roomudn_to_rendudn": {
                "uuid:room1": "uuid:rend1",
                "uuid:room2": "uuid:rend2",
            },
        }
        self.host.lists = {
            "rooms": ["Living Room", "Kitchen"],
            "zones": [["Kitchen"], ["Living Room"]],
            "spotify_renderer": ["uuid:rend2"],
        }
        self.host.wsd = {
            "devices": {
                "uuid:dev1": {
                    "rendererUdn": "uuid:rend1",
                    "name": "Living Room",
                    "powerState": POWER_ACTIVE,
                    "spotifyState": "inactive",
                },
                "uuid:dev2": {
                    "rendererUdn": "uuid:rend2",
                    "name": "Kitchen",
                    "powerState": "AUTOMATIC_STANDBY",
                    "spotifyState": SPOTIFY_ACTIVE,
                },
            },
            "host_info": {"hostName": "test-host", "roomName": "Server Room"},
        }

    def test_device_udn_to_name(self):
        assert self.host.device_udn_to_name("uuid:dev1") == "Living Room"

    def test_device_udn_to_name_unknown_raises(self):
        with pytest.raises(KeyError):
            self.host.device_udn_to_name("uuid:unknown")

    def test_device_udn_to_location(self):
        assert self.host.device_udn_to_location("uuid:dev1") == "http://10.0.0.1:47365"

    def test_device_udn_to_location_unknown_raises(self):
        with pytest.raises(KeyError):
            self.host.device_udn_to_location("uuid:unknown")

    def test_get_zones(self):
        zones = self.host.get_zones()
        assert ["Kitchen"] in zones
        assert ["Living Room"] in zones

    def test_get_rooms(self):
        rooms = self.host.get_rooms()
        assert "Living Room" in rooms
        assert "Kitchen" in rooms

    def test_get_host_room(self):
        assert self.host.get_host_room() == "Server Room"

    def test_get_host_name(self):
        assert self.host.get_host_name() == "test-host"

    def test_room_is_spotify_single_room(self):
        assert self.host.room_is_spotify_single_room("Kitchen") is True
        assert self.host.room_is_spotify_single_room("Living Room") is False

    def test_get_room_power_state(self):
        assert self.host.get_room_power_state("Living Room") == POWER_ACTIVE

    def test_get_room_power_state_unknown_raises(self):
        with pytest.raises(KeyError):
            self.host.get_room_power_state("Kitchen")

    def test_zone_is_valid_true(self):
        assert self.host.zone_is_valid(["Living Room"]) is True

    def test_zone_is_valid_false(self):
        assert self.host.zone_is_valid(["Nonexistent"]) is False

    def test_room_is_valid(self):
        assert self.host.room_is_valid("Living Room") is True
        assert self.host.room_is_valid("Nonexistent") is False

    def test_rooms_are_valid(self):
        assert self.host.rooms_are_valid(["Living Room"]) is True
        assert self.host.rooms_are_valid(["Living Room", "Kitchen"]) is True
        assert self.host.rooms_are_valid(["Living Room", "Nonexistent"]) is False


class TestRaumfeldHostUpdateMethods:
    """Tests for update methods that parse XML content."""

    def setup_method(self):
        mock_session = MagicMock()
        self.host = RaumfeldHost(host="127.0.0.1", session=mock_session)

    def test_update_host_info(self):
        xml = (
            '<?xml version="1.0"?>'
            "<hostInfo>"
            "<hostName>MyHost</hostName>"
            "<roomName>Office</roomName>"
            "</hostInfo>"
        )
        self.host._RaumfeldHost__update_host_info(xml)
        assert self.host.wsd["host_info"]["hostName"] == "MyHost"
        assert self.host.wsd["host_info"]["roomName"] == "Office"

    def test_location_is_valid(self):
        self.host.lists = {"locations": ["http://10.0.0.1:47365"]}
        assert self.host.location_is_valid("http://10.0.0.1:47365") is True
        assert self.host.location_is_valid("http://10.0.0.2:47365") is False
        assert self.host.location_is_valid(None) is False
        assert self.host.location_is_valid("") is False


class TestRaumfeldHostSnapLogic:
    """Tests for snapshot save/restore logic paths."""

    def setup_method(self):
        mock_session = MagicMock()
        self.host = RaumfeldHost(host="127.0.0.1", session=mock_session)

    def test_snap_stores_data(self):
        key = "test_key"
        self.host.snap[key] = {
            "read_only": False,
            "uri": "dlna-playsingle://test",
            "metadata": "<DIDL-Lite><item>Test</item></DIDL-Lite>",
            "abs_time": "00:01:30",
            "volume": 50,
            "mute": False,
        }

        assert self.host.snap[key]["uri"] == "dlna-playsingle://test"
        assert self.host.snap[key]["volume"] == 50
        assert self.host.snap[key]["mute"] is False
