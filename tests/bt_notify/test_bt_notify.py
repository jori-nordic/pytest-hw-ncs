#!/usr/bin/env python3
import pytest
from contextlib import contextmanager

class Devkit:
    def __init__(self, id, name):
        self.segger_id = id
        self.name = name
        self.in_use = False
    def open(self):
        print(f'Devkit {self.name} opened')
        self.in_use = True
    def close(self):
        print(f'Devkit {self.name} closed')
        self.in_use = False
    def available(self):
        return not self.in_use

devkits = [Devkit(1, "device-one"),
           Devkit(2, "device-two"),
           Devkit(3, "device-three")]

@contextmanager
def hwdevice():
    dev = get_available_dk()
    dev.open()
    yield dev
    dev.close()

class RPCDevice:
    def __init__(self, testdevice):
        self.serial = None
        self.testdevice = testdevice
    def open(self):
        print("RPC open")
        self.serial = 1
    def close(self):
        print("RPC close")
        self.serial = 0

def configure_advertiser(rpcdevice):
    # configure & start advertiser with static name
    print("Configure adv")
    pass

def configure_scanner(rpcdevice):
    # configure & start scanner
    print("Configure scan")
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

def get_available_dk():
    for dev in devkits:
        if dev.available():
            return dev
    return False

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
