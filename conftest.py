#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import pytest
import yaml
import logging
from contextlib import ExitStack
from targettest.devkit import Devkit, discover_dks, halt_unused
from targettest.provision import (register_dk, get_dk_list,
                                  FlashedDevice, RPCDevice, TestDevice)

LOGGER = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption("--no-flash", action="store_true",
                     help='Skip the erase/flash cycle')

    # Note: has to be called with `-s` option so the test session can prompt the
    # user to reset the device(s) manually.
    parser.addoption("--no-emu", action="store_true",
                     help='Don\'t connect to jlink emulator, has to be called with `-s`. \
This allows the use of a debugger during the test run.')

    parser.addoption("--devconf", action="store",
                     help='Use a static device configuration (see sample_devconf.yml)')

    parser.addoption("--dut-family", action="store",
                     help='specify a device (nrf52, nrf53) family for the DUT.')

    parser.addoption("--tester-family", action="store",
                     help='specify a device (nrf52, nrf53) family for the Tester.')

    parser.addoption("--no-rtt", action="store_true",
                     help="Disable use of Segger RTT for logging")

    parser.addoption("--single-device", action="store_true",
                     help="some help")


def get_device_list_from_devconf(devconf):
    LOGGER.info(f'Using devconf: {devconf}')
    with open(devconf, 'r') as stream:
        # Assuming only one config per devconf file
        parsed = yaml.safe_load(stream)

    devices = parsed['devices']

    return devices

@pytest.fixture(scope="session", autouse=True)
def devkits(request):
    # Don't discover devices if devconf was specified on cli
    devconf = request.config.getoption("--devconf")
    if devconf is not None:
        LOGGER.info(f'Getting devices from devconf')
        dk_list = get_device_list_from_devconf(devconf)
    else:
        LOGGER.info(f'Discovering devices...')
        dk_list = None

    dks = discover_dks(dk_list)

    LOGGER.info(f'Registering devices: {[devkit.segger_id for devkit in dks]}')

    rtt_logging = not request.config.getoption("--no-rtt")

    for devkit in dks:
        devkit.rtt_logging = rtt_logging
        register_dk(devkit)

def get_device_by_name(devices, name):
    for dev in devices:
        if dev['name'] == name:
            return dev

    return None

def get_board_by_family(family: str):
    if family.upper() == 'NRF52':
        return 'nrf52840dk/nrf52840'
    else:
        return 'nrf5340dk/nrf5340/cpuapp'

@pytest.fixture(scope="class")
def flasheddevices(request):
    # TODO: refactor for an arbitrary number of devices (1->n)
    flash = not request.config.getoption("--no-flash")
    emu = not request.config.getoption("--no-emu")
    devconf = request.config.getoption("--devconf")
    dut_family = request.config.getoption("--dut-family")
    tester_family = request.config.getoption("--tester-family")
    single_device = request.config.getoption("--single-device")
    rtt_logging = not request.config.getoption("--no-rtt")

    # Select the devices families
    if dut_family is None:
        dut_family = 'nrf53'

    if tester_family is None:
        tester_family = 'nrf53'

    # Select the actual devices
    dut_id = None
    tester_id = None

    if devconf is not None:
        with open(devconf, 'r') as stream:
            # Assuming only one config per devconf file
            parsed = yaml.safe_load(stream)

        config = parsed['configurations'][0]
        devices = parsed['devices']

        dut_name = config['dut_' + dut_family]
        dut_id = get_device_by_name(devices, dut_name)['segger']
        assert dut_id, 'DUT not found in configuration'

        tester_name = config['tester_' + tester_family]
        tester_id = get_device_by_name(devices, tester_name)['segger']
        assert tester_id, 'Tester not found in configuration'

        LOGGER.info(f'DUT: {dut_id} Tester: {tester_id}')

    # ExitStack is equivalent to multiple nested `with` statements, but is more readable
    with ExitStack() as stack:
        dut_dk = stack.enter_context(
            FlashedDevice(request,
                          name='DUT',
                          family=dut_family,
                          id=dut_id,
                          board=get_board_by_family(dut_family),
                          flash_device=flash,
                          emu=emu))

        if not single_device:
            tester_dk = stack.enter_context(
                FlashedDevice(request,
                            name='Tester',
                            family=tester_family,
                            id=tester_id,
                            board=get_board_by_family(tester_family),
                            flash_device=flash,
                            emu=emu))
        else:
            tester_dk = None

        devices = {'dut_dk': dut_dk, 'tester_dk': tester_dk}
        halt_unused(get_dk_list())

        yield devices

        LOGGER.debug('closing DK APIs')


@pytest.fixture()
def testdevice(flasheddevices):
    with ExitStack() as stack:
        try:
            dut_dk = flasheddevices['dut_dk']

            # TODO: what about --no-emu. Does it mean only halt the first device?

            LOGGER.debug(f'opening DUT rpc {dut_dk.segger_id}')
            dut_rpc = stack.enter_context(RPCDevice(dut_dk))
            dut = TestDevice(dut_dk, dut_rpc)

            devices = {'dut': dut}
            LOGGER.info(f'Test device: {devices}')

            yield devices

            # Flush logs.
            # TODO: either namespace RPC cmds or add special packet
            dut.rpc.cmd(7)

        finally:
            LOGGER.info(f'[{dut_dk.segger_id}] DUT logs:\n{dut_dk.log}')

            LOGGER.debug('closing RPC channels')


@pytest.fixture()
def testdevices(flasheddevices):
    with ExitStack() as stack:
        try:
            dut_dk = flasheddevices['dut_dk']
            tester_dk = flasheddevices['tester_dk']

            LOGGER.debug(f'opening DUT rpc {dut_dk.segger_id}')
            dut_rpc = stack.enter_context(RPCDevice(dut_dk))
            dut = TestDevice(dut_dk, dut_rpc)

            LOGGER.debug(f'opening Tester rpc {tester_dk.segger_id}')
            tester_rpc = stack.enter_context(RPCDevice(tester_dk))
            tester = TestDevice(tester_dk, tester_rpc)

            devices = {'dut': dut, 'tester': tester}
            LOGGER.info(f'Test devices: {devices}')

            yield devices

            # Flush logs.
            # TODO: either namespace RPC cmds or add special packet
            dut.rpc.cmd(7)
            tester.rpc.cmd(7)

        finally:
            LOGGER.info(f'[{dut_dk.segger_id}] DUT logs:\n{dut_dk.log}')
            LOGGER.info(f'[{tester_dk.segger_id}] Tester logs:\n{tester_dk.log}')

            LOGGER.debug('closing RPC channels')
