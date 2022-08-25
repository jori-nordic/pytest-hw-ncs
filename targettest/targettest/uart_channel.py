import serial
import time
import threading
import logging
from contextlib import contextmanager
from targettest.uart_packet import UARTHeader
from targettest.rpc_packet import RPCPacket
from targettest.abstract_transport import PacketTransport

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
                 rx_handler=None):
        # TODO: Maybe serial.threaded could be used
        threading.Thread.__init__(self, daemon=True)
        self.port = port

        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self._rx_handler = rx_handler # Mandatory, called for each RX packet/unit

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

            byte_count += self._serial.write(data)

            if time.monotonic() - start_time > timeout:
                LOGGER.error(f'Message not sent during required time: {timeout}')
                raise TimeoutError

        return byte_count

    def run(self):
        LOGGER.debug(f'Start RX [{self.port}]')
        self._stop_rx_flag.clear()

        while not self._stop_rx_flag.isSet():
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


class UARTRPCChannel(PacketTransport):
    def __init__(self,
                 port,
                 baudrate=1000000,
                 rtscts=True,
                 packet_handler=None):

        self.uart = UARTChannel(port, baudrate, rtscts, rx_handler=self.handle_rx)
        self.state = UARTDecodingState()

        LOGGER.debug(f'UART packet channel init: {port}')

    def __repr__(self):
        return f'{self.uart.port}'

    def open(self):
        self.uart.open()

    def close(self):
        self.uart.close()

    def send(self, data, timeout=15):
        self.uart.send(data, timeout)

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
                packet = RPCPacket.unpack(data)
                self.packet_handler(packet)

                # Consume the data in the RX buffer
                data = data[self.state.header._size + self.state.header.length:]
                self.state.reset()

                if len(data) > 0:
                    self.handle_rx(data)

