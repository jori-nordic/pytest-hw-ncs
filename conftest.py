#!/usr/bin/env python3

import pytest
import yaml
import logging
from contextlib import ExitStack
from targettest.devkit import discover_dks, Devkit
from targettest.provision import register_dk, FlashedDevice, RPCDevice, TestDevice

LOGGER = logging.getLogger(__name__)


def pytest_addoption(parser):
    # Skip the erase/flash cycle
    parser.addoption("--no-flash", action="store_true")

    # Use a specific device configuration
    # See sample_devconf.yaml
    parser.addoption("--devconf", action="store")

    # Specify either nrf52 or nrf53 DUT families
    parser.addoption("--dut-family", action="store")

    # Specify either nrf52 or nrf53 DUT families
    parser.addoption("--tester-family", action="store")


@pytest.fixture(scope="session", autouse=True)
def devkits(request):
    # Don't discover devices if devconf was specified on cli
    devconf = request.config.getoption("--devconf")
    if devconf is not None:
        return

    LOGGER.info(f'Discovering devices...')
    devkits = discover_dks()
    LOGGER.info(f'Available devices: {[devkit.segger_id for devkit in devkits]}')
    for devkit in devkits:
        register_dk(devkit)

def get_device_by_name(devices, name):
    for dev in devices:
        if dev['name'] == name:
            return dev

    return None

def get_board_by_family(family: str):
    if family.upper() == 'NRF52':
        return 'nrf52840dk_nrf52840'
    else:
        return 'nrf5340dk_nrf5340_cpuapp'

@pytest.fixture(scope="class")
def flasheddevices(request):
    no_flash = request.config.getoption("--no-flash")
    devconf = request.config.getoption("--devconf")
    dut_family = request.config.getoption("--dut-family")
    tester_family = request.config.getoption("--tester-family")

    # Select the devices families
    if dut_family is None:
        dut_family = 'nrf53'

    if tester_family is None:
        tester_family = 'nrf53'

    # Select the actual devices
    dut_id = None
    tester_id = None
    if devconf is not None:
        LOGGER.info(f'Using devconf: {devconf}')
        with open(devconf, 'r') as stream:
            # Assuming only one config per devconf file
            parsed = yaml.safe_load(stream)

        config = parsed['configurations'][0]
        devices = parsed['devices']

        dut_name = config['dut_' + dut_family]
        dut_id = get_device_by_name(devices, dut_name)['segger']

        register_dk(Devkit(dut_id, dut_family, dut_name))
        assert dut_id, 'DUT not found in configuration'

        tester_name = config['tester_' + tester_family]
        tester_id = get_device_by_name(devices, tester_name)['segger']

        register_dk(Devkit(tester_id, tester_family, tester_name))
        assert tester_id, 'Tester not found in configuration'

        LOGGER.info(f'DUT: {dut_id} Tester: {tester_id}')

    no_log = True

    # ExitStack is equivalent to multiple nested `with` statements, but is more readable
    with ExitStack() as stack:
        dut_dk = stack.enter_context(
            FlashedDevice(request,
                          family=dut_family,
                          id=dut_id,
                          board=get_board_by_family(dut_family),
                          no_flash=no_flash,
                          no_log=no_log))

        tester_dk = stack.enter_context(
            FlashedDevice(request,
                          family=tester_family,
                          id=tester_id,
                          board=get_board_by_family(tester_family),
                          no_flash=no_flash,
                          no_log=no_log))

        devices = {'dut_dk': dut_dk, 'tester_dk': tester_dk}

        yield devices

        LOGGER.debug('closing DK APIs')

@pytest.fixture()
def testdevices(flasheddevices):
    with ExitStack() as stack:
        dut_dk = flasheddevices['dut_dk']
        LOGGER.debug(f'opening DUT rpc {dut_dk.segger_id}')
        dut_rpc = stack.enter_context(RPCDevice(dut_dk))
        dut = TestDevice(dut_dk, dut_rpc)

        tester_dk = flasheddevices['tester_dk']
        LOGGER.debug(f'opening Tester rpc {tester_dk.segger_id}')
        tester_rpc = stack.enter_context(RPCDevice(tester_dk))
        tester = TestDevice(tester_dk, tester_rpc)

        devices = {'dut': dut, 'tester': tester}
        LOGGER.info(f'Test devices: {devices}')

        # Start RTT logging

        yield devices

        LOGGER.debug('closing RPC channels')
