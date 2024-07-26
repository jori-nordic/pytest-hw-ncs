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


class RTTLogger(threading.Thread):
    def __init__(self, emu, handler):
        threading.Thread.__init__(self, daemon=True)
        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self.ready = False
        self.handler = handler
        self.emu = emu

    def run(self):
        LOGGER.debug(f'RTT start')
        self._stop_rx_flag.clear()

        LOGGER.debug(f'RTT search...')
        self.emu.rtt_start()
        while not (self.emu.rtt_is_control_block_found() or
                   self._stop_rx_flag.is_set()):
            time.sleep(.1)

        self.ready = True

        LOGGER.debug(f'RTT opened')
        while not self._stop_rx_flag.is_set():
            recv = self.emu.rtt_read(0, 255)
            if len(recv) > 0:
                self.handler(recv)

            # Yield to other threads
            time.sleep(.01)

        LOGGER.debug(f'RTT stop')
        self.emu.rtt_stop()

    def open(self):
        self.start()

    def close(self):
        self._stop_rx_flag.set()
        self.join()


class Devkit:
    def __init__(self, id, family, name, port=None, rtt_logging=True):
        self.emu = None
        self.segger_id = int(id)
        self.family = family.upper()
        self.port = port
        self.rtt_logging = rtt_logging

        self.name = name
        self.in_use = False

        self.log = ''

    def __repr__(self):
        return f'{self.name}: {self.segger_id} {self.port} '

    def log_handler(self, rx: str):
        self.log += rx

    def start_logging(self):
        self.log = ''

        if not self.rtt_logging:
            LOGGER.debug(f'[{self.segger_id}] skipping log setup')
            return

        self.rtt = RTTLogger(self.emu, self.log_handler)
        self.rtt.start()
        end_time = time.monotonic() + 15
        while not self.rtt.ready:
            time.sleep(.1)
            if time.monotonic() > end_time:
                raise Exception('Unable to start logging')

        LOGGER.debug(f'[{self.segger_id}] logging started')

    def stop_logging(self):
        if not self.rtt_logging:
            LOGGER.debug(f'[{self.segger_id}] skipping log teardown')
            return

        try:
            self.rtt.close()
        finally:
            LOGGER.debug(f'[{self.segger_id}] logging stopped')

    def open(self, open_emu):
        LOGGER.debug(f'[{self.segger_id}] devkit open')
        self.in_use = True

        # Don't try to fetch the port path if supplied
        if self.port is None:
            self.port = get_serial_port(self.segger_id)

        if open_emu:
            self.apiobject = SeggerDevice(self.family, self.segger_id)
            self.emu = self.apiobject.__enter__()
        else:
            self.rtt_logging = False

    def close(self):
        LOGGER.debug(f'[{self.segger_id}] devkit close')
        self.in_use = False

        if self.emu is not None:
            self.apiobject.__exit__(None, None, None)

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



def discover_dks(device_list=None):
    # device_list: list of dicts with name, id, family
    if device_list is not None:
        devkits = []
        with SeggerEmulator() as api:
            for device in device_list:
                family = device['family'].upper()
                id = int(device['segger'])
                port = get_serial_port(id, family, api)
                devkits.append(
                    Devkit(id, family, f'dk-{family}-{id}', port))

        return devkits

    with SeggerEmulator() as api:
        ids = api.enum_emu_snr()
        devkits = []
        for id in ids:
            api.connect_to_emu_with_snr(id)
            family = api.read_device_family()
            port = get_serial_port(id, family, api)
            devkits.append(
                Devkit(id, family, f'dk-{family}-{id}', port))
            api.disconnect_from_emu()

    return devkits
