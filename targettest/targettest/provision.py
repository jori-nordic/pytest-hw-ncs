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

def extract_net_hex(merged_hex, output_hex):
    """Writes a new ihex file containing only the nRF53 network core's FW."""
    ih = IntelHex(str(merged_hex))
    net = ih[0x1000000:]
    net.write_hex_file(str(output_hex))

def get_fw_path(suite, board, network_core=None):
    """Find the firmware for the calling test suite"""
    root_dir = pathlib.Path(suite.config.rootdir)
    script_path = pathlib.Path(getattr(suite.module, "__file__"))
    rel_suite_path = script_path.parent.relative_to(root_dir)

    fw_build = root_dir / 'build' / rel_suite_path / board

    if network_core is None:
        fw_hex = fw_build / 'zephyr' / 'zephyr.hex'
    else:
        merged_hex = fw_build / 'zephyr' / 'merged_domains.hex'
        fw_hex = fw_build / 'zephyr' / 'network.hex'
        extract_net_hex(merged_hex, fw_hex)

    assert fw_build.exists(), "Missing firmware"

    return fw_hex

@contextmanager
def FlashedDevice(request, family='NRF53', id=None, board='nrf5340dk_nrf5340_cpuapp', name=None, flash_device=True, emu=True):
    # Select HW device
    dev = get_available_dk(family, id)
    assert dev is not None, f'Hardware device not found'

    if family is not None:
        family = family.upper()

    if name is not None:
        dev.name = name

    if flash_device:
        # Flash device with test FW & reset it
        if family == 'NRF53':
            # Flash the network core first
            fw_hex = get_fw_path(request, board, network_core=True)
            flash(dev.segger_id, dev.family, fw_hex, core='NET')

        fw_hex = get_fw_path(request, board)
        flash(dev.segger_id, dev.family, fw_hex)

        reset(dev.segger_id, dev.family)

    dev.open(open_emu=emu)

    yield dev

    dev.close()


@contextmanager
def RPCDevice(device: Devkit, group='nrf_pytest'):
    try:
        # Manage RPC transport
        uart = UARTRPCChannel(port=device.port)
        channel = RPCChannel(uart)
        uart.open()
        LOGGER.debug('Wait for RPC ready')
        # Start receiving bytes
        device.reset()
        device.start_logging()

        # Wait until we have received the handshake/init packet
        end_time = time.monotonic() + 5
        while not channel.established:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Unresponsive device')

        if 0:
            # Wait for the READY event (sent from main)
            # This is a user-defined event, it's not part of the nrf-rpc init sequence.
            event = channel.get_evt()
            assert event.opcode == 0x01
            LOGGER.info(f'[{device.port}] channel ready')

        yield channel

    finally:
        LOGGER.info(f'[{device.port}] closing channel')
        uart.close()
        device.stop_logging()
        device.halt()


class TestDevice():
    """Convenience class to group devkit and rpc objects for further usage in
    the test case."""
    def __init__(self, devkit: Devkit, rpc: UARTRPCChannel):
        self.dk = devkit
        self.rpc = rpc

    def __repr__(self):
        return f'[{self.dk.segger_id}] {self.dk.port}'
