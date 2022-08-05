#!/usr/bin/env python3

import pytest
from contextlib import contextmanager
from targettest.devkit import (populate_dks,
                               get_available_dk,
                               recover,
                               flash,
                               reset)
import pathlib


# Base path of the testing system.
# Used for locating the binaries to flash for each test.
BASE_PATH = pathlib.Path.cwd()


def get_fw_path(suite, child_image_name=None):
    """Find the firmware for the test suite"""
    # TODO: handle netcore
    test_path = pathlib.Path(
        getattr(suite.module, "__file__")).parent
    fw_build = BASE_PATH / 'build' / test_path.relative_to(BASE_PATH)

    if child_image_name is None:
        fw_hex = fw_build / 'zephyr/zephyr.hex'
    else:
        fw_hex = fw_build / child_image_name / 'zephyr/zephyr.hex'

    assert fw_build.exists(), "Missing firmware"

    return fw_hex


@pytest.fixture(scope="session", autouse=True)
def devkits():
    print(f'Discovering devices...')
    populate_dks()


@contextmanager
def hwdevice(request):
    family = 'NRF53'

    # Select HW device
    # TODO: add devconf parsing
    dev = get_available_dk(family)
    assert dev is not None, f'No {family} devices'

    recover(dev.segger_id, family)

    # Flash device with test FW & reset it
    if family == 'NRF53':
        # Flash the network core first
        fw_hex = get_fw_path(request, child_image_name='cpunet')
        flash(dev.segger_id, dev.family, fw_hex, core='NET')

    fw_hex = get_fw_path(request)
    flash(dev.segger_id, dev.family, fw_hex)

    reset(dev.segger_id, dev.family)

    # Open device comm channel
    dev.open()
    dev.start_logging()

    yield dev

    dev.stop_logging()
    dev.close()

