#!/usr/bin/env python3
import pytest
import sys
import time
from contextlib import contextmanager
from targettest.rpc_packet import RPCPacketType, RPCPacket
from targettest.uart_channel import UARTRPCChannel
from conftest import hwdevice


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
    channel = UARTRPCChannel(port=dev.port)
    channel.start()
    while not channel.ready:
        time.sleep(.1)

    event = channel.get_evt()
    assert event.opcode == 0x01 # READY event
    print('Channel ready!')

    yield channel
    print('closing channel!')

    channel.close()

@pytest.fixture(scope="class")
def dut(request):
    with hwdevice(request) as dev:
        with rpcdevice(dev) as rpcdev:
            init_bluetooth(rpcdev)
            yield rpcdev

@pytest.fixture(scope="class")
def tester(request):
    with hwdevice(request) as dev:
        with rpcdevice(dev) as rpcdev:
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
