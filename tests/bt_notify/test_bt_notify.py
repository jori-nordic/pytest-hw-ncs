#!/usr/bin/env python3
import pytest
import sys
import time
import enum
import logging
from targettest.cbor import CBORPayload

LOGGER = logging.getLogger(__name__)

class RPCCommands(enum.IntEnum):
    BT_SCAN = 0x01
    BT_ADVERTISE = enum.auto()
    BT_CONNECT = enum.auto()
    BT_DISCONNECT = enum.auto()

class RPCEvents(enum.IntEnum):
    READY = 0x01
    BT_CONNECTED = enum.auto()
    BT_DISCONNECTED = enum.auto()
    BT_SCAN_REPORT = enum.auto()

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    LOGGER.info("Configure adv")
    rsp = rpcdevice.cmd(RPCCommands.BT_ADVERTISE)
    LOGGER.info(f'rsp: {CBORPayload.read(rsp.payload).objects}')

    LOGGER.info("Start conn")
    conn = [
        [1, bytes([1, 2, 3, 4, 5, 6])],
        [7, 1000, 200, 2000]
    ]
    payload = CBORPayload(conn).encoded
    LOGGER.info(f'payload: {payload.hex(" ")}')
    rsp = rpcdevice.cmd(RPCCommands.BT_CONNECT,
                        payload)
    LOGGER.info(f'rsp: {CBORPayload.read(rsp.payload).objects}')

def configure_scanner(rpcdevice):
    # configure & start scanner
    LOGGER.info("Configure scan")
    rpcdevice.cmd(RPCCommands.BT_ADVERTISE)

def init_bluetooth(rpcdevice):
    # - call `bt_init`
    pass

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

        event = advertiser.rpc.get_evt(timeout=10)
        assert event is not None

        payload = CBORPayload.read(event.payload).objects[0]
        LOGGER.info(f'evt: {payload}')
