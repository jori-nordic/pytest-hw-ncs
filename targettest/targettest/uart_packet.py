#!/usr/bin/env python3

import struct


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
