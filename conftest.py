#!/usr/bin/env python3

import pytest
from contextlib import contextmanager, ExitStack
from targettest.devkit import discover_dks
from targettest.provision import register_dk, FlashedDevice, RPCDevice, TestDevice


def pytest_addoption(parser):
    # Add option to skip the erase/flash cycle
    parser.addoption("--no-flash", action="store_true")


# TODO: have an option to use a static definition instead
# since looping through the devkits is pretty slow
@pytest.fixture(scope="session", autouse=True)
def devkits():
    print(f'Discovering devices...')
    devkits = discover_dks()
    print(f'Available devices: {[devkit.segger_id for devkit in devkits]}')
    for devkit in devkits:
        register_dk(devkit)

@pytest.fixture(scope="class")
def flasheddevices(request):
    no_flash = request.config.getoption("--no-flash")

    # ExitStack is equivalent to multiple nested `with` statements, but is more readable
    with ExitStack() as stack:
        dut_dk = stack.enter_context(FlashedDevice(request, no_flash=no_flash))
        tester_dk = stack.enter_context(FlashedDevice(request, family='NRF52', board='nrf52840dk_nrf52840', no_flash=no_flash))

        devices = {'dut_dk': dut_dk, 'tester_dk': tester_dk}

        yield devices

        print('closing DK APIs')

@pytest.fixture()
def testdevices(flasheddevices):
    with ExitStack() as stack:
        dut_dk = flasheddevices['dut_dk']
        print(f'opening DUT rpc {dut_dk.segger_id}')
        dut_rpc = stack.enter_context(RPCDevice(dut_dk))
        dut = TestDevice(dut_dk, dut_rpc)

        tester_dk = flasheddevices['tester_dk']
        print(f'opening Tester rpc {tester_dk.segger_id}')
        tester_rpc = stack.enter_context(RPCDevice(tester_dk))
        tester = TestDevice(tester_dk, tester_rpc)

        devices = {'dut': dut, 'tester': tester}
        print(f'testdevices: {devices}')

        # Start RTT logging

        yield devices

        print('closing RPC channels')

