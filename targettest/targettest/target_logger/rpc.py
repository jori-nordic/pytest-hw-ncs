#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
from targettest.target_logger.interface import TargetLogger


class RPCLogger(TargetLogger):
    """Logger over NIH-RPC. NIH-RPC will call devkit.log_handler directly."""
    # TODO: come up with better architecture than this

    def open(self):
        pass

    def flush(self):
        pass

    def close(self):
        pass
