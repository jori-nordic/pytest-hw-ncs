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
## Discovery
## Filtering
## Running
### For different families
### With a static device definition
### Printing the logs as they come
## Debugging
### Ozone
### Python
## Reporting

# How does it work
## Test setup procedure
## Discovering devices
## Device provisioning
## Communications
### nRF RPC + CBOR
### Calling functions on target
### Getting data from the target
