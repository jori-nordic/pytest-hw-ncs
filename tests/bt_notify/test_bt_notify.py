#!/usr/bin/env python3
from targettest.rpc import RPCDevice
from targettest.devkit import get_available_dk
import pytest
import sys
from contextlib import contextmanager

@contextmanager
def hwdevice():
    dev = get_available_dk()
    dev.open()
    yield dev
    dev.close()

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
def rpcdevice(hwdev):
    # Manage RPC transport
    # device = RPC "pipe"
    device = RPCDevice(hwdev)
    device.open()
    yield device
    device.close()

@pytest.fixture
def dut():
    with hwdevice() as hwdev:
        with rpcdevice(hwdev) as rpcdev:
            init_bluetooth(rpcdev)
            yield rpcdev

@pytest.fixture
def tester():
    with hwdevice() as hwdev:
        with rpcdevice(hwdev) as rpcdev:
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
