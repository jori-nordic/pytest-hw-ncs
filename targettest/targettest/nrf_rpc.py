#!/usr/bin/env python3

# Scratchpad for nRF RPC UART transport

import time
import threading
import serial
import cbor2

class UARTRPC(threading.Thread):
    DEFAULT_TIMEOUT = 0.001
    DEFAULT_WRITE_TIMEOUT = 5
    MAX_RECV_BYTE_COUNT = 256
    RPC_HEADER_LENGTH = 7

    def __init__(self,
                 port=None,
                 baudrate=1000000,
                 rtscts=True,
                 ignore_timeout=False):
        # TODO: remove ?
        # Maye use serial.threaded instead
        # Set daemon to True so the thread does not prevent the test session from exiting.
        threading.Thread.__init__(self, daemon=True)
        self._stop_rx_flag = threading.Event()

        self.ignore_timeout = ignore_timeout
        self._max_recv_byte_count = self.MAX_RECV_BYTE_COUNT

        self._rx_buf = b''
        self._packet_len = 0
        self._building_header = True

        self._payload_handler = None

        self._serial = serial.Serial(port=port, baudrate=baudrate, rtscts=rtscts,
                                     timeout=UARTRPC.DEFAULT_TIMEOUT,
                                     write_timeout=UARTRPC.DEFAULT_WRITE_TIMEOUT)

    def send(self, data, timeout=15):
        data = bytearray(data)

        byte_count = 0
        start_time = time.monotonic()

        while data:
            data = data[byte_count:]

            try:
                byte_count += self._serial.write(data)
            except serial.serialutil.SerialTimeoutException:
                # Added for old nRF53 devkits
                # TODO: is that necessary anymore ?
                if self.ignore_timeout:
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

            self.handle_rx(recv)

    def stop(self):
        self._stop_rx_flag.set()
        self.join()
        self._serial.close()

    def handle_rx(self, data):
        if self._building_header:
            if len(self._rx_buf) == 0 and data[0] != 85:
                return

            self._rx_buf += data

            if len(self._rx_buf) >= self.RPC_HEADER_LENGTH:
                packet_len = decode_uart_header(data)
                if packet_len == 0:
                    return
                else:
                    self._building_header = False
                    self._packet_len = packet_len

                    # Only keep the payload
                    self._rx_buf = b''
                    data = data[self.RPC_HEADER_LENGTH:]

        # Past this point, we want to receive the payload
        if len(data) == 0:
            return

        self._rx_buf = data[:self._packet_len]

        if len(self._rx_buf) == self._packet_len:
            self._payload_handler(self._rx_buf)
            self._rx_buf = data[self._packet_len:]
            self._building_header = True

def decode_uart_header(data):
    if data[:4] != b'UART':
        return 0

    length = data[4] + (data[5] << 8)

    # TODO: implement CRC
    crc = data[6]

    return length

def handle_payload(payload):
    if payload[0] == 0x04:
        handshake()

    print(f'Payload {payload.hex(" ")}')

def handshake():
    # len lsb, len msb, crc
    uart_header = b'UART' + bytearray.fromhex('18 00 00')

    # Protocol version + RPC group name
    header = bytearray.fromhex('04 00 ff 00 ff')
    version = b'\x00'
    payload = b'nrf_sample_entropy'

    packet = bytearray(uart_header + header + version + payload)
    print('Send handshake')
    rpc.send(packet)


rpc = UARTRPC(port='/dev/ttyACM6')
rpc._payload_handler = handle_payload
rpc.start()

# Send RPC handshake
# Doesn't use CBOR
handshake_payload = b'nrf_sample_entropy'
rpc.send(handshake_payload)

# Don't exit immediately
rpc.join()
