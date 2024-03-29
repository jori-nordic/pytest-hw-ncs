#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
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
    BT_SCAN_STOP = enum.auto()
    BT_CONNECT = enum.auto()
    BT_DISCONNECT = enum.auto()
    K_OOPS = enum.auto()

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    LOGGER.info("Configure adv")
    rpcdevice.evt(RPCEvents.BT_ADVERTISE)

def configure_scanner(rpcdevice):
    # configure & start scanner
    LOGGER.info("Configure scan")
    rpcdevice.evt_cbor(RPCEvents.BT_SCAN, -50)

def connect(rpcdevice, addr, cfg=None):
    if cfg is None:
        cfg = [0, 60, 30, 2000]

    params = [addr, cfg]
    rpcdevice.evt_cbor(RPCEvents.BT_CONNECT, params)

@pytest.fixture
def advertiser(testdevices):
    configure_advertiser(testdevices['dut'].rpc)
    return testdevices['dut']

@pytest.fixture
def scanner(testdevices):
    configure_scanner(testdevices['tester'].rpc)
    return testdevices['tester']


class TestBluetooth():

    def test_boot(self, testdevices):
        LOGGER.info("Boot test")
        assert len(testdevices) == 2

    def test_trigger_oops(self, testdevices):
        LOGGER.info("k_oops test")
        # Trigger a kernel panic
        with pytest.raises(Exception):
            # Will raise a comm failure because the device will be unresponsive
            testdevices['dut'].rpc.evt(RPCEvents.K_OOPS)

    def test_scan(self, advertiser, scanner):
        LOGGER.info("Scan test")

        # Get demo event
        event, payload = advertiser.rpc.get_evt_cbor(timeout=10)
        assert event is not None

        LOGGER.info(f'evt: {payload}')

        # Get scanned device event
        event, payload = scanner.rpc.get_evt_cbor(timeout=10)
        assert event is not None

        LOGGER.info(f'evt: {payload}')

    def test_conn(self, testdevices):
        peripheral = testdevices['dut'].rpc
        central = testdevices['tester'].rpc

        # Configure an advertiser and a scanner
        peripheral.evt(RPCEvents.BT_ADVERTISE)
        central.evt_cbor(RPCEvents.BT_SCAN, -50)

        # Pull out the demo event we don't care about
        event = peripheral.get_evt(timeout=10)
        assert event.opcode == RPCEvents.DEMO_NESTED_LIST

        # Wait for the first scan report
        event, payload = central.get_evt_cbor(timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_SCAN_REPORT

        # Decode payload and extract the address
        LOGGER.info(f'scan report: {payload}')
        addr = payload[0]

        # Stop scanner and create a connection
        LOGGER.info("Start conn")
        central.evt(RPCEvents.BT_SCAN_STOP)
        connect(central, addr)

        # Wait for the connected event on both sides
        event, payload = central.get_evt_cbor(timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_CONNECTED
        LOGGER.info(f'connected: {payload}')

        event, payload = peripheral.get_evt_cbor(timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_CONNECTED
        LOGGER.info(f'connected: {payload}')
