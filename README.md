# Pytest-based embedded testing framework

# WARNING

This branch IS NOT READY YET! DO NOT USE!
Also I force-push all the time :)

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

## Pre-requesites

Install the `targettest` package as local. This will install the required dependencies.
``` sh
pip3 install -e targettest/
```

## Building

Source `zephyr-env.sh` (just like when building a stand-alone zephyr project).
Call `build.sh`, it will build all the test FW images for the 'nrf5340dk_nrf5340_cpuapp' and 'nrf52840dk_nrf52840' platforms.

The build output is located in `build/`, with the path of the test suite folder.

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

### Default options

Call `pytest` (no arguments) at the repo root.
Logs will only be printed if a testcase fails.

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

## Test fixtures

Pytest has the concept of [Test fixtures](https://docs.pytest.org/en/7.1.x/explanation/fixtures.html#about-fixtures).

In a nutshell, they define the environment of the test:
Instead on overloading `setUp` and `tearDown` methods, the test can require the presence of ready-to-use objects.

The testcase method simply defines a parameter, and pytest will look for and execute a function decorated with `@pytest.fixture()` that has the same name. This fixture function can either return a value, or act as a context manager and `yield` a value, allowing it to do some cleanup when the testcase exits.

E.g. a testcase that only deals with checking the throughput of a BLE connection can request the presence of a `connection` object, for which it can then call `send` and `receive` functions. Then the test code is very straightforward to read and there is no confusion on what it is actually testing.

Fixtures can be scoped (session, class, case) and can also request other fixtures.

## Test setup procedure

When pytest is invoked:
- Parsing starts at `conftest.py`
    - `pytest_addoption()` adds some custom options to the pytest cli
    - The `devkits()` fixture registers development kits connected to the computer

Pytest begins executing a test suite:
- The `flasheddevices()` fixture provisions two devices of the correct family from the registered list, and flashes them with the firmware that matches the test suite's folder name. The emulator is also connected to. The unused DKs' CPUs are halted.

Pytest begins executing a test case:
- The `testdevices()` fixture is requested by the testcases. It opens the PC's serial port, and initiates nRF RPC communication. Once it has received the READY event (0x01) for both DUT and Tester, and opened the RTT logging channel, it returns the two devices as a dict.

Pytest ends the test case:
- Control is returned to `testdevices()`, which then prints the device logs for that test case.

Pytest ends the test suite:
- Control is returned to `flasheddevices()`, that in turn releases the `FlashedDevice` objects, closing the emulator connections.

## Communications

### NIH RPC

It is possible for the python test script to call test functions defined in the firmware.
This happens using the `nih_rpc` library, communicating over UART (serial port).
Similarly, it is possible to receive events from the device.

The format is roughly: type, opcode, RPC metadata, payload (serialized-struct).

The opcode is a byte, and the IDs used in the firmware and in the test script
need to match. It is recommended to use enums to that effect.

### Calling functions on target

`RPCChannel.cmd()`: send a command (with optional parameters) to the device.

### Getting data from the target

Events that are emitted on target are stored in a python
[Queue](https://docs.python.org/3/library/queue.html) in a FIFO manner.

`RPCChannel.get_evt()`: get an event from the device. A tuple is returned,
containing the raw event and its decoded payload.

# Other boards

What do we need to run the framework on other boards?

- get firmware
- flash firmware
- set-up OOB logging (doesn't have to be over RTT)
- set-up NIH-RPC channel (doesn't have to be over UART)

- method to discover board (opt)
  - find serial port for RPC+log
  - find endpoint to flash to

# TODO

Goal: run tests written for this framework on zephyr platforms from different vendors.

- [x] integrate sysbuild into build.sh
- [x] run on latest NCS
- [x] run on latest zephyr
- [ ] run with board from any other vendor
- [ ] make platform description schema (platform.yml)
- [ ] make it possible to flash+log+run without segger emulator
- [x] describe nih_rpc
- [x] fix most TODOs in nih_rpc
- [ ] write Bluetooth stress test
- [ ] make pytest understand the platform test matrix
- [ ] make pytest build the firmware
- [ ] support for split-build (ie hci_uart or ipc as precompiled .hex)
- [ ] clean-up architecture. or at least document w/ diagram.
- [x] initialize Devkit() objects from only one place (and time)
- [x] fix up INITRSP / READY-event business
  - we just initialize NIH-RPC from main()
- [ ] namespace for System RPC events
