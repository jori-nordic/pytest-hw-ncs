#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
from abc import ABC
from targettest.target_logger.interface import TargetLogger


class TargetDevice(ABC):
    """Interface for a target device.

       That means a board containing an embedded processor. The framework will
       provision the target by flashing and connecting a logger and an RPC
       channel the test can use to trigger actions and receive events.
    """

    def __init__(self, snr, family, name, target_logger_class: TargetLogger):
        # TODO: Set typing for the arguments
        """Do not access hardware in the constructor."""
        self._snr = snr
        self._family = family   # TODO: maybe rename family?
        self._name = name
        self._target_logger_class = target_logger_class

    def __repr__(self):
        return f'{self.name}'

    @property
    def log(self):
        raise NotImplementedError

    @property
    def snr(self):
        return self._snr

    @property
    def family(self):
        return self._family

    @property
    def serial_port(self):
        """Mandatory for devices that support UARTPacketTransport"""
        raise NotImplementedError

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self._name = new_name

    def available(self):
        """True if the device is already used by the framework."""
        raise NotImplementedError

    def halt(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    def open(self, connect_emulator=True):
        """Open the device.

        This can mean many things, one of them being opening a connection to the
        JTAG probe. It can also be used to read information from the target, for
        example the serial port path.
        """
        raise NotImplementedError

    def close(self):
        """Close all resources the open() method has opened."""
        raise NotImplementedError

    def open_log(self):
        """Open a TargetLogger instance to the device.

        The type of that TargetLogger should be of self._target_logger_class.
        """
        raise NotImplementedError

    def close_log(self):
        """Close the TargetLogger instance."""
        raise NotImplementedError

    def append_to_log(self, rx: str):
        """Optional. Append `rx` to the target logs."""
        pass
