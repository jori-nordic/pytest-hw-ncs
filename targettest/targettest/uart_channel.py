#!/usr/bin/env python3

import serial
import time
import threading
import queue
import logging
from contextlib import contextmanager
from targettest.uart_packet import UARTHeader
from targettest.rpc_packet import RPCPacket, RPCPacketType

LOGGER = logging.getLogger(__name__)

class UARTChannel(threading.Thread):
    DEFAULT_TIMEOUT = 0.001
    DEFAULT_WRITE_TIMEOUT = 5
    MAX_RECV_BYTE_COUNT = 256
    RPC_HEADER_LENGTH = 7

    def __init__(self,
                 port=None,
                 baudrate=1000000,
                 rtscts=True,
                 ignore_timeout=False,
                 rx_handler=None):
        # TODO: remove ?
        # Maye use serial.threaded instead
        # Set daemon to True so the thread does not prevent the test session from exiting.
        threading.Thread.__init__(self, daemon=True)
        self.port = port

        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self._rx_handler = rx_handler # Mandatory, called for each RX packet/unit

        self._ignore_timeout = ignore_timeout
        self._max_recv_byte_count = self.MAX_RECV_BYTE_COUNT

        self._serial = serial.Serial(port=port, baudrate=baudrate, rtscts=rtscts,
                                     timeout=UARTChannel.DEFAULT_TIMEOUT,
                                     write_timeout=UARTChannel.DEFAULT_WRITE_TIMEOUT)

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

            try:
                byte_count += self._serial.write(data)
            except serial.serialutil.SerialTimeoutException:
                # Added for old nRF53 devkits
                # TODO: is that necessary anymore ?
                if self._ignore_timeout:
                    # Assume all data has been sent
                    byte_count += len(data)
                else:
                    raise

            if time.monotonic() - start_time > timeout:
                LOGGER.error(f'Message not sent during required time: {timeout}')
                raise TimeoutError

        return byte_count

    def run(self):
        LOGGER.debug(f'Start RX [{self.port}]')
        # TODO: find more idiomatic way of doing this
        self._stop_rx_flag.clear()

        while not self._stop_rx_flag.isSet():
            recv = self._serial.read(self.MAX_RECV_BYTE_COUNT)

            # TODO: remove ?
            # Supposedly helps with multiple devices
            if recv == b'':
                time.sleep(0.01)
                continue

            LOGGER.debug(f'RX [{self.port}] {recv.hex(" ")}')

            self._rx_handler(recv)

    def stop(self):
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


class UARTRPCChannel(UARTChannel):
    def __init__(self,
                 port=None,
                 baudrate=1000000,
                 rtscts=True,
                 ignore_timeout=False,
                 default_packet_handler=None,
                 group_name=None):

        super().__init__(port, baudrate, rtscts, ignore_timeout, rx_handler=self.handle_rx)

        LOGGER.debug(f'rpc channel init: {port}')
        self.group_name = group_name
        self.remote_gid = 0
        self.default_packet_handler = default_packet_handler
        self.state = UARTDecodingState()

        self.handler_lut = {item.value: {} for item in RPCPacketType}
        self.established = False
        self.events = queue.Queue()

    def handle_rx(self, data: bytes):
        # Prepend the (just received) data with the remains of the last RX
        data = self.state.rx_buf + data
        # Save the current data in case decoding is not complete
        self.state.rx_buf = data

        if self.state.header is None and len(data) >= UARTHeader._size:
            # Attempt to decode the header
            self.state.header = UARTHeader.unpack(data)

        if self.state.header is None:
            # Header failed to decode, eat one byte and try again
            self.state.rx_buf = self.state.rx_buf[1:]
            if len(data) >= UARTHeader._size:
                self.handle_rx(b'')
        else:
            # Header has been decoded
            # Try to decode the packet
            if len(data[self.state.header._size:]) >= self.state.header.length:
                packet = RPCPacket.unpack(data)
                self.handler(packet)

                # Consume the data in the RX buffer
                data = data[self.state.header._size + self.state.header.length:]
                self.state.reset()

                if len(data) > 0:
                    self.handle_rx(data)

    def handler_exists(self, packet: RPCPacket):
        return packet.opcode in self.handler_lut[packet.packet_type]

    def lookup(self, packet: RPCPacket):
        return self.handler_lut[packet.packet_type][packet.opcode]

    def handler(self, packet: RPCPacket):
        LOGGER.debug(f'Handling {packet}')
        # TODO: terminate session on ERR packets
        # Call opcode handler if registered, else call default handler
        if packet.packet_type == RPCPacketType.INIT:
            # Check the INIT packet is for the test system
            assert packet.payload == b'\x00' + self.group_name.encode()
            self.remote_gid = packet.gid_src

            self.clear_buffers()
            self.clear_events()

            # Mark channel as usable and send INIT response
            self.send_init()
            self.established = True
            LOGGER.debug(f'[{self.port}] channel established')
        elif packet.packet_type == RPCPacketType.EVT:
            self.events.put(packet)
        elif packet.packet_type == RPCPacketType.RSP:
            # We just assume only one command can be in-flight at a time
            # Should be enough for testing, can be extended later.
            self.rsp = packet
        elif self.handler_exists(packet):
            self.lookup(packet)(self, packet)
        elif self.default_packet_handler is not None:
            self.default_packet_handler(self, packet)
        else:
            LOGGER.error(f'[{self.port}] unhandled packet {packet}')

    def register_packet(self, packet_type: RPCPacketType, opcode: int, packet_handler):
        self.handler_lut[packet_type][opcode] = packet_handler

    def cmd(self, opcode: int, data: bytes=b'', timeout=5):
        packet = RPCPacket(RPCPacketType.CMD, opcode,
                           src=0, dst=0xFF, gid_src=0, gid_dst=self.remote_gid,
                           payload=data)
        self.rsp = None

        super().send(packet.raw)

        end_time = time.monotonic() + timeout
        while self.rsp is None:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Command timeout')

        return self.rsp

    def clear_events(self):
        while not self.events.empty():
            self.events.get()

    def get_evt(self, opcode=None, timeout=5):
        if opcode is None:
            return self.events.get(timeout=timeout)

        # TODO: add filtering by opcode

        return None

    def send_init(self):
        # Isn't encoded with CBOR
        # Protocol version + RPC group name
        version = b'\x00'
        payload = self.group_name.encode()
        packet = RPCPacket(RPCPacketType.INIT,
                           0, 0, 0xFF, 0, 0xFF,
                           version + payload)

        LOGGER.debug(f'Send handshake {packet}')
        super().send(packet.raw)
