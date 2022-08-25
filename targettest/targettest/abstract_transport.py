from abc import ABC


class PacketTransport(ABC):
    def __init__(self, packet_handler):
        # Called on a full packet
        self.packet_handler = packet_handler

    def send(self, data, timeout=15):
        pass

    def clear_buffers(self):
        pass

    def open(self):
        pass

    def close(self):
        pass
