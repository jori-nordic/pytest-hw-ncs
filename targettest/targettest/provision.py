#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#
import logging
from typing import List
from targettest.target.interface import TargetDevice

LOGGER = logging.getLogger(__name__)

devkits = []
def register_dk(device: TargetDevice):
    LOGGER.debug(f'Register DK: {device.snr}')
    devkits.append(device)

def get_available_dk(family, id=None):
    family = family.upper()

    for dev in devkits:
        if dev.available() and dev.family == family:
            if id is None:
                return dev
            else:
                id = int(id)
                if dev.snr == id:
                    return dev
    return None

def get_dk_list():
    return devkits

def halt_unused(devkits: List[TargetDevice]):
    unused = [dk for dk in devkits if dk.available()]
    LOGGER.info(f'Halting unused DKs {unused}')
    for dk in unused:
        dk.halt()

