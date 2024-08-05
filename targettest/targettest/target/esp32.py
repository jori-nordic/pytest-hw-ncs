#
# Copyright (c) 2024 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import usb.core
import usb.util
import logging
import os
import subprocess
from targettest.target_logger.rpc import RPCLogger
from targettest.target_logger.interface import TargetLogger
from targettest.target.interface import TargetDevice


USB_VID_ESPRESSIF = 0x303a
LOGGER = logging.getLogger(__name__)

def list_connected_esp32_devices():
    """List all ESP32 devices connected over USB."""
    usb_devices = usb.core.find(find_all=True, idVendor=USB_VID_ESPRESSIF)
    devkits = []

    for dev in usb_devices:
        d = {'snr': dev.serial_number,
             'family': 'esp32c3'}
        devkits.append(d)

    LOGGER.debug(f'Found ESP devices: {devkits}')

    return devkits

def get_fw_build_dir(root_dir, test_path, board, network_core=None):
    rel_suite_path = test_path.parent.relative_to(root_dir)

    # Assume zephyr sysbuild
    build_dir = root_dir / 'build' / rel_suite_path / board / 'fw'

    fw_hex = build_dir / 'zephyr' / 'zephyr.hex'

    assert fw_hex.exists(), f"Missing firmware: {fw_hex}"

    return build_dir

def esp32_magic_usb_reset(serial_path):
    """Perform a song and dance to reset ESP32 through USB."""
    s = serial.Serial()
    s.baudrate = 115200
    s.port = serial_path

    s.dtr = True
    s.rts = False

    s.dtr = False
    s.rts = True

    MINIMAL_EN_TRUE_DELAY = 0.005
    time.sleep(MINIMAL_EN_TRUE_DELAY)

    s.rts = False


class ESP32Devkit(TargetDevice):
    """Interface ESP32C3 devkit.

       This has been tested with a 01space esp32c3 board with display.
    """

    def __init__(self, snr, family, name, target_logger_class: TargetLogger):
        self._snr = str(snr)
        self._family = family   # TODO: maybe rename family?
        self._name = name
        self._target_logger_class = target_logger_class

        self._target_logger = None
        self._log = ''

        super().__init__(snr, family.upper(), name, target_logger_class)

    def __repr__(self):
        return f'{self.name}'

    @property
    def log(self):
        return self._log

    @property
    def snr(self):
        return self._snr

    @property
    def family(self):
        return self._family

    @property
    def serial_port(self):
        by_id_path = '/dev/serial/by-id'
        if not os.path.exists(by_id_path):
            raise FileNotFoundError(f"{by_id_path} does not exist")

        for device in os.listdir(by_id_path):
            if self.snr in device:
                return os.path.join(by_id_path, device)

        raise Exception("Unable to find serial port for {self.snr}")

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self._name = new_name

    def available(self):
        return not self._in_use

    def flash(self, root_path, test_path, board_name):
        """Flash the device with the appropriate .hex file."""
        fw_dir = get_fw_build_dir(root_path, test_path, board_name)
        # flash_using_west(self.serial_port)

        command = ['west', 'flash', '--esp-device', self.serial_port]
        try:
            result = subprocess.run(command,
                                    cwd=fw_dir,
                                    check=True,
                                    capture_output=True,
                                    text=True)
        except subprocess.CalledProcessError as e:
            LOGGER.error(f'Failed to run `west flash`: {e}')
            LOGGER.error(f'Error output: {e.stderr}')

    def halt(self):
        # N/A
        pass

    def boot(self):
        # such acronyms, very wow
        LOGGER.debug("Resetting through USB-CDC RTS/CTS")
        esp32_magic_usb_reset(self.serial_port)

    def reset(self):
        # N/A
        pass

    def open(self, connect_emulator=True):
        # N/A
        pass

    def close(self):
        # N/A
        pass

    def _log_handler(self, rx: str):
        self._log += rx

    @property
    def log(self):
        return self._log

    def open_log(self):
        self._log = ''

        if self._target_logger_class is RPCLogger:
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

    def append_to_log(self, rx: str):
        self._log_handler(rx)
