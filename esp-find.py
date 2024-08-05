import usb.core
import usb.util
import os
import serial
import time


def get_port(serial_number):
    by_id_path = '/dev/serial/by-id'
    if not os.path.exists(by_id_path):
        raise FileNotFoundError(f"{by_id_path} does not exist")

    for device in os.listdir(by_id_path):
        if serial_number in device:
            return os.path.join(by_id_path, device)

    raise ValueError(f"No device with serial number {serial_number} found")

def discover_serial_by_pid(idVendor):
    devices = usb.core.find(find_all=True, idVendor=idVendor)
    serial_numbers = []

    for dev in devices:
        d = {'serial': dev.serial_number,
             'port': get_port(dev.serial_number)}
        serial_numbers.append(d)

    print(f'Found serials: {serial_numbers}')

    return serial_numbers[0]['port']

def connect(serial_port):
    print(f'opening {serial_port}')

    s = serial.Serial()
    s.baudrate = 115200
    s.port = serial_port

    s.dtr = True
    s.rts = False

    if True:
        s.dtr = False
        s.rts = True

        MINIMAL_EN_TRUE_DELAY = 0.005
        time.sleep(MINIMAL_EN_TRUE_DELAY)

    s.rts = False

    print('Entering RX loop')
    s.open()

    line = b''
    while True:
        recv = s.read(1)

        # Yield to other threads
        if recv == b'':
            time.sleep(0.0001)
            continue

        line += recv

        if recv == b'\n':
            print(f'RX {line}')
            line = b''



if __name__ == "__main__":
    VENDOR_ID = 0x303a

    try:
        serial_port = discover_serial_by_pid(VENDOR_ID)

        connect(serial_port)
    except ValueError as e:
        print(e)
    except FileNotFoundError as e:
        print(e)
