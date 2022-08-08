#!/usr/bin/env python3
import pytest
import sys
import time


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

@pytest.fixture
def advertiser(testdevices):
    configure_advertiser(testdevices['dut'])
    return testdevices['dut']

@pytest.fixture
def scanner(testdevices):
    configure_scanner(testdevices['tester'])
    return testdevices['tester']


class TestBluetoothNotification():

    def test_boot(self, testdevices):
        print("Boot test")
        print(testdevices)
        assert False

    def test_notify(self, advertiser, scanner):
        print("Notify test")
        print(advertiser)
        print(scanner)
        assert False
