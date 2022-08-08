#!/usr/bin/env python3

import pytest
from contextlib import contextmanager, ExitStack
from targettest.devkit import discover_dks
from targettest.provision import register_dk, FlashedDevice, RPCDevice


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
def testdevices(request):
    with ExitStack() as stack:
        dut_device = stack.enter_context(FlashedDevice(request))
        tester_device = stack.enter_context(FlashedDevice(request, family='NRF52', board='nrf52840dk_nrf52840'))

        print(f'opening DUT rpc {dut_device.segger_id}')
        dut = stack.enter_context(RPCDevice(dut_device))

        print(f'opening Tester rpc {tester_device.segger_id}')
        tester = stack.enter_context(RPCDevice(tester_device))

        devices = {'dut': dut, 'tester': tester}
        print(f'testdevices: {devices}')

        yield devices

        print('closing testdevices')
