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
        print(f'[{id}] connecting...')

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
    def __init__(self, id, family):
        threading.Thread.__init__(self, daemon=True)
        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self.segger_id = id
        self.family = family

    def run(self):
        print(f'[{self.segger_id}] RTT start')
        # TODO: find more idiomatic way of doing this
        self._stop_rx_flag.clear()

        print(f'[{self.segger_id}] RTT search...')
        self.api.rtt_start()
        while not self.api.rtt_is_control_block_found():
            time.sleep(.01)

        print(f'[{self.segger_id}] RTT opened')
        while not self._stop_rx_flag.isSet():
            recv = self.api.rtt_read(0, 1)
            print(f'[{self.segger_id}] RTT: {recv}')

            # Batch RTT reads
            time.sleep(.01)
            # TODO: do something with that data

        print(f'[{self.segger_id}] RTT stop')
        self.api.rtt_stop()

    def open(self):
        self.start()

    def close(self):
        self._stop_rx_flag.set()
        self.join()


class Devkit:
    def __init__(self, id, family, name, port=None):
        self.segger_id = id
        self.family = family
        self.port = port

        self.name = name
        self.in_use = False

        # This will be filled with the RTT logs
        self.log = b''

    def start_logging(self):
        return
        self.rtt = RTTLogger(self.segger_id, self.family)
        self.rtt.start()
        print(f'[{self.segger_id}]: start logging')

    def stop_logging(self):
        return
        self.rtt.close()
        print(f'[{self.segger_id}]: stop logging')

    def open(self):
        print(f'[{self.segger_id}]: open')
        self.in_use = True
        # Don't try to fetch the port path if supplied
        if self.port is None:
            self.port = get_serial_port(self.segger_id)
        # TODO: make jlink API access disable-able from cli
        return
        self.api = LowLevel.API(self.family)
        self.api.open()
        self.api.connect_to_emu_with_snr(self.segger_id)
        self.api.select_coprocessor(coproc['APP'])
        self.api.connect_to_device()

    def close(self):
        print(f'[{self.segger_id}]: close')
        self.in_use = False
        return
        if self.api is not None:
            self.api.disconnect_from_device()
            self.api.disconnect_from_emu()
            self.api.close()

    def available(self):
        return not self.in_use

    def reset(self):
        reset(self.segger_id, self.family)
        return
        print(f'[{self.segger_id}] self-reset')
        self.api.debug_reset()
        print(f'[{self.segger_id}] self-reset ok')

    def halt(self):
        halt(self.segger_id, self.family)


def get_serial_port(id):
    with SeggerEmulator() as api:
        # Will get the last serial port. This is connected to the APP core
        # on nRF53 DKs.
        return api.enum_emu_com_ports(id)[-1].path

def recover(id, family):
    with SeggerEmulator(family, id) as api:
        print(f'[{id}] recover')
        if family != 'NRF52':
            select_core(api, 'NET')
            api.recover()

        select_core(api, 'APP')
        api.recover()

def flash(id, family, hex_path, core='APP', reset=True):
    with SeggerDevice(family, id, core) as cpu:
        print(f'[{id}] [{family}-{core}] Flashing with {str(hex_path)}')
        # Erase the target's flash
        cpu.erase_file(hex_path)

        # Flash & verify
        cpu.program_file(hex_path)
        cpu.verify_file(hex_path)

def reset(id, family):
    with SeggerDevice(family, id) as api:
        print(f'[{id}] reset')
        api.debug_reset()
        # Other ways to reset the device:
        # api.sys_reset()
        # api.hard_reset()
        # api.pin_reset()

def halt(id, family):
    with SeggerDevice(family, id) as api:
        print(f'[{id}] halt')
        api.halt()

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
