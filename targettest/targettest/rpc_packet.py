#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import enum
import struct
from targettest.uart_packet import UARTPacket

import logging

LOGGER = logging.getLogger(__name__)


class RPCPacketType(enum.IntEnum):
    INIT = 0
    CMD = enum.auto()
    RSP = enum.auto()
    EVT = enum.auto()
    ACK = enum.auto()
    ERR = enum.auto()


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

        # Build whole packet
        self.packet = UARTPacket(self.header + self.payload)
        self.raw = self.packet.raw

    def __repr__(self):
        return '{} {:02x} LEN {} DATA {}'.format(
            self.packet_type.name,
            self.opcode,
            len(self.payload),
            self.payload.hex(' ')
        )

    @classmethod
    def unpack(cls, packet: bytes):
        payload = UARTPacket.unpack(packet).payload

        # Separate RPC cmd/evt payload from RPC header
        rpc_header = payload[:cls._size]
        payload = payload[cls._size:]

        packet_type, opcode = struct.unpack(cls._format, rpc_header)

        return RPCPacket(packet_type, opcode, payload)


    def decode(self, schema: dict):
        return _decode(schema, self.payload)
