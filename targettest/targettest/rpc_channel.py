#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import time
import queue
import logging
from targettest.abstract_transport import PacketTransport
from targettest.rpc_packet import RPCPacket, RPCPacketType

LOGGER = logging.getLogger(__name__)


class RPCChannel():
    def __init__(self, transport: PacketTransport, default_packet_handler=None):
        # A valid transport has to be initialized first
        self.transport = transport
        self.transport.packet_handler = self.handler

        self.established = False

        # Handlers
        self.events = queue.Queue()
        self.default_packet_handler = default_packet_handler
        self.handler_lut = {item.value: {} for item in RPCPacketType}

    def handler_exists(self, packet: RPCPacket):
        return packet.opcode in self.handler_lut[packet.packet_type]

    def lookup(self, packet: RPCPacket):
        return self.handler_lut[packet.packet_type][packet.opcode]

    def handler(self, packet: RPCPacket):
        LOGGER.debug(f'Handling {packet}')
        # TODO: terminate session on ERR packets
        # Call opcode handler if registered, else call default handler
        if packet.packet_type == RPCPacketType.INIT:
            self.transport.clear_buffers()
            self.clear_events()

            # Mark channel as usable and send INIT response
            self.send_init()
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

        elif self.handler_exists(packet):
            self.lookup(packet)(self, packet)

        elif self.default_packet_handler is not None:
            self.default_packet_handler(self, packet)

        else:
            LOGGER.error(f'[{self.transport}] unhandled packet {packet}')

    def register_packet(self, packet_type: RPCPacketType, opcode: int, packet_handler):
        self.handler_lut[packet_type][opcode] = packet_handler

    def ack(self, opcode: int):
        # TODO: add event index or document in order
        packet = RPCPacket(RPCPacketType.ACK, opcode, payload=b'')

        self.transport.send(packet.raw)

    def cmd(self, opcode: int, data: dict or bytes = b'', timeout=5):
        packet = RPCPacket(RPCPacketType.CMD, opcode, payload=data)
        self._rsp = None

        self.transport.send(packet.raw)

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

        # TODO: add filtering by opcode
        if opcode is None:
            event = self.events.get(timeout=timeout)

        if schema:
            decoded = event.decode(schema)

        return event, decoded

    def send_init(self):
        # TODO: implement
        pass
