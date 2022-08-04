#!/usr/bin/env python3
from targettest.rpc import RPCDevice
import pytest
import sys
from contextlib import contextmanager

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    print("Configure adv", file=sys.stderr)
    pass

def configure_scanner(rpcdevice):
    # configure & start scanner
    print("Configure scan", file=sys.stderr)
    pass

def init_bluetooth(rpcdevice):
    # - call `bt_init`
    pass

@contextmanager
def rpcdevice(dev):
    # Manage RPC transport
    # device = RPC "pipe"
    device = RPCDevice(dev)
    device.open()
    yield device
    device.close()

@pytest.fixture
def dut(hwdevice):
    with rpcdevice(hwdevice) as rpcdev:
        init_bluetooth(rpcdev)
        yield rpcdev

@pytest.fixture
def tester(hwdevice):
    with rpcdevice(hwdevice) as rpcdev:
        init_bluetooth(rpcdev)
        yield rpcdev

@pytest.fixture
def advertiser(dut):
    configure_advertiser(dut)
    return dut

@pytest.fixture
def scanner(tester):
    configure_scanner(tester)
    return tester


class TestBluetoothNotification:

    def test_boot(self, dut, tester):
        print("Boot test")
        print(dut)
        assert False

    def test_notify(self, advertiser, scanner):
        print("Notify test")
        print(advertiser)
        print(scanner)
        assert False
