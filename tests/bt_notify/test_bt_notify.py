#!/usr/bin/env python3
import pytest
import sys
import time
import enum
import logging
from targettest.cbor import CBORPayload

LOGGER = logging.getLogger(__name__)

class RPCEvents(enum.IntEnum):
    READY = 0x01
    BT_CONNECTED = enum.auto()
    BT_DISCONNECTED = enum.auto()
    BT_SCAN_REPORT = enum.auto()
    DEMO_NESTED_LIST = enum.auto()

    # Commands (still sent in EVT format)
    BT_ADVERTISE = enum.auto()
    BT_SCAN = enum.auto()
    BT_CONNECT = enum.auto()

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    LOGGER.info("Configure adv")
    rpcdevice.evt(RPCEvents.BT_ADVERTISE)

    LOGGER.info("Start conn")
    cfg = [
        [1, bytes([1, 2, 3, 4, 5, 6])],
        [7, 1000, 200, 2000]
    ]
    rpcdevice.evt_cbor(RPCEvents.BT_CONNECT, cfg)

def configure_scanner(rpcdevice):
    # configure & start scanner
    LOGGER.info("Configure scan")
    rpcdevice.evt(RPCEvents.BT_SCAN)

@pytest.fixture
def advertiser(testdevices):
    configure_advertiser(testdevices['dut'].rpc)
    return testdevices['dut']

@pytest.fixture
def scanner(testdevices):
    configure_scanner(testdevices['tester'].rpc)
    return testdevices['tester']


class TestBluetoothNotification():

    def test_boot(self, testdevices):
        LOGGER.info("Boot test")
        assert len(testdevices) == 2

    def test_scan(self, advertiser, scanner):
        LOGGER.info("Scan test")

        # Get demo event
        event = advertiser.rpc.get_evt(timeout=10)
        assert event is not None
        payload = CBORPayload.read(event.payload).objects[0]
        LOGGER.info(f'evt: {payload}')

        event = scanner.rpc.get_evt(timeout=10)
        assert event is not None

        payload = CBORPayload.read(event.payload).objects[0]
        LOGGER.info(f'evt: {payload}')
