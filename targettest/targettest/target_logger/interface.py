#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
from abc import ABC


class TargetLogger(ABC):
    """Sink for target logs. I.e. this will read log messages from the target over
       UART or RTT or some other transport and pass them to the test framework
       for debug purposes.
    """

    def __init__(self, output_handler):
        """Initialize and set a callback for each retrieved log line."""

        # Implementation should call this when it has read a full line.
        # If this is not set, the default output method is left up to implementation.
        # E.g. send to logger instance, or stderr etc..
        self.output_handler = output_handler

    def open(self):
        """Open the log transport (e.g. UART / RTT). Blocking."""
        pass

    def flush(self):
        """Force flushing the buffer (if it exists) into output_handler"""
        pass

    def close(self):
        """Close the log transport (e.g. UART / RTT). Blocking."""
        pass

