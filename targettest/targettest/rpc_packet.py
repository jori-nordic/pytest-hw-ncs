#!/usr/bin/env python3
import enum
import struct
from targettest.uart_packet import UARTPacket


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

    # Header: SRC + type, ID, DST, GID SRC, GID DST
    def __init__(self,
                 packet_type: RPCPacketType,
                 opcode, src, dst, gid_src, gid_dst,
                 payload: bytes):
        self.packet_type = RPCPacketType(packet_type)
        self.opcode = opcode
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
        raw_header = payload[:cls._size]
        payload = payload[cls._size:]

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
