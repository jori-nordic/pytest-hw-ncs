#!/usr/bin/env python3

# Scratchpad for nRF RPC UART transport

import cbor2
from targettest.uart_channel import UARTRPCChannel
from targettest.rpc_packet import (RPCPacket, RPCPacketType)


def default_handler(packet: RPCPacket):
    print(f'Default RPC packet handler {payload}')

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

def init_packet(packet: RPCPacket):
    print(f'Custom init handler: {packet}')


rpc = UARTRPCChannel(port='/dev/ttyACM6', default_packet_handler=default_handler)
rpc.start()

rpc.register_packet(RPCPacketType.INIT, 0x00, handshake)
rpc.register_packet(RPCPacketType.CMD, 0x01, init_packet)

# Receive init command
# CBOR, has w/a u32

# Don't exit immediately
rpc.join()
