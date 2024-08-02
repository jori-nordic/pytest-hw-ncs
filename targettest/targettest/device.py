#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import time
import logging
from contextlib import contextmanager
from targettest.packet_transport.uart import UARTPacketTransport
from targettest.rpc import RPCChannel
from targettest.devkit import Devkit
from targettest.provision import get_available_dk

LOGGER = logging.getLogger(__name__)


@contextmanager
def FlashedDevice(root_dir,
                  test_path,
                  family='NRF53',
                  id=None,
                  board='nrf5340dk/nrf5340/cpuapp',
                  name=None,
                  flash_device=True,
                  emu=True):
    """A device that has been flashed with the correct FW for the test"""

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

    This contextmanager will print the device logs before exiting.
    """
    try:
        # Manage RPC transport
        uart = UARTPacketTransport(port=device.port)
        rpc = RPCChannel(uart, log_handler=device.log_handler)
        uart.open(rpc.handler)
        LOGGER.debug('Wait for RPC ready')
        # Start receiving bytes
        device.reset()
        device.open_log()

        # Wait until we have received the handshake/init packet
        end_time = time.monotonic() + 5
        while not rpc.established:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Unresponsive device')

        LOGGER.info(f'[{device.port}] rpc ready')

        yield rpc

    finally:
        LOGGER.info(f'[{device.port}] closing rpc')
        uart.close()
        device.close_log()
        device.halt()
        LOGGER.info(f'[{device.segger_id}] Device logs:\n{device.log}')


class TestDevice():
    """Convenience class to group devkit and rpc objects for further usage in
    the test case."""
    def __init__(self, devkit: Devkit, rpc: UARTPacketTransport):
        self.dk = devkit
        self.rpc = rpc

    def __repr__(self):
        return f'[{self.dk.segger_id}] {self.dk.port}'
