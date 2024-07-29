#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import time
import pathlib
import logging
from contextlib import contextmanager
from intelhex import IntelHex
from targettest.devkit import Devkit, flash, reset
from targettest.uart_channel import UARTRPCChannel
from targettest.rpc_channel import RPCChannel

LOGGER = logging.getLogger(__name__)

devkits = []
def register_dk(device: Devkit):
    LOGGER.debug(f'Register DK: {device.segger_id}')
    devkits.append(device)

def get_available_dk(family, id=None):
    family = family.upper()

    for dev in devkits:
        if dev.available() and dev.family == family:
            if id is None:
                return dev
            else:
                id = int(id)
                if dev.segger_id == id:
                    return dev
    return None

def get_dk_list():
    return devkits

def get_fw_path(suite, board, hci_uart=False, network_core=None):
    """Find the firmware for the calling test suite"""
    root_dir = pathlib.Path(suite.config.rootdir)
    script_path = pathlib.Path(getattr(suite.module, "__file__"))
    rel_suite_path = script_path.parent.relative_to(root_dir)

    # This assumes all multi-image builds are built using sysbuild

    if hci_uart:
        # TODO: use a more explicit option than just "split"
        # like, --harness-type=hci_uart or --harness-type=hci_ipc etc
        build_dir = root_dir / 'build' / rel_suite_path / board / 'hci_uart'
    elif network_core is not None:
        build_dir = root_dir / 'build' / rel_suite_path / board / 'hci_ipc'
    else:
        build_dir = root_dir / 'build' / rel_suite_path / board / 'fw'

    fw_hex = build_dir / 'zephyr' / 'zephyr.hex'

    assert fw_hex.exists(), f"Missing firmware: {fw_hex}"

    return fw_hex

@contextmanager
def FlashedDevice(request, family='NRF53', id=None, board='nrf5340dk/nrf5340/cpuapp', name=None, flash_device=True, emu=True):
    # Select HW device
    dev = get_available_dk(family, id)
    assert dev is not None, f'Hardware device not found'

    if family is not None:
        family = family.upper()

    if name is not None:
        dev.name = name

    use_hci_uart = name == "DUT 1"

    if flash_device:
        # Flash device with test FW & reset it
        if family == 'NRF53':
            # Flash the network core first
            fw_hex = get_fw_path(request, board, hci_uart=use_hci_uart, network_core=True)
            flash(dev.segger_id, dev.family, fw_hex, core='NET')

        fw_hex = get_fw_path(request, board, hci_uart=use_hci_uart)
        flash(dev.segger_id, dev.family, fw_hex)

        # TODO: maybe halt instead? At least try to reduce number of reset calls
        reset(dev.segger_id, dev.family)

    dev.open(open_emu=emu)

    yield dev

    dev.close()


@contextmanager
def RPCDevice(device: Devkit):
    """A device that has:
       - an established NIH-RPC transport
         - means RPC command handlers are registered on target
       - a target logger backend
       - a device management API (reset/halt/etc)
    """
    try:
        # Manage RPC transport
        uart = UARTRPCChannel(port=device.port)
        channel = RPCChannel(uart, log_handler=device.log_handler)
        uart.open()
        LOGGER.debug('Wait for RPC ready')
        # Start receiving bytes
        device.reset()
        device.open_log()

        # Wait until we have received the handshake/init packet
        end_time = time.monotonic() + 5
        while not channel.established:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Unresponsive device')

        LOGGER.info(f'[{device.port}] channel ready')

        yield channel

    finally:
        LOGGER.info(f'[{device.port}] closing channel')
        uart.close()
        device.close_log()
        device.halt()


class TestDevice():
    """Convenience class to group devkit and rpc objects for further usage in
    the test case."""
    def __init__(self, devkit: Devkit, rpc: UARTRPCChannel):
        self.dk = devkit
        self.rpc = rpc

    def __repr__(self):
        return f'[{self.dk.segger_id}] {self.dk.port}'
