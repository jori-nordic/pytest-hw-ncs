#!/usr/bin/env python3
import time
import pathlib
import logging
from contextlib import contextmanager
from targettest.devkit import Devkit, flash, reset
from targettest.uart_channel import UARTRPCChannel

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

def get_fw_path(suite, board, child_image_name=None):
    """Find the firmware for the calling test suite"""
    root_dir = pathlib.Path(suite.config.rootdir)
    script_path = pathlib.Path(getattr(suite.module, "__file__"))
    rel_suite_path = script_path.parent.relative_to(root_dir)

    fw_build = root_dir / 'build' / rel_suite_path / board

    if child_image_name is None:
        fw_hex = fw_build / 'zephyr/zephyr.hex'
    else:
        fw_hex = fw_build / child_image_name / 'zephyr/zephyr.hex'

    assert fw_build.exists(), "Missing firmware"

    return fw_hex


@contextmanager
def FlashedDevice(request, family='NRF53', id=None, board='nrf5340dk_nrf5340_cpuapp', no_flash=False, no_log=False):
    # Select HW device
    dev = get_available_dk(family, id)
    assert dev is not None, f'Hardware device not found'

    if family is not None:
        family = family.upper()

    if not no_flash:
        # Flash device with test FW & reset it
        if family == 'NRF53':
            # Flash the network core first
            fw_hex = get_fw_path(request, board, child_image_name='hci_rpmsg')
            flash(dev.segger_id, dev.family, fw_hex, core='NET')

        fw_hex = get_fw_path(request, board)
        flash(dev.segger_id, dev.family, fw_hex)

        reset(dev.segger_id, dev.family)

    # Open device comm channel
    dev.open(not no_log)

    yield dev

    dev.close()


@contextmanager
def RPCDevice(device: Devkit, group='nrf_pytest'):
    try:
        # Manage RPC transport
        channel = UARTRPCChannel(port=device.port, group_name=group)
        channel.start()
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

        # Wait for the READY event (sent from main)
        # This is a user-defined event, it's not part of the nrf-rpc init sequence.
        event = channel.get_evt()
        assert event.opcode == 0x01
        LOGGER.info(f'[{device.port}] channel ready')

        yield channel

    finally:
        LOGGER.info(f'[{device.port}] closing channel')
        channel.stop()
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
