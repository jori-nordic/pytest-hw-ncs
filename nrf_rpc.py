#!/usr/bin/env python3

# Scratchpad for nRF RPC UART transport

import cbor2
from targettest.uart_channel import UARTRPCChannel
from targettest.rpc_packet import (RPCPacket, RPCPacketType)
from targettest.cbor import CBORPayload


def default_handler(packet: RPCPacket):
    print(f'Default RPC packet handler {packet}')

def handshake(packet: RPCPacket):
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
    print('')

def entropy_init(packet: RPCPacket):
    print(f'entropy_init: {packet}')

    decoded = CBORPayload.read(packet.payload)
    print(f'Decoded: {decoded.objects}')

    # i32: errcode
    payload = CBORPayload(0)
    packet = RPCPacket(RPCPacketType.RSP, 0x01,
                       0, 0, 0, 0,
                       payload.encoded)

    print(f'Response: {packet}')
    rpc.send(packet.raw)
    print('')

def entropy_get(packet: RPCPacket):
    print(f'entropy_get: {packet}')

    decoded = CBORPayload.read(packet.payload)
    print(f'Decoded: {decoded.objects}')

    # i32: length
    length = decoded.objects[0]

    # i32: errcode
    payload = CBORPayload(0)
    # bstr(len): entropy data
    payload.append(bytes(range(length)))

    packet = RPCPacket(RPCPacketType.RSP, 0x02,
                       0, 0, 0, 0,
                       payload.encoded)
    print(f'Response: {packet}')
    rpc.send(packet.raw)
    print('')


rpc = UARTRPCChannel(port='/dev/ttyACM6', default_packet_handler=default_handler)
rpc.start()

# Register cmd handlers
rpc.register_packet(RPCPacketType.INIT, 0x00, handshake)
rpc.register_packet(RPCPacketType.CMD, 0x01, entropy_init)
rpc.register_packet(RPCPacketType.CMD, 0x02, entropy_get)

# Don't exit immediately
rpc.join()
