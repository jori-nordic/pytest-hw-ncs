import time
import queue
import logging
from targettest.abstract_transport import PacketTransport
from targettest.cbor import CBORPayload
from targettest.rpc_packet import RPCPacket, RPCPacketType

LOGGER = logging.getLogger(__name__)


class RPCChannel():
    def __init__(self, transport: PacketTransport, default_packet_handler=None, group_name=None):
        # A valid transport has to be initialized first
        self.transport = transport
        self.transport.packet_handler = self.handler

        self.group_name = group_name
        self.remote_gid = 0
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
            # Check the INIT packet is for the test system
            assert packet.payload == b'\x00' + self.group_name.encode()
            self.remote_gid = packet.gid_src

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
        packet = RPCPacket(RPCPacketType.ACK, opcode,
                           src=0, dst=0xFF,
                           gid_src=self.remote_gid, gid_dst=self.remote_gid,
                           payload=b'')

        self.transport.send(packet.raw)

    def evt(self, opcode: int, data: bytes=b'', timeout=5):
        packet = RPCPacket(RPCPacketType.EVT, opcode,
                           src=0, dst=0xFF,
                           gid_src=self.remote_gid, gid_dst=self.remote_gid,
                           payload=data)
        self._ack = (None, opcode)

        self.transport.send(packet.raw)

        end_time = time.monotonic() + timeout
        while self._ack[0] is None:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Async command timeout')

        # Return packet containing the ACK
        return self._ack[1]

    def evt_cbor(self, opcode: int, data=None, timeout=5):
        if data is not None:
            payload = CBORPayload(data).encoded
            LOGGER.debug(f'encoded payload: {payload.hex(" ")}')
            self.evt(opcode, payload, timeout=timeout)
        else:
            self.evt(opcode, timeout=timeout)

    def cmd(self, opcode: int, data: bytes=b'', timeout=5):
        # WARNING:
        #
        # Only use EVENTS (async) when calling APIs that make use of nRF RPC on
        # the device (e.g., if using BT_RPC and calling bt_enable() in the
        # handler).
        #
        # If commands (sync) are used, nRF RPC will get confused, being called
        # from an existing RPC context (UART in this case) and will try to send
        # the command over IPC, but using the wrong IDs, resulting in a deadlock.
        packet = RPCPacket(RPCPacketType.CMD, opcode,
                           src=0, dst=0xFF,
                           gid_src=self.remote_gid, gid_dst=self.remote_gid,
                           payload=data)
        self._rsp = None

        self.transport.send(packet.raw)

        end_time = time.monotonic() + timeout
        while self._rsp is None:
            time.sleep(.01)
            if time.monotonic() > end_time:
                raise Exception('Command timeout')

        return self._rsp

    def cmd_cbor(self, opcode: int, data=None, timeout=5):
        if data is not None:
            payload = CBORPayload(data).encoded
            LOGGER.debug(f'encoded payload: {payload.hex(" ")}')
            rsp = self.cmd(opcode, payload, timeout=timeout)
        else:
            rsp = self.cmd(opcode, timeout=timeout)

        LOGGER.debug(f'decoded payload: {rsp.payload.hex(" ")}')
        return CBORPayload.read(rsp.payload).objects

    def clear_events(self):
        while not self.events.empty():
            self.events.get()

    def get_evt(self, opcode=None, timeout=5):
        if opcode is None:
            return self.events.get(timeout=timeout)

        # TODO: add filtering by opcode
        return None

    def send_init(self):
        # Isn't encoded with CBOR
        # Protocol version + RPC group name
        version = b'\x00'
        payload = self.group_name.encode()
        packet = RPCPacket(RPCPacketType.INIT,
                           0, 0, 0xFF, self.remote_gid, self.remote_gid,
                           version + payload)

        LOGGER.debug(f'Send handshake {packet}')
        self.transport.send(packet.raw)
