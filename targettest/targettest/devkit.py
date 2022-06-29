class Devkit:
    def __init__(self, id, name):
        self.segger_id = id
        self.name = name
        self.in_use = False
    def open(self):
        print(f'Devkit {self.name} opened')
        self.in_use = True
    def close(self):
        print(f'Devkit {self.name} closed')
        self.in_use = False
    def available(self):
        return not self.in_use

devkits = [Devkit(1, "device-one"),
           Devkit(2, "device-two"),
           Devkit(3, "device-three")]

def get_available_dk():
    for dev in devkits:
        if dev.available():
            return dev
    return False
