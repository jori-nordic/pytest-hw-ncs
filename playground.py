#!/usr/bin/env python3
import cbor2
from targettest.uart_channel import UARTRPCChannel, UARTDecodingState, UARTHeader
from targettest.rpc_packet import (RPCPacket, RPCPacketType)
from targettest.cbor import CBORPayload

state = UARTDecodingState()

def handle_rx(data: bytes):
    # Prepend the (just received) data with the remains of the last RX
    data = state.rx_buf + data
    # Save the current data in case decoding is not complete
    state.rx_buf = data

    if state.header is None and len(data) >= UARTHeader._size:
        # Attempt to decode the header
        state.header = UARTHeader.unpack(data)

    if state.header is None:
        # header is invalid, eat one byte and try again (if enough bytes)
        state.rx_buf = state.rx_buf[1:]
        if len(data) >= UARTHeader._size:
            handle_rx(b'')

    else:
        # Header has been decoded
        # Try to decode the packet
        if len(data[state.header._size:]) >= state.header.length:
            packet = RPCPacket.unpack(data)
            handler(packet)

            # Consume the data in the RX buffer
            data = data[state.header._size + state.header.length:]
            state.reset()

            if len(data) > 0:
                print(f'data remaining')
                handle_rx(data)

def handler(packet):
    print('##########################################')
    print(f'handle packet: {packet}')


# import pdb;pdb.set_trace()
handle_rx(bytes.fromhex('01 02 03 55 41 52 54 07 00 00 01 ff'))
handle_rx(bytes.fromhex('00 00 00 00 f6 55 41 52 54 07 00 00 01 ff 00 00 00 00 f6'))

handle_rx(bytes.fromhex('55 41 52 54 10 00 00 04 00 ff 00 ff 00 6e 72 66 5f 70 79 74 65 73 74'))
