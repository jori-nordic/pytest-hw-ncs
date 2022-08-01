#!/usr/bin/env python3

import serial
import time
import threading
from targettest.uart_packet import UARTHeader
from targettest.rpc_packet import RPCPacket, RPCPacketType


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

        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self._rx_handler = rx_handler # Mandatory, called for each RX packet/unit

        self._ignore_timeout = ignore_timeout
        self._max_recv_byte_count = self.MAX_RECV_BYTE_COUNT

        self._serial = serial.Serial(port=port, baudrate=baudrate, rtscts=rtscts,
                                     timeout=UARTChannel.DEFAULT_TIMEOUT,
                                     write_timeout=UARTChannel.DEFAULT_WRITE_TIMEOUT)

    def send(self, data, timeout=15):
        data = bytearray(data)

        byte_count = 0
        start_time = time.monotonic()

        print(f'TX: {data.hex(" ")}')
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
                print(f'Message not sent during required time: {timeout}')
                raise TimeoutError

        return byte_count

    def run(self):
        # TODO: find more idiomatic way of doing this
        self._stop_rx_flag.clear()

        while not self._stop_rx_flag.isSet():
            recv = self._serial.read(self.MAX_RECV_BYTE_COUNT)

            # # TODO: remove ?
            # if not isinstance(recv, bytearray):
            #     print(f'serial.read returned {type(recv)}:{recv}')
            #     continue

            # TODO: remove ?
            # Supposed to help with multiple devices
            if recv == b'':
                time.sleep(0.05)
                continue

            print(f'RX: {recv.hex(" ")}')

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
        self.building = False


class UARTRPCChannel(UARTChannel):
    def __init__(self,
                 port=None,
                 baudrate=1000000,
                 rtscts=True,
                 ignore_timeout=False,
                 default_packet_handler=None):

        super().__init__(port, baudrate, rtscts, ignore_timeout, rx_handler=self.handle_rx)

        self.default_packet_handler = default_packet_handler
        self.state = UARTDecodingState()
        self.handler_lut = {item.value: {} for item in RPCPacketType}

    def handle_rx(self, data: bytes):
        # Prepend the (just received) data with the remains of the last RX
        data = self.state.rx_buf + data

        if not self.state.building and len(data) >= UARTHeader._size:
            # Attempt to decode the header
            self.state.header = UARTHeader.unpack(data)
        else:
            self.state.building = False

        if self.state.header is not None:
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
        # Call opcode handler if registered, else call default handler
        if self.handler_exists(packet):
            self.lookup(packet)(packet)
        else:
            self.default_packet_handler(packet)

    def register_packet(self, packet_type: RPCPacketType, opcode: int, packet_handler):
        self.handler_lut[packet_type][opcode] = packet_handler
