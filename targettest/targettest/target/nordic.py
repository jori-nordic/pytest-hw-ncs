#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import threading
import time
import logging
from contextlib import contextmanager
from pynrfjprog import LowLevel, APIError
from pynrfjprog import Parameters
from targettest.target.interface import TargetDevice
from targettest.target_logger.rtt import RTTLogger
from targettest.target_logger.rpc import RPCLogger
from targettest.target_logger.interface import TargetLogger

LOGGER = logging.getLogger(__name__)

@contextmanager
def SeggerEmulator(family='UNKNOWN', id=None, core=None):
    """Instantiate the pynrfjprog API and optionally connect to a device."""
    try:
        api = LowLevel.API(family)
        api.open()
        if id is not None:
            api.connect_to_emu_with_snr(id, 4000)

        if core is not None:
            cpu = coproc[core]
            api.select_coprocessor(cpu)

        yield api

    finally:
        if id is not None:
            api.disconnect_from_emu()
        api.close()

coproc = {'APP': Parameters.CoProcessor.CP_APPLICATION,
          'NET': Parameters.CoProcessor.CP_NETWORK}

def select_core(api, core):
    cpu = coproc[core]
    LOGGER.debug(f'[{cpu.name}] select core')
    api.select_coprocessor(cpu)

@contextmanager
def SeggerDevice(family='UNKNOWN', id=None, core='APP'):
    with SeggerEmulator(family, id, core=core) as api:
        try:
            api.connect_to_device()
        except APIError.APIError as e:
            if family != 'NRF52':
                select_core(api, 'NET')
                api.recover()

            select_core(api, 'APP')
            api.recover()
            select_core(api, core)

        LOGGER.debug(f'[{id}] jlink open')

        yield api

        api.disconnect_from_device()
        LOGGER.debug(f'[{id}] jlink closed')


def get_fw_path(root_dir, test_path, board, network_core=None):
    """Find the firmware for the calling test suite"""
    rel_suite_path = test_path.parent.relative_to(root_dir)

    # This assumes all multi-image builds are built using sysbuild

    if network_core is not None:
        build_dir = root_dir / 'build' / rel_suite_path / board / 'hci_ipc'
    else:
        build_dir = root_dir / 'build' / rel_suite_path / board / 'fw'

    fw_hex = build_dir / 'zephyr' / 'zephyr.hex'

    assert fw_hex.exists(), f"Missing firmware: {fw_hex}"

    return fw_hex


