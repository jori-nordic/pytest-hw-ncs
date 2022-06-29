class RPCDevice:
    def __init__(self, testdevice):
        self.serial = None
        self.testdevice = testdevice
    def open(self):
        print("RPC open")
        self.serial = 1
    def close(self):
        print("RPC close")
        self.serial = 0
