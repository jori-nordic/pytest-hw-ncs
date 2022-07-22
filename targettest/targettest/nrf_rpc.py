#!/usr/bin/env python3

# Scratchpad for nRF RPC UART transport

import enum
import struct
import time
import threading
import serial
import cbor2


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
        # print(f'header unpack: buf {packet}')
        try:
            (header, length, crc) = struct.unpack(cls._format, packet)
            if header == cls._header:
                # print('header unpack success')
                return cls(length, crc)

        except struct.error:
            print("Struct error")
            pass

        print('header unpack failure')
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
        # print(f'UARTPacket unpack from {packet}')
        # Called on the whole buffer, containing the header too
        header = UARTHeader.unpack(packet)
        packet = packet[header._size:] # Remove the header
        packet = packet[:header.length] # Remove anything after the advertised length
        # print(f'header {header} raw {packet}')

        if len(packet) < header.length:
            # TODO raise EOFError ?
            print('Packet not complete')
            return None
        else:
            return cls(packet)


class RPCPacketType(enum.IntEnum):
    EVT = 0
    RSP = 1
    ACK = 2
    ERR = 3
    INIT = 4
    CMD = 0x80


class RPCPacket():
    _format = '<BBBBB'
    _size = struct.calcsize(_format)

    # Header: SRC + type, ID, DST, GID SRC, GID DST, CBOR u32 (primary)
    def __init__(self,
                 packet_type: RPCPacketType,
                 opcode, src, dst, gid_src, gid_dst,
                 payload: bytes):
        self.packet_type = RPCPacketType(packet_type)
        self.src = src
        self.dst = dst
        self.gid_src = gid_src
        self.gid_dst = gid_dst
        self.payload = payload
        self.header = struct.pack(self._format,
                                  packet_type | src,
                                  opcode,
                                  dst,
                                  gid_src,
                                  gid_dst)

        # Build whole packet
        self.packet = UARTPacket(self.header + self.payload)
        self.raw = self.packet.raw

    def __repr__(self):
        return f'[{self.packet_type.name}] {self.packet}'

    @classmethod
    def unpack(cls, packet: bytes):
        payload = UARTPacket.unpack(packet).payload
        raw_header = payload[:cls._size]
        print(f'RPCPacket payload {payload} header {raw_header}')
        (packet_type,
         opcode,
         dst,
         gid_src,
         gid_dst) = struct.unpack(cls._format, raw_header)

        if packet_type & RPCPacketType.CMD:
            src = packet_type & 0x7F
            packet_type = RPCPacketType.CMD
        else:
            src = 0

        return RPCPacket(packet_type, opcode, src, dst, gid_src, gid_dst, payload)


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
        self._building = False
        self._header = None

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
        # Prepend the (just received) data with the remains of the last RX
        data = self._rx_buf + data

        if not self._building and len(data) >= UARTHeader._size:
            # Attempt to decode the header
            self._header = UARTHeader.unpack(data)
        else:
            self._building = False

        if self._header is not None:
            # Header has been decoded
            # Try to decode the packet
            if len(data[self._header._size:]) >= self._header.length:
                packet = RPCPacket.unpack(data)
                # Process data
                self._payload_handler(packet)
                # Consume the data in the RX buffer
                data = data[self._header._size + self._header.length + 1:]
                # Reset state
                self._header = None
                self._rx_buf = b''

        self._rx_buf += data

        # TODO: maybe re-trigger handle_rxr

def handle_payload(payload: RPCPacket):
    # Here we should dispatch based on the packet type
    # and a LUT of ID-associated functions
    if payload.packet_type == RPCPacketType.INIT:
        handshake()

    print(f'Payload handle {payload}')

def handshake():
    # Doesn't use CBOR
    # Doesn't have the workaround u32 val in the middle

    # Protocol version + RPC group name
    version = b'\x00'
    payload = b'nrf_sample_entropy'
    packet = RPCPacket(RPCPacketType.INIT,
                       0, 0, 0xFF, 0, 0xFF,
                       version + payload)

    print(f'Send handshake {packet}')
    rpc.send(packet.raw)


rpc = UARTRPC(port='/dev/ttyACM2')
rpc._payload_handler = handle_payload
rpc.start()

# Receive init command
# CBOR, has w/a u32

# Don't exit immediately
rpc.join()
