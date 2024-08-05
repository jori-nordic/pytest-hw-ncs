#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import time
import enum
import struct
import queue
import logging
from targettest.packet_transport.interface import PacketTransport

LOGGER = logging.getLogger(__name__)


class RPCPacketType(enum.IntEnum):
    INIT = 0
    INITRSP = enum.auto()
    CMD = enum.auto()
    RSP = enum.auto()
    EVT = enum.auto()
    ACK = enum.auto()
    ERR = enum.auto()
    LOG = enum.auto()


def _encode(data: dict):
    encoded = b''
    for key, value in data.items():
        if not isinstance(value[1], bytes):
            encoded += struct.pack(value[0], value[1])
        else:
            encoded += value[1]

    return encoded

def _decode(schema: dict, buf: bytearray):
    result = {}
    offset = 0
    for key, value in schema.items():
        result[key] = (value[0], struct.unpack_from(value[0], buf, offset)[0])
        offset += struct.calcsize(value[0])

    return result


class RPCPacket():
    _format = '<BH'
    _size = struct.calcsize(_format)

    # Header: type + opcode
    def __init__(self,
                 packet_type: RPCPacketType,
                 opcode,
                 payload: bytes or dict = None):
        self.packet_type = RPCPacketType(packet_type)
        self.opcode = opcode
        self.header = struct.pack(self._format,
                                  packet_type,
                                  opcode)

        if isinstance(payload, bytes):
            self.payload = payload
        elif isinstance(payload, dict):
            self.payload = _encode(payload)
        else:
            raise Exception("Provide payload as either a dict or bytes")

        # Build whole packet. Transport-specific headers are defined and
        # prepended (if necessary) by the transports themselves.
        self.serialized = self.header + self.payload

    def __repr__(self):
        return '{} {:02x} LEN {} DATA {}'.format(
            self.packet_type.name,
            self.opcode,
            len(self.payload),
            self.payload.hex(' ')
        )

    @classmethod
    def unpack(cls, payload: bytes):
        # Separate RPC cmd/evt payload from RPC header
        rpc_header = payload[:cls._size]
        payload = payload[cls._size:]

        packet_type, opcode = struct.unpack(cls._format, rpc_header)

        return RPCPacket(packet_type, opcode, payload)


    def decode(self, schema: dict):
        return _decode(schema, self.payload)


class RPCChannel():
    def __init__(self, transport: PacketTransport, default_packet_handler=None, log_handler=None):
        # A valid transport has to be initialized first
        self.transport = transport
        self.device_log_handler = log_handler

        self.established = False

        # Handlers
        self.events = queue.Queue()
        self.default_packet_handler = default_packet_handler
        self.handler_lut = {item.value: {} for item in RPCPacketType}

    def handler_exists(self, packet: RPCPacket):
        return packet.opcode in self.handler_lut[packet.packet_type]

    def lookup(self, packet: RPCPacket):
        return self.handler_lut[packet.packet_type][packet.opcode]

    def handler(self, payload: bytes):
        packet = RPCPacket.unpack(payload)

        LOGGER.debug(f'Handling {packet}')
        # Call opcode handler if registered, else call default handler
        if packet.packet_type == RPCPacketType.INIT:
            self.transport.clear_buffers()
            self.clear_events()

            self.send_init()

        elif packet.packet_type == RPCPacketType.INITRSP:
            self.transport.clear_buffers()
            self.clear_events()

            self.send_initrsp()

            self.established = True
            LOGGER.debug(f'[{self.transport}] channel established')

        elif packet.packet_type == RPCPacketType.EVT:
            self.events.put(packet)
            self.ack(packet.opcode)

        elif packet.packet_type == RPCPacketType.ACK:
            (_, sent_opcode) = self._ack
            assert packet.opcode == sent_opcode
            self._ack = (packet, packet.opcode)

        elif packet.packet_type == RPCPacketType.RSP:
            # We just assume only one command can be in-flight at a time
            # Should be enough for testing, can be extended later.
            self._rsp = packet

        elif packet.packet_type == RPCPacketType.LOG:
            if self.device_log_handler is not None:
                try:
                    self.device_log_handler(packet.payload.decode())
                except UnicodeDecodeError:
                    LOGGER.debug(f'[{self.transport}] dropping malformed log packet')
            return

        elif self.handler_exists(packet):
            self.lookup(packet)(self, packet)

        elif self.default_packet_handler is not None:
            self.default_packet_handler(self, packet)

        else:
            LOGGER.error(f'[{self.transport}] unhandled packet {packet}')

    def register_packet(self, packet_type: RPCPacketType, opcode: int, packet_handler):
        self.handler_lut[packet_type][opcode] = packet_handler

    def ack(self, opcode: int):
        # ACKs should always be sent in the same order the events were received
        packet = RPCPacket(RPCPacketType.ACK, opcode, payload=b'')

        self.transport.send(packet.serialized)

    def cmd(self, opcode: int, data: dict or bytes = b'', timeout=5):
        packet = RPCPacket(RPCPacketType.CMD, opcode, payload=data)
        self._rsp = None

        while not self.established:
            time.sleep(.01)

        self.transport.send(packet.serialized)

        end_time = time.monotonic() + timeout
        while self._rsp is None:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Command timeout')

        return self._rsp

    def clear_events(self):
        while not self.events.empty():
            self.events.get()

    def get_evt(self, opcode=None, schema=None, timeout=5):
        event = None
        decoded = None

        if opcode is not None:
            # TODO: add filtering by opcode
            event = self.events.get(timeout=timeout)
        else:
            event = self.events.get(timeout=timeout)

        if schema:
            decoded = event.decode(schema)

        return event, decoded

    def send_init(self):
        packet = RPCPacket(RPCPacketType.INIT, 0, payload=b'')

        self.transport.send(packet.serialized)

    def send_initrsp(self):
        packet = RPCPacket(RPCPacketType.INITRSP, 0, payload=b'')

        self.transport.send(packet.serialized)