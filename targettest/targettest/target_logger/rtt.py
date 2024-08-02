import time
import logging
import threading
from targettest.target_logger.interface import TargetLogger


LOGGER = logging.getLogger(__name__)

class RTTLogger(TargetLogger, threading.Thread):
    def __init__(self, id, emulator, output_handler=None, search_timeout=15):
        threading.Thread.__init__(self, daemon=True)
        self._stop_rx_flag = threading.Event() # Used to cleanly stop the RX thread
        self.ready = False
        self.emulator = emulator
        self.segger_id = id
        self.search_timeout = search_timeout
        self.output_handler = output_handler

    def open(self):
        def _wait_until_thread_started(ready):
            end_time = time.monotonic() + self.search_timeout
            while not ready():
                time.sleep(.1)
                if time.monotonic() > end_time:
                    raise Exception('Unable to start logging')

        self.start()
        _wait_until_thread_started(lambda: self.ready)

        LOGGER.debug(f'[{self.segger_id}] logging started')

    def flush(self):
        # les chiens aboient, la caravane..
        pass

    def close(self):
        LOGGER.debug(f'[{self.segger_id}] stopping logger..')
        self._stop_rx_flag.set()
        self.join()
        LOGGER.debug(f'[{self.segger_id}] logging stopped')

    def run(self):
        LOGGER.debug('RTT start')
        self._stop_rx_flag.clear()

        LOGGER.debug('RTT search...')
        self.emulator.rtt_start()
        while not (self.emulator.rtt_is_control_block_found() or
                   self._stop_rx_flag.is_set()):
            time.sleep(.1)

        self.ready = True

        LOGGER.debug('RTT opened')
        while not self._stop_rx_flag.is_set():
            recv = self.emulator.rtt_read(0, 255)
            if len(recv) > 0:
                self.output_handler(recv)

            # Yield to other threads
            time.sleep(.01)

        LOGGER.debug('RTT stop')
        self.emulator.rtt_stop()
