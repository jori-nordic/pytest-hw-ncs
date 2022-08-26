# Pytest-based embedded testing framework

# What is it

This is an example test framework for testing embedded applications on the nRF52 and nRF53 platforms.
It is not officially supported by Nordic Semiconductor.

Tests are written using the pytest framework, leveraging its filtering and reporting capabilities.
The tests can call (C) functions running on the device and get data back, using nRF RPC.

# How do I use it

## Folder structure

```
├── build.sh                          # test FW build script
├── conftest.py                       # configuration script automatically run by pytest
├── pytest.ini                        # pytest configuration options
├── README.md
├── sample_devconf.yml                # example static device configuration
├── targettest                        # testing framework (as python library)
│   ├── setup.cfg
│   ├── setup.py
│   └── targettest
│       ├── cbor.py                   # CBOR encoding/decoding
│       ├── devkit.py                 # Hardware device representation and operations
│       ├── provision.py              # Preparation of the device for a test
│       ├── abstract_transport.py     # interface for the nRF RPC packet transport
│       ├── rpc_packet.py             # nRF RPC packet formatting
│       ├── rpc_channel.py            # nRF RPC packet dispatch (into the test)
│       ├── uart_packet.py            # UART packet encapsulation
│       └── uart_channel.py           # Serial port handling & UART packet re-assembly
│
└── tests                                         # Top-level test suite folder
    └── bt_notify                                 # example test suite
        ├── fw                                    # firmware for that test suite
        │   ├── boards                            # DeviceTree overlays for specific boards (set UART speed etc)
        │   │   ├── nrf52840dk_nrf52840.overlay
        │   │   ├── nrf5340dk_nrf5340_cpuapp.conf
        │   │   └── nrf5340dk_nrf5340_cpuapp.overlay
        │   ├── child_image                       # Configuration overrides for network core images
        │   │   └── rpc_host.conf
        │   ├── CMakeLists.txt
        │   ├── prj.conf                          # Default prj.conf
        │   ├── prj_nrf5340dk_nrf5340_cpuapp.conf # prj.conf used when compiling for that board
        │   ├── src
        │   │   ├── main.c
        │   │   └── rpc_handler.c                 # target commands and events
        │   └── test_rpc_opcodes.h                # command and event IDs
        └── test_bt_notify.py                     # contains the test logic
```

## Building

Source `zephyr-env.sh` (just like when building a stand-alone zephyr project).
Call `build.sh`, it will build all the test FW images for the 'nrf5340dk_nrf5340_cpuapp' and 'nrf52840dk_nrf52840' platforms.

Firmware images are defined as standard zephyr applications, so the Zephyr and NCS documentation applies.

## Discovery

Use the pytest `--collect-only` option along with any filtering (`-k`) necessary.
To get a list of all the test suites (`Class`) and cases (`Function`) in the repo:

``` sh
pytest --collect-only
```

Sample output:
``` sh
platform linux -- Python 3.8.5, pytest-6.2.2, py-1.10.0, pluggy-0.13.1
rootdir: /home/john/repos/pytest-hw-ncs, configfile: pytest.ini
collected 4 items

<Module tests/bt_notify/test_bt_notify.py>
  <Class TestBluetooth>
      <Function test_boot>
      <Function test_trigger_oops>
      <Function test_scan>
      <Function test_conn>
```

## Filtering

Pytest's [documentation](https://docs.pytest.org/en/7.1.x/how-to/usage.html#specifying-which-tests-to-run) applies.

## Running

### For different families

Use the `--dut-family` and `--tester-family` options.
E.g. run all tests with the DUT an nRF53 board and the tester an nRF52840 board:

``` sh
pytest --dut-family=nrf53 --tester-family=nrf52
```

### With a static device definition

By default, the test system will discover any nordic DKs connected to the computer and allocate the correct ones depending on the family.
This behavior can be changed by using a static configuration. When using a static configuration, pytest will not 'waste' time by querying all DKs connected, and will only communicate with the devices in the static configuration.

Call pytest with the `--devconf` option:

``` sh
pytest --devconf=./sample_devconf.yml
```

See `sample_devconf.yml` for the format.

### Without flashing

If quickly iterating on a testcase, it can be annoying to wait for the devices to be flashed (with the same FW image no less) on each run.
Use the `--no-flash` switch to skip flashing.

### Printing the logs as they come

Pytest is quiet by default, only printing the python logger's output when a test fails.
But when debugging, it might be useful to have immediate feedback.
Use the `--log-cli-level` switch to set the live log level.
Use the `-s` switch to print stdout immediately.

``` sh
pytest -s --log-cli-level=DEBUG
```

### Stopping on the first error

Pytest will by default run all the tests, even if one fails in the middle.
To stop on the first failure, use the `-x` switch.

## Debugging

### Firmware

The firmware can be debugged while the test is running.
Use the `--no-emu` switch to sever the test system's connection to the J-Link emulator.

As the test system uses the J-Link emulator connection for logging (over Segger RTT) and reset/halt, it will:
- not capture any device logs
- prompt the user to reset the boards for each testcase

To that end, a combination of switches have to be selected:
- `-s` to get the reset prompts
- `--no-flash` to not connect to the emulator for flashing
- `--no-emu` to not connect to the emulator during the test execution

E.g. to debug a testcase called 'test_scan':
``` sh
pytest -s --no-emu --no-flash -k test_scan
```

### Python

Pytest tests can be run in a python debugger, like any other script. VSCode is free and pretty nice, with support for threads.
See [this stackoverflow answer](https://stackoverflow.com/a/64629222) for an example debug configuration.

## Reporting

Pytest can emit JUnit reports [as per the documentation](https://docs.pytest.org/en/7.1.x/how-to/output.html#creating-junitxml-format-files):

``` sh
pytest --junitxml=path/to/report.xml
```

They can then be plugged in a CI system (like Jenkins) or easily viewed with [junit2html](https://gitlab.com/inorton/junit2html):

``` sh
# will generate path/to/report.xml.html

junit2html path/to/report.xml
```

# How does it work
## Test setup procedure
## Discovering devices
## Device provisioning
## Communications
### nRF RPC + CBOR
### Calling functions on target
### Getting data from the target
