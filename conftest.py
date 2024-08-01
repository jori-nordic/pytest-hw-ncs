#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import pytest
import yaml
import logging
import pathlib
from contextlib import ExitStack, contextmanager
from targettest.target_logger.rtt import RTTLogger
from targettest.target_logger.rpc import RPCLogger
from targettest.devkit import Devkit, list_connected_nordic_devices
from targettest.provision import (register_dk, get_dk_list, halt_unused,
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

    parser.addoption("--num-testers", action="store",
                     help="Number of tester devices to provision")


def get_device_list_from_devconf(devconf):
    LOGGER.info(f'Using devconf: {devconf}')
    with open(devconf, 'r') as stream:
        # Assuming only one config per devconf file
        parsed = yaml.safe_load(stream)

    devices = parsed['devices']

    return devices

def get_logger_type(request):
    rtt = not request.config.getoption("--no-rtt")

    if rtt:
        type = RTTLogger
    else:
        type = RPCLogger

    LOGGER.debug(f'Using logger type: {type}')

    return type


def make_devkits(device_list=None, target_logger_type=None):
    if device_list is None:
        # If no devices are specified, grab all the connected nordic devkits.
        device_list = list_connected_nordic_devices()

    devkits = []
    for device in device_list:
        family = device['family'].upper()
        id = int(device['segger'])
        devkits.append(
            Devkit(id,
                    family,
                    f'dk-{family}-{id}',
                    target_logger_type))

    return devkits


@pytest.fixture(scope="session", autouse=True)
def devkits(request):
    # Don't discover devices if devconf was specified on cli
    devconf = request.config.getoption("--devconf")
    if devconf is not None:
        LOGGER.info(f'Get devices from devconf')
        dk_list = get_device_list_from_devconf(devconf)
    else:
        LOGGER.info(f'Get devices automatically')
        dk_list = None

    logger_type = get_logger_type(request)
    dks = make_devkits(dk_list, logger_type)

    for dk in dks:
        register_dk(dk)


def get_device_id_from_config(config, devices, name, family):
    def _get_id_by_name(devices, name):
        for dev in devices:
            if dev['name'] == name:
                return dev

        return None

    device_name = config[name + '_' + family]
    device_id = _get_id_by_name(devices, device_name)['segger']

    assert device_id, f'{name} not found in configuration'
    return device_id


def get_board_by_family(family: str):
    if family.upper() == 'NRF52':
        return 'nrf52840dk/nrf52840'
    else:
        return 'nrf5340dk/nrf5340/cpuapp'

@contextmanager
def make_flasheddevices(root_dir,
                        test_path,
                        flash,
                        emu,
                        devconf,
                        dut_family,
                        tester_family,
                        num_testers,
                        rtt_logging):

    # Select the devices families
    if dut_family is None:
        dut_family = 'nrf53'

    if tester_family is None:
        tester_family = 'nrf53'

    # Select the actual devices
    dut_id = None
    tester_ids = []

    if devconf is None:
        for num in range(num_testers):
            # FlashedDevice() will grab an available device at random
            tester_ids.append(None)

        LOGGER.info(f'No devconf, will grab any available devices')
    else:
        with open(devconf, 'r') as stream:
            # Assuming only one config per devconf file
            parsed = yaml.safe_load(stream)

        config = parsed['configurations'][0]
        devices = parsed['devices']

        dut_id = get_device_id_from_config(config, devices, "dut", dut_family)

        for num in range(num_testers):
            tester_id = get_device_id_from_config(config, devices, f'tester_{num}', tester_family)
            tester_ids.append(tester_id)

        LOGGER.info(f'devconf: DUT: {dut_id} Testers: {tester_ids}')

    # ExitStack is equivalent to multiple nested `with` statements, but is more readable
    with ExitStack() as stack:
        dut_dk = stack.enter_context(
            FlashedDevice(root_dir,
                          test_path,
                          name='DUT',
                          family=dut_family,
                          id=dut_id,
                          board=get_board_by_family(dut_family),
                          flash_device=flash,
                          emu=emu))

        tester_dks = []
        for tester_id in tester_ids:
            tester_dk = stack.enter_context(
                FlashedDevice(root_dir,
                              test_path,
                              name='Tester',
                              family=tester_family,
                              id=tester_id,
                              board=get_board_by_family(tester_family),
                              flash_device=flash,
                              emu=emu))
            tester_dks.append(tester_dk)

        devices = {'dut_dk': dut_dk, 'tester_dks': tester_dks}
        halt_unused(get_dk_list())

        yield devices

        LOGGER.debug('closing DK APIs')


@pytest.fixture(scope="class")
def flasheddevices(request):
    # TODO: refactor for an arbitrary number of devices (1->n)
    flash = not request.config.getoption("--no-flash")
    emu = not request.config.getoption("--no-emu")
    devconf = request.config.getoption("--devconf")
    dut_family = request.config.getoption("--dut-family")
    tester_family = request.config.getoption("--tester-family")
    num_testers_str = request.config.getoption("--num-testers")
    rtt_logging = not request.config.getoption("--no-rtt")
    root_dir = pathlib.Path(request.config.rootdir)
    # This builds a path from the tests' file names
    # E.g. `test_bt_notify.py` -> `tests/bt_notify/`
    test_path = pathlib.Path(getattr(request.module, "__file__"))

    # sad.jpg
    try:
        num_testers = int(num_testers_str)
    except:
        num_testers = 1

    with make_flasheddevices(root_dir, test_path, flash, emu, devconf, dut_family, tester_family, num_testers, rtt_logging) as devices:
        yield devices


@contextmanager
def make_testdevices(request, flasheddevices, num_testers):
    """Return a ready-to-use hardware configuration.

    I.e. a list of devices that:
    - are flashed (only once per-class)
    - have an established RPC connection
    - have a connected log sink

    There is always at least one device, the "DUT", optionally followed by a
    bunch of "Tester" devices.

    The DUT fixture should be parameterized such that each testcase that uses
    the `testdevices` fixture runs once per DUT platform/parameter.

    The Testers fixture is not parameterized, but we can still choose its
    platform using a command line option.
    """

    dut_dk = flasheddevices['dut_dk']
    tester_dks = flasheddevices['tester_dks']

    assert len(tester_dks) >= num_testers, "Not enough testers have been flashed"

    with ExitStack() as stack:
        LOGGER.debug(f'opening DUT rpc {dut_dk.segger_id}')
        dut_rpc = stack.enter_context(RPCDevice(dut_dk))
        dut = TestDevice(dut_dk, dut_rpc)

        testers = []
        for i in range(num_testers):
            tester_dk = tester_dks[i]
            LOGGER.debug(f'opening Tester rpc {tester_dk.segger_id}')
            tester_rpc = stack.enter_context(RPCDevice(tester_dk))
            tester = TestDevice(tester_dk, tester_rpc)
            testers.append(tester)

        devices = {'dut': dut, 'testers': testers}
        LOGGER.info(f'Test devices: {devices}')

        yield devices

        # Flush logs.
        # TODO: either namespace RPC cmds or add special packet
        try:
            dut.rpc.cmd(7)
            for tester in testers:
                tester.rpc.cmd(7)
        except:
            pass


@pytest.fixture()
def testdevice(request, flasheddevices):
    with make_testdevices(request, flasheddevices, num_testers=0) as devices:
        yield devices

@pytest.fixture()
def testdevices(request, flasheddevices):
    with make_testdevices(request, flasheddevices, num_testers=1) as devices:
        yield devices

@pytest.fixture()
def harness_multi_link(request, flasheddevices):
    with make_testdevices(request, flasheddevices, num_testers=2) as devices:
        yield devices
