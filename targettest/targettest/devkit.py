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
from targettest.rtt_logger import RTTLogger
from targettest.rpc_logger import RPCLogger
from targettest.abstract_logger import TargetLogger

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


class Devkit:
    def __init__(self, id, family, name, port=None, target_logger_class=TargetLogger):
        self.emu = None
        self.segger_id = int(id)
        self.family = family.upper()
        self.port = port

        self.name = name
        self.in_use = False

        self.log = ''
        self._target_logger_class = target_logger_class
        self.target_logger = None

    def __repr__(self):
        return f'{self.name}: {self.segger_id} {self.port} '

    def log_handler(self, rx: str):
        self.log += rx

    def open(self, open_emu):
        LOGGER.debug(f'[{self.segger_id}] devkit open')
        self.in_use = True

        # Don't try to fetch the port path if supplied
        if self.port is None:
            self.port = get_serial_port(self.segger_id)

        # Rest of setup involves the Segger ICE
        if open_emu:
            self.apiobject = SeggerDevice(self.family, self.segger_id)
            self.emu = self.apiobject.__enter__()

        self.in_use = True

    def close(self):
        LOGGER.debug(f'[{self.segger_id}] devkit close')

        if self.emu is not None:
            self.apiobject.__exit__(None, None, None)

        self.in_use = False

    def open_log(self):
        self.log = ''

        if self._target_logger_class is RTTLogger:
            # TODO: figure out a better place and time for this. We need an
            # already open segger emulator, so finding the correct place to
            # initialize is not trivial.
            self.target_logger = self._target_logger_class(output_handler=self.log_handler,
                                                           id=self.segger_id,
                                                           emulator=self.emu)
        elif self._target_logger_class is RPCLogger:
            # In the log-over-RPC case, we don't need special parameters:
            # NIH-RPC will directly call the Devkit() log handler function when
            # LOG packets are received.
            self.target_logger = self._target_logger_class(output_handler=self.log_handler)
        else:
            raise Exception(f"Logger class {self.target_logger} not supported")

        self.target_logger.open()

    def close_log(self):
        if self.target_logger is not None:
            self.target_logger.close()

    def available(self):
        return not self.in_use

    def reset(self):
        if self.emu is None:
            LOGGER.info(f'[{self.segger_id}] interactive reset')
            input(f'\nReset device [{self.segger_id}] and press enter')
        else:
            reset(self.segger_id, self.family, self.emu)

    def halt(self):
        if self.emu is None:
            LOGGER.info(f'[{self.segger_id}] skipping halt')
        else:
            halt(self.segger_id, self.family, self.emu)


def get_serial_port(id, family=None, api=None):
    def _get_serial_port(id, family):
        ports = api.enum_emu_com_ports(id)

        LOGGER.debug(f'[{id}] Serial ports: {ports}')

        assert len(ports) > 0, f"[{id}] is not connected"

        # TODO: add better rules depending on family
        # Probably in a platform.yml describing those

        if family == 'nrf53':
            # Will get the last serial port. This is connected to the APP core
            # on nRF53 DKs.
            sorted_ports = sorted(ports, key=lambda port: port.vcom)
            return ports[-1].path
        else:
            return ports[0].path

    assert api is not None

    return _get_serial_port(id, family)

def flash(id, family, hex_path, core='APP', reset=True):
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

def halt_unused(devkits: list):
    unused = [dk for dk in devkits if not dk.in_use]
    for dk in unused:
        halt(dk.segger_id, dk.family)

def discover_dks(device_list=None, target_logger_class=TargetLogger):
    # TODO: maybe discover_dks should rather return a dict instead of
    # registering full-blown Devkit() objects. That way, the caller can register
    # those, and register the target logger too.
    #
    # device_list: list of dicts with name, id, family
    if device_list is not None:
        devkits = []
        with SeggerEmulator() as api:
            for device in device_list:
                family = device['family'].upper()
                id = int(device['segger'])
                port = get_serial_port(id, family, api)
                devkits.append(
                    Devkit(id, family, f'dk-{family}-{id}', port, target_logger_class))

        return devkits

    with SeggerEmulator() as api:
        ids = api.enum_emu_snr()
        devkits = []
        for id in ids:
            api.connect_to_emu_with_snr(id)
            family = api.read_device_family()
            port = get_serial_port(id, family, api)
            devkits.append(
                Devkit(id, family, f'dk-{family}-{id}', port, target_logger_class))
            api.disconnect_from_emu()

    return devkits
