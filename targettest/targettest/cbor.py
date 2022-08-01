#!/usr/bin/env python3

from io import BytesIO
import cbor2


def encode_null():
    return cbor2.dumps(None)

def encode_obj(obj):
    return cbor2.dumps(obj)


class CBORPayload():
    def __init__(self, first_obj=None):
        self.encoded = b''
        self.objects = []

        # End with a null value (nRF RPC limitation)
        self.encoded += encode_null()

        if first_obj is not None:
            self.append(first_obj)

    def append(self, obj):
        self.objects.append(obj)
        self.encoded = self.encoded[:-1] # Remove previous null value
        self.encoded += encode_obj(obj) + encode_null()

    @classmethod
    def read(cls, payload: bytes):
        objects = []

        # FIXME: the CBOR bytestream nRF RPC / entropy sample output is not
        # compliant: the elements are not wrapped in a container type (e.g. an
        # array/map), and so, compliant libraries such as the python one and the
        # online sandbox are not able to decode it properly. If it were
        # compliant, this fn could just be a call to `cbor2.loads(payload)`.
        #
        # The reverse is also true: nRF RPC will fail to pick individual
        # elements if sent as an array: we have to either use struct.pack and
        # just serialize the data ourselves (nulling any benefits of the CBOR
        # encoding) or append encoded objects manually (out of spec, but it's
        # what we try to do in this file).
        with BytesIO(payload) as fp:
            try:
                while objects.append(cbor2.load(fp)):
                    pass
            except cbor2.CBORDecodeEOF:
                # End of stream has been reached
                pass

        # Remove final null value if present
        if objects[-1] == None:
            objects = objects[:-1]

        payload = CBORPayload()
        for obj in objects:
            payload.append(obj)

        return payload