class NordicDevkit(TargetDevice):
    def __init__(self,
                 snr,
                 family,
                 name,
                 target_logger_class=TargetLogger):

        self._emu = None
        self._segger_id = int(snr)
        self._port = None
        self._in_use = False

        self._target_logger = None
        self._log = ''

        super().__init__(snr, family.upper(), name, target_logger_class)

    def __repr__(self):
        return f'{self.name}: {self.snr} {self._port}'

    @property
    def serial_port(self):
        assert self._port is not None
        return self._port

    def flash(self, root_path, test_path, board_name):
        if self.family == 'NRF53':
            # Flash the network core first
            fw_hex = get_fw_path(root_path, test_path, board_name, network_core=True)
            flash(self.snr, self.family, fw_hex, core='NET')

        fw_hex = get_fw_path(root_path, test_path, board_name)
        flash(self.snr, self.family, fw_hex)

        # TODO: maybe halt instead? At least try to reduce number of reset calls
        reset(self.snr, self.family)

    def open(self, connect_emulator=True):
        LOGGER.debug(f'[{self.snr}] devkit open')
        self._in_use = True

        # Rest of setup involves the Segger ICE
        if connect_emulator:
            self.apiobject = SeggerDevice(self.family, self.snr)
            self._emu = self.apiobject.__enter__()

        # Don't try to fetch the port path if supplied
        if self._port is None:
            self._port = get_serial_port(self.snr,
                                         self.family)

    def close(self):
        LOGGER.debug(f'[{self.snr}] devkit close')

        if self._emu is not None:
            self.apiobject.__exit__(None, None, None)

        self._in_use = False

    def _log_handler(self, rx: str):
        self._log += rx

    @property
    def log(self):
        return self._log

    def append_to_log(self, rx: str):
        self._log_handler(rx)

    def open_log(self):
        self._log = ''

        if self._target_logger_class is RTTLogger:
            # TODO: figure out a better place and time for this. We need an
            # already open segger emulator, so finding the correct place to
            # initialize is not trivial.
            self._target_logger = self._target_logger_class(output_handler=self._log_handler,
                                                           id=self.snr,
                                                           emulator=self._emu)
        elif self._target_logger_class is RPCLogger:
            # In the log-over-RPC case, we don't need special parameters:
            # NIH-RPC will directly call the Devkit() log handler function when
            # LOG packets are received.
            self._target_logger = self._target_logger_class(output_handler=self._log_handler)
        else:
            raise Exception(f"Logger class {self._target_logger} not supported")

        self._target_logger.open()

    def close_log(self):
        if self._target_logger is not None:
            self._target_logger.close()

    def available(self):
        return not self._in_use

    def reset(self):
        if self._emu is None:
            LOGGER.info(f'[{self.snr}] interactive reset')
            input(f'\nReset device [{self.snr}] and press enter')
        else:
            reset(self.snr, self.family, self._emu)

    def halt(self):
        if self._in_use and self._emu is None:
            # This means that we have a connection from another program that we
            # don't want interrupted, e.g. a debugger. In that case we don't
            # want to connect just to halt the device.
            LOGGER.info(f'[{self.snr}] skipping halt')
        else:
            halt(self.snr, self.family, self._emu)


def get_serial_port(id, family=None, api=None):
    def _get_serial_port(id, family, api):
        ports = api.enum_emu_com_ports(id)

        LOGGER.debug(f'[{id}] Serial ports: {ports}')

        assert len(ports) > 0, f"[{id}] is not connected"

        # TODO: add better rules depending on family
        # Probably in a platform.yml describing those

        sorted_ports = sorted(ports, key=lambda port: port.vcom)

        if family == 'NRF53':
            # Will get the last serial port. This is connected to the APP core
            # on nRF53 DKs.
            return sorted_ports[-1].path
        else:
            return sorted_ports[0].path

    if api is not None:
        return _get_serial_port(id, family, api)

    # TODO: figure out if this messes with a connected debugger
    with SeggerEmulator() as api:
        return _get_serial_port(id, family, api)

def flash(id, family, hex_path, core='APP'):
    with SeggerDevice(family, id, core) as cpu:
        LOGGER.info(f'[{id}] [{family}-{core}] Flashing with {str(hex_path)}')
        # Erase the target's flash
        cpu.erase_file(hex_path)

        # Flash & verify
        cpu.program_file(hex_path)
        cpu.verify_file(hex_path)

def reset(id, family, emu=None):
    if emu is not None:
        LOGGER.info(f'[{id}] reset')
        # emu.debug_reset()
        emu.pin_reset()
    else:
        with SeggerDevice(family, id) as emu:
            LOGGER.info(f'[{id}] reset')
            emu.pin_reset()
            # Other ways to reset the device:
            # emu.debug_reset()
            # emu.sys_reset()
            # emu.hard_reset()

def halt(id, family, emu=None):
    LOGGER.info(f'[{id}] halt')
    if emu is not None:
        emu.halt()
    else:
        with SeggerDevice(family, id) as emu:
            emu.halt()

def list_connected_nordic_devices():
    with SeggerEmulator() as api:
        ids = api.enum_emu_snr()
        devkits = []
        for id in ids:
            api.connect_to_emu_with_snr(id)
            family = api.read_device_family()
            info = {'segger': id,
                    'family': family}
            devkits.append(info)
            api.disconnect_from_emu()

        return devkits
