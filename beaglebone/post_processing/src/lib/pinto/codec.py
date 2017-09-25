import cv2
import numpy
from time import time



# encoded -> save -> file
def save(file, encoded):
    with open(file, 'wb') as f:
        for e in encoded:
            f.write((len(e)).to_bytes(4, byteorder='big'))
            f.write(e.tostring())


# file -> load -> encoded
def load(file):
    with open(file, 'rb') as f:
        loaded = []
        while True:
            size = int.from_bytes(f.read(4), byteorder='big')
            if size == 0: break
            data = f.read(size)
            d = numpy.fromstring(data, dtype=numpy.uint8)
            loaded.append(d)
    return loaded



# frame -> encode -> encoded
def encode(arg):
    if type(arg) == list:
        return [ cv2.imencode('.png', arg)[1] for f in arg ]
    elif type(arg) == numpy.ndarray:
        return cv2.imencode('.png', arg)[1]



# encoded -> decode -> frame
def decode(arg):
    if type(arg) == list:
        return [ cv2.imdecode(f, cv2.IMREAD_UNCHANGED) for f in arg ]
    elif type(arg) == numpy.ndarray:
        return cv2.imdecode(arg, cv2.IMREAD_UNCHANGED)
