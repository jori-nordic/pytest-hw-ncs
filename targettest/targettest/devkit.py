from pynrfjprog import LowLevel, APIError
from pynrfjprog import Parameters
from contextlib import contextmanager
import threading
import time


# Don't hold a lock on segger API. This might seem counter-intuitive but it'll
# help when making an option to not touch the segger DLL at all in order to keep
# a debugger connected.

# TODO: add try-except to all contextmanagers
@contextmanager
def SeggerEmulator(family='UNKNOWN', id=None, core=None):
    """Instantiate the pynrfjprog API and optionally connect to a device."""
    api = LowLevel.API(family)
    api.open()
    if id is not None:
        api.connect_to_emu_with_snr(id)

    if core is not None:
        cpu = coproc[core]
        api.select_coprocessor(cpu)

    yield api

    if id is not None:
        api.disconnect_from_emu()
    api.close()

coproc = {'APP': Parameters.CoProcessor.CP_APPLICATION,
          'NET': Parameters.CoProcessor.CP_NETWORK}

def select_core(api, core):
    cpu = coproc[core]
    print(f'[{cpu.name}] select core')
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

        print(f'[{id}] connected')

        yield api

        api.disconnect_from_device()
        print(f'[{id}] disconnected')


class RTTLogger(threading.Thread):
    def __init__(self, emu, handler):
        threading.Thread.__init__(self, daemon=True)
        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self.ready = False
        self.handler = handler
        self.emu = emu

    def run(self):
        print(f'RTT start')
        # TODO: find more idiomatic way of doing this
        self._stop_rx_flag.clear()

        print(f'RTT search...')
        self.emu.rtt_start()
        while not self.emu.rtt_is_control_block_found():
            time.sleep(.1)

        self.ready = True

        print(f'RTT opened')
        while not self._stop_rx_flag.isSet():
            recv = self.emu.rtt_read(0, 100)
            if len(recv) > 0:
                # print(f'RTT: {recv}')
                self.handler(recv)

            # Batch RTT reads
            time.sleep(.01)
            # TODO: do something with that data

        print(f'RTT stop')
        self.emu.rtt_stop()

    def open(self):
        self.start()

    def close(self):
        self._stop_rx_flag.set()
        self.join()


class Devkit:
    def __init__(self, id, family, name, port=None, open_emu=True):
        self.open_emu = open_emu
        self.emu = None
        self.segger_id = id
        self.family = family
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
            return

        self.rtt = RTTLogger(self.emu, self.log_handler)
        self.rtt.start()
        while not self.rtt.ready:
            time.sleep(.1)
        print(f'[{self.segger_id}]: logging started')

    def stop_logging(self):
        if self.emu is None:
            return

        try:
            self.rtt.close()
        finally:
            print(f'[{self.segger_id}]: logging stopped')
            print(self.log)

    def open(self):
        print(f'[{self.segger_id}]: open')
        self.in_use = True

        # Don't try to fetch the port path if supplied
        if self.port is None:
            self.port = get_serial_port(self.segger_id)

        if self.open_emu:
            self.apiobject = SeggerDevice(self.family, self.segger_id)
            self.emu = self.apiobject.__enter__()

    def close(self):
        print(f'[{self.segger_id}]: close')
        self.in_use = False

        if self.emu is not None:
            self.apiobject.__exit__(None, None, None)

    def available(self):
        return not self.in_use

    def reset(self):
        if self.emu is None:
            print(f'[{segger_id}]: skipping reset')
            return
        reset(self.segger_id, self.family, self.emu)

    def halt(self):
        if self.emu is None:
            print(f'[{segger_id}]: skipping halt')
            return
        halt(self.segger_id, self.family, self.emu)


def get_serial_port(id):
    with SeggerEmulator() as api:
        # Will get the last serial port. This is connected to the APP core
        # on nRF53 DKs.
        return api.enum_emu_com_ports(id)[-1].path

def flash(id, family, hex_path, core='APP', reset=True):
    with SeggerDevice(family, id, core) as cpu:
        print(f'[{id}] [{family}-{core}] Flashing with {str(hex_path)}')
        # Erase the target's flash
        cpu.erase_file(hex_path)

        # Flash & verify
        cpu.program_file(hex_path)
        cpu.verify_file(hex_path)

def reset(id, family, emu=None):
    print(f'[{id}] reset')
    if emu is not None:
        emu.debug_reset()
    else:
        # TODO: check if this doesn't disturb Ozone
        with SeggerDevice(family, id) as emu:
            emu.debug_reset()
            # Other ways to reset the device:
            # emu.sys_reset()
            # emu.hard_reset()
            # emu.pin_reset()

def halt(id, family, emu=None):
    print(f'[{id}] halt')
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
