from pynrfjprog import LowLevel
from pynrfjprog import Parameters
from contextlib import contextmanager


# Don't hold a lock on segger API. This might seem counter-intuitive but it'll
# help when making an option to not touch the segger DLL at all in order to keep
# a debugger connected.

@contextmanager
def SeggerEmulator(family='UNKNOWN', id=None):
    """Instantiate the pynrfjprog API and optionally connect to a device."""
    api = LowLevel.API(family)
    api.open()
    if id is not None:
        api.connect_to_emu_with_snr(id)

    yield api

    if id is not None:
        api.disconnect_from_emu()
    api.close()

@contextmanager
def SeggerDevice(family='UNKNOWN', id=None, core='APP'):
    with SeggerEmulator(family, id) as api:
        if core == 'APP':
            cpu = Parameters.CoProcessor.CP_APPLICATION
        elif core == 'NET':
            cpu = Parameters.CoProcessor.CP_NETWORK
        else:
            return None

        print(f'[{id}] connecting...')
        api.select_coprocessor(cpu)
        api.connect_to_device()
        print(f'[{id}] connected')

        yield api

        api.disconnect_from_device()
        print(f'[{id}] disconnected')


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
        print(f'[{self.segger_id}]: start logging')

    def stop_logging(self):
        print(f'[{self.segger_id}]: stop logging')

    def open(self):
        print(f'[{self.segger_id}]: open')
        self.in_use = True
        # Don't try to fetch the port path if supplied
        if self.port is None:
            self.port = get_serial_port(self.segger_id)
        # TODO: make jlink API access disable-able from cli

    def close(self):
        print(f'[{self.segger_id}]: close')
        self.in_use = False

    def available(self):
        return not self.in_use


def get_serial_port(id):
    with SeggerEmulator() as api:
        # Will get the last serial port. This is connected to the APP core
        # on nRF53 DKs.
        return api.enum_emu_com_ports(id)[-1].path

def recover(id, family):
    with SeggerEmulator(family, id) as api:
        print(f'[{id}] recover')
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
