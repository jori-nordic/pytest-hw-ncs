from pynrfjprog import API
from contextlib import contextmanager


# Don't hold a lock on segger API, in order to allow running tests with a debugger.

@contextmanager
def SeggerApi(family='UNKNOWN', id=None):
    """Instantiate the pynrfjprog API and optionally connect to a device."""
    api = API.API(family)
    api.open()
    if id is not None:
        api.connect_to_emu_with_snr(id)

    yield api

    if id is not None:
        api.disconnect_from_emu()
    api.close()


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


devkits = []
def populate_dks():
    with SeggerApi() as api:
        ids = api.enum_emu_snr()
        devices = []
        for id in ids:
            print(f'connecting to {id}')
            api.connect_to_emu_with_snr(id)
            family = api.read_device_family()
            port = api.enum_emu_com_ports(id)[-1].path
            devkits.append(
                Devkit(id, family, f'dk-{family}-{id}', port))
            api.disconnect_from_emu()

        print(f'Available devices: {devkits}')


def get_available_dk(family):
    for dev in devkits:
        if dev.available() and dev.family == family:
            return dev
    return None

def get_serial_port(id):
    with SeggerApi() as api:
        # Will get the last serial port. This is connected to the APP core
        # on nRF53 DKs.
        return api.enum_emu_com_ports(id)[-1].path

def flash(id, family, hex_path, recover=True, reset=True):
    print(f'Flashing {id} [{family}] with {str(hex_path)}')
    with SeggerApi(family, id) as api:
        # TODO: do I need to select the coprocessor here?

        # Erase the target's flash
        if recover:
            api.recover()
        else:
            api.erase_file(hex_path)

        # Flash & verify
        api.program_file(hex_path)
        api.verify_file(hex_path)

def reset(id, family):
    with SeggerApi(family, id) as api:
        api.debug_reset()
        # Other ways to reset the device:
        # api.sys_reset()
        # api.hard_reset()
        # api.pin_reset()
