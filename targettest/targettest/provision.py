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

def halt_unused(devkits: list):
    unused = [dk for dk in devkits if not dk.in_use]
    LOGGER.info(f'Halting unused DKs {unused}')
    for dk in unused:
        dk.halt()

@contextmanager
def FlashedDevice(root_dir,
                  test_path,
                  family='NRF53',
                  id=None,
                  board='nrf5340dk/nrf5340/cpuapp',
                  name=None,
                  flash_device=True,
                  emu=True):

    # Select HW device
    dev = get_available_dk(family, id)
    assert dev is not None, f'Hardware device not found'

    family = family.upper()

    if name is not None:
        dev.name = name

    if flash_device:
        dev.flash(root_dir, test_path, board)

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
