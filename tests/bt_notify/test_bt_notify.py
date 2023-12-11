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

LOGGER = logging.getLogger(__name__)

class RPCEvents(enum.IntEnum):
    READY = 0x01
    BT_CONNECTED = enum.auto()
    BT_DISCONNECTED = enum.auto()
    BT_SCAN_REPORT = enum.auto()

class RPCCmds(enum.IntEnum):
    BT_ADVERTISE = 0x01
    BT_SCAN = enum.auto()
    BT_SCAN_STOP = enum.auto()
    BT_CONNECT = enum.auto()
    BT_DISCONNECT = enum.auto()
    K_OOPS = enum.auto()

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    LOGGER.info("Configure adv")
    # rpcdevice.evt(RPCEvents.BT_ADVERTISE)
    rpcdevice.cmd(RPCCmds.BT_ADVERTISE)

def configure_scanner(rpcdevice):
    # configure & start scanner
    LOGGER.info("Configure scan")
    # rpcdevice.evt_cbor(RPCEvents.BT_SCAN, -50)
    rpcdevice.cmd(RPCCmds.BT_SCAN, {'rssi_threshold': ('<b', -120)})

def connect(rpcdevice, addr: bytes):
    schema = {
        'peer': ('<7s', addr),
        'options': ('<I', 0x00), # BT_CONN_LE_OPT_NONE
        'interval': ('<H', 0x0060), # BT_GAP_SCAN_FAST_INTERVAL
        'window': ('<H', 0x0060), # BT_GAP_SCAN_FAST_INTERVAL
        'interval_coded': ('<H', 0x00),
        'window_coded': ('<H', 0x00),
        'timeout': ('<H', 0x00)
    }
    rpcdevice.cmd(RPCCmds.BT_CONNECT, schema)

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
            testdevices['dut'].rpc.cmd(RPCCmds.K_OOPS)

    def test_scan(self, advertiser, scanner):
        LOGGER.info("Scan test")

        # Get scanned device event
        schema = {'addr': ('<7s', None), 'rssi': ('<b', None), 'type': ('<B', None), 'ad_length': ('<H', None)}
        event, decoded = scanner.rpc.get_evt(schema=schema, timeout=10)
        assert event is not None

        LOGGER.info(f'evt: {event}')
        LOGGER.info(f'evt: {decoded}')

    def test_conn(self, testdevices):
        peripheral = testdevices['dut'].rpc
        central = testdevices['tester'].rpc

        # Configure an advertiser and a scanner
        peripheral.cmd(RPCCmds.BT_ADVERTISE)
        central.cmd(RPCCmds.BT_SCAN, {'rssi_threshold': ('<b', -60)})

        # Pull out the demo event we don't care about
        # event = peripheral.get_evt(timeout=10)
        # assert event.opcode == RPCEvents.DEMO_NESTED_LIST

        # Wait for the first scan report
        # event, payload = central.get_evt_cbor(timeout=10)
        schema = {'addr': ('<7s', None), 'rssi': ('<b', None), 'type': ('<B', None), 'ad_length': ('<H', None)}
        event, decoded = central.get_evt(schema=schema, timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_SCAN_REPORT

        # Decode payload and extract the address
        LOGGER.info(f'scan report: {decoded}')
        addr = decoded['addr'][1]

        # Stop scanner and create a connection
        LOGGER.info("Start conn")
        central.cmd(RPCCmds.BT_SCAN_STOP)
        connect(central, addr)

        # Wait for the connected event on both sides
        schema = {'addr': ('<7s', None), 'conn_err': ('<B', None)}
        event, decoded = central.get_evt(schema=schema, timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_CONNECTED
        LOGGER.info(f'schema: {schema}')
        LOGGER.info(f'connected: {decoded}')

        schema = {'addr': ('<7s', None), 'conn_err': ('<B', None)}
        event, decoded = peripheral.get_evt(schema=schema, timeout=10)
        assert event is not None
        assert event.opcode == RPCEvents.BT_CONNECTED
        LOGGER.info(f'connected: {decoded}')
