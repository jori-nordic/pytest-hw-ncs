import threading
import time
import logging
from contextlib import contextmanager
from pynrfjprog import LowLevel, APIError
from pynrfjprog import Parameters

LOGGER = logging.getLogger(__name__)

# Don't hold a lock on segger API. This might seem counter-intuitive but it'll
# help when making an option to not touch the segger DLL at all in order to keep
# a debugger connected.

# TODO: add try-except to all contextmanagers
@contextmanager
def SeggerEmulator(family='UNKNOWN', id=None, core=None):
    """Instantiate the pynrfjprog API and optionally connect to a device."""
    try:
        api = LowLevel.API(family)
        api.open()
        if id is not None:
            api.connect_to_emu_with_snr(id)

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
        # TODO: find more idiomatic way of doing this
        self._stop_rx_flag.clear()

        LOGGER.debug(f'RTT search...')
        self.emu.rtt_start()
        while not (self.emu.rtt_is_control_block_found() or
                   self._stop_rx_flag.isSet()):
            time.sleep(.1)

        self.ready = True

        LOGGER.debug(f'RTT opened')
        while not self._stop_rx_flag.isSet():
            recv = self.emu.rtt_read(0, 100)
            if len(recv) > 0:
                self.handler(recv)

            # Batch RTT reads
            time.sleep(.01)
            # TODO: do something with that data

        LOGGER.debug(f'RTT stop')
        self.emu.rtt_stop()

    def open(self):
        self.start()

    def close(self):
        self._stop_rx_flag.set()
        self.join()


class Devkit:
    def __init__(self, id, family, name, port=None):
        self.emu = None
        self.segger_id = int(id)
        self.family = family.upper()
        self.port = port

        self.name = name
        self.in_use = False

        self.log = ''

    def __repr__(self):
        return f'[{self.segger_id}] {self.port}'

    def log_handler(self, rx: str):
        self.log += rx

    def start_logging(self):
        if self.emu is None:
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
        if self.emu is None:
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


def get_serial_port(id):
    with SeggerEmulator() as api:
        # Will get the last serial port. This is connected to the APP core
        # on nRF53 DKs.
        return api.enum_emu_com_ports(id)[-1].path

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
        # TODO: check if this doesn't disturb Ozone
        with SeggerDevice(family, id) as emu:
            LOGGER.info(f'[{id}] reset')
            # emu.debug_reset()
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

def discover_dks():
    with SeggerEmulator() as api:
        ids = api.enum_emu_snr()
        devkits = []
        for id in ids:
            api.connect_to_emu_with_snr(id)
            family = api.read_device_family()
            port = api.enum_emu_com_ports(id)[-1].path
            devkits.append(
                Devkit(id, family, f'dk-{family}-{id}', port))
            api.disconnect_from_emu()

    return devkits
