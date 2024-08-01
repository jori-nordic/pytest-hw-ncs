#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import serial
import time
import threading
import logging
import struct
from contextlib import contextmanager
from targettest.packet_transport.interface import PacketTransport

LOGGER = logging.getLogger(__name__)


class UARTHeader():
    _header = b'UART'
    _format = '<4sHB'
    _size = struct.calcsize(_format)

    def __init__(self, length: int, crc: int):
        self.length = length
        self.crc = crc
        self.raw = struct.pack(self._format, self._header, self.length, self.crc)

    @classmethod
    def unpack(cls, packet: bytes):
        packet = packet[:cls._size]
        # LOGGER.debug(f'try-unpack: {packet.hex(" ")}')
        try:
            (header, length, crc) = struct.unpack(cls._format, packet)
            if header == cls._header:
                return cls(length, crc)

        except struct.error:
            LOGGER.info("Struct decoding error")
            pass

        # LOGGER.debug(f'invalid header ({packet.hex(" ")})')
        return None

    @classmethod
    def calc_crc(cls, packet: bytes):
        return 0

    def __repr__(self):
        return f'len {self.length} crc {self.crc} raw {self.raw}'


class UARTPacket():
    def __init__(self, payload=b''):
        self.length = len(payload)
        self.header = UARTHeader(self.length, UARTHeader.calc_crc(payload))
        self.payload = payload
        self.raw = self.header.raw + payload

    def __repr__(self):
        return f'UARTPacket: header ({self.header}) payload {self.payload}'

    @classmethod
    def unpack(cls, packet: bytes):
        # Called on the whole buffer, containing the header too
        header = UARTHeader.unpack(packet)
        packet = packet[header._size:] # Remove the header
        packet = packet[:header.length] # Remove anything after the advertised length
        LOGGER.debug(f'header {header} raw {packet}')

        if len(packet) < header.length:
            LOGGER.warning('Packet not complete')
            return None
        else:
            return cls(packet)


class UARTTransport(threading.Thread):
    DEFAULT_TIMEOUT = 0.001
    DEFAULT_WRITE_TIMEOUT = 5
    MAX_RECV_BYTE_COUNT = 256
    RPC_HEADER_LENGTH = 7

    def __init__(self,
                 port=None,
                 baudrate=1000000,
                 rtscts=True,
                 rx_handler=None):
        # TODO: Maybe serial.threaded could be used
        threading.Thread.__init__(self, daemon=True)
        self.port = port

        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self._rx_handler = rx_handler # Mandatory, called for each RX packet/unit

        self._max_recv_byte_count = self.MAX_RECV_BYTE_COUNT

        self._serial = serial.Serial(port=port, baudrate=baudrate, rtscts=rtscts,
                                     timeout=UARTTransport.DEFAULT_TIMEOUT,
                                     write_timeout=UARTTransport.DEFAULT_WRITE_TIMEOUT)

    def clear_buffers(self):
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def send(self, data, timeout=15):
        data = bytearray(data)

        byte_count = 0
        start_time = time.monotonic()

        LOGGER.debug(f'TX [{self.port}] {data.hex(" ")}')
        while data:
            data = data[byte_count:]

            byte_count += self._serial.write(data)

            if time.monotonic() - start_time > timeout:
                LOGGER.error(f'Message not sent during required time: {timeout}')
                raise TimeoutError

        return byte_count

    def run(self):
        LOGGER.debug(f'Start RX [{self.port}]')
        self._stop_rx_flag.clear()

        while not self._stop_rx_flag.is_set():
            recv = self._serial.read(self.MAX_RECV_BYTE_COUNT)

            # Yield to other threads
            if recv == b'':
                time.sleep(0.0001)
                continue

            LOGGER.debug(f'RX [{self.port}] {recv.hex(" ")}')

            self._rx_handler(recv)

    def open(self):
        self.start()

    def close(self):
        self._stop_rx_flag.set()
        self.join()
        self._serial.close()


class UARTDecodingState():
    def __init__(self):
        self.reset()

    def reset(self):
        self.rx_buf = b''
        self.header = None

    def __repr__(self):
        return f'{self.header} buf {self.rx_buf.hex(" ")}'


class UARTPacketTransport(PacketTransport):
    def __init__(self,
                 port,
                 baudrate=1000000,
                 rtscts=True):

        self.uart = UARTTransport(port, baudrate, rtscts, rx_handler=self.handle_rx)
        self.state = UARTDecodingState()
        self.packet_handler = None

        LOGGER.debug(f'UART packet channel init: {port}')

    def __repr__(self):
        return f'{self.uart.port}'

    def open(self, packet_handler):
        self.packet_handler = packet_handler
        self.uart.open()

    def close(self):
        self.uart.close()

    def send(self, data: bytes, timeout=15):
        self.uart.send(UARTPacket(data).raw, timeout)

    def handle_rx(self, data: bytes):
        # Prepend the (just received) data with the remains of the last RX
        data = self.state.rx_buf + data
        # Save the current data in case decoding is not complete
        self.state.rx_buf = data

        if len(data) >= UARTHeader._size:
            if self.state.header is None:
                # Attempt to decode the header
                self.state.header = UARTHeader.unpack(data)

            if self.state.header is None:
                # Header failed to decode, eat one byte and try again
                self.state.rx_buf = self.state.rx_buf[1:]
                if len(data) >= UARTHeader._size:
                    self.handle_rx(b'')

        if self.state.header is not None:
            # Header has been decoded
            # Try to decode the packet
            if len(data[self.state.header._size:]) >= self.state.header.length:
                try:
                    payload = UARTPacket.unpack(data).payload
                except Exception as e:
                    LOGGER.error(f'Failed to decode uart packet: {data}')
                    raise e

                self.packet_handler(payload)

                # Consume the data in the RX buffer
                data = data[self.state.header._size + self.state.header.length:]
                self.state.reset()

                if len(data) > 0:
                    self.handle_rx(data)

