#!/usr/bin/env python3
import pytest
import sys
import time
import enum
from targettest.cbor import CBORPayload


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
    print("Configure adv")
    rsp = rpcdevice.cmd(RPCCommands.BT_ADVERTISE)
    print(f'rsp: {CBORPayload.read(rsp.payload).objects}')

    print("Start conn")
    conn = [
        [1, bytes([1, 2, 3, 4, 5, 6])],
        [7, 1000, 200, 2000]
    ]
    payload = CBORPayload(conn).encoded
    print(f'payload: {payload.hex(" ")}')
    rsp = rpcdevice.cmd(RPCCommands.BT_CONNECT,
                        payload)
    print(f'rsp: {CBORPayload.read(rsp.payload).objects}')

def configure_scanner(rpcdevice):
    # configure & start scanner
    print("Configure scan")
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

    # def test_boot(self, testdevices):
    #     print(testdevices)
    #     print("Boot test")
    #     assert len(testdevices) == 2

    def test_scan(self, advertiser, scanner):
        print("Test stderr", file=sys.stderr)
        print("Scan test")
        print(advertiser)
        print(scanner)

        time.sleep(5)
        assert False
