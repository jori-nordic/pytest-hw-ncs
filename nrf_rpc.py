#!/usr/bin/env python3

# Scratchpad for nRF RPC UART transport

import cbor2
from targettest.uart_channel import UARTRPCChannel
from targettest.rpc_packet import (RPCPacket, RPCPacketType)


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


rpc = UARTRPCChannel(port='/dev/ttyACM6', rpc_handler=handle_payload)
rpc.start()

# Receive init command
# CBOR, has w/a u32

# Don't exit immediately
rpc.join()
