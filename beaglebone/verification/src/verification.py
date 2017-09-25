import sys

import cv2
import numpy as np
import hashlib
import struct

from time import time

from lib.pinto.codec import decode
from lib.pinto.common import filename, ext, getROI, parse



# verify
def _verify(vhd_file, ved_file, vbd_file, row, col, scale):
    print('verify video')
    print('  vhd file: %s' % vhd_file)
    print('  ved file: %s' % ved_file)
    print('  vbd file: %s' % vbd_file)
    t = time()


    ohd = None
    with open(vhd_file, 'r') as vhd:
        ohd = vhd.read().split()[0].split('=')[1]
        
    hd = None
    with open(ved_file, 'rb') as ved:
        with open(vbd_file, 'r') as vbd:
            h_obj = hashlib.new('sha256')

            while True:
                s = ved.read(4)
                if len(s) == 0: break
                size = struct.unpack('>I', s)[0]
                data = ved.read(size)
                
                frame = decode(np.fromstring(data, dtype=np.uint8))

                line = vbd.readline()[:-1]
                if line:
                    index = [ int(x) for x in line.split(',') ]
                    
                h, w = frame.shape[:2]
                
                for r in range(row):
                    for c in range(col):
                        x1, y1 = w * c // col, h * r // row
                        x2, y2 = w * (c + 1) // col, h * (r + 1) // row
                        
                        if line and (r * col + c) in index:
                            # blurred block
                            rh, rw = cv2.resize(getROI(frame, x1, y1, x2, y2), None, fx=1.0/scale, fy=1.0/scale, interpolation=cv2.INTER_NEAREST).shape[:2]
                            roi = getROI(frame, x1, y1, x1 + rw, y1 + rh)
                            h_obj.update(bytes(roi))
                        else:
                            # non blurred block
                            shrinked = cv2.resize(getROI(frame, x1, y1, x2, y2), None, fx=1.0/scale, fy=1.0/scale, interpolation=cv2.INTER_NEAREST)
                            h_obj.update(bytes(shrinked))


            hd = h_obj.hexdigest()
    print('  hash data in DB   :', ohd)
    print('  hash data of query:', hd)
    print('  result: %s' % ('same' if ohd == hd else 'different'))
    print('  elapsed time:', time() - t)
    print('')




# usage
def usage():
    print('usage:')
    print('python3 verification.py (original vhd file) (blurred ved file) (vbd file)')



# main
if __name__ == '__main__':
    if len(sys.argv) == 4:
        # video hash file
        vhd_file = '../data/fingerprint/' + ext(filename(sys.argv[1]), 'vhd')

        # video encoding file
        ved_file = '../data/video/' + ext(filename(sys.argv[2]), 'ved')

        # video blur file
        vbd_file = '../data/blur/' + ext(filename(sys.argv[3]), 'vbd')

        # configuration: row, col, scale
        with open('../config.txt', 'r') as config:
            data = parse(config.read())
            try:
                row = int(data['row'])
                col = int(data['column'])
                scale = float(data['scale'])
            except KeyError:
                print('error: configuration')
                exit()


        _verify(vhd_file, ved_file, vbd_file, row, col ,scale)


    else:
        usage()
