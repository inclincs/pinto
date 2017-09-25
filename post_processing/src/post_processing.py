# -*- coding: utf8 -*-

import sys

import cv2
import numpy as np
import struct

from time import time

from lib.pinto.codec import encode, decode
from lib.pinto.common import filename, ext, getROI, setROI, parse



def face(frame, cascade):
    return list(cascade.detectMultiScale(
        frame,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE
    ))



def license_plate(frame, cascade):
    return list(cascade.detectMultiScale(
        frame,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(60, 10),
        flags=cv2.CASCADE_DO_CANNY_PRUNING
    ))



# blur
def _blur(ved_file, vmd_file, vbd_file, pbved_file, pbvmd_file):
    cascades = [ cv2.CascadeClassifier(x) for x in [ '../data/detect/face.xml', '../data/detect/eu.xml', '../data/detect/kr.xml' ] ]
    
    # Read vmd file
    with open(vmd_file, 'r') as vmd:
        total = vmd.read()

        # Copy vmd to pbvmd
        with open(pbvmd_file, 'w') as pbvmd:
            pbvmd.write(total)

        # Parse information
        data = parse(total)
        try:
            video_time = int(data['video_time'])
            row = int(data['row'])
            col = int(data['column'])
            scale = float(data['scale'])
        except KeyError:
            print('error: configuration')
            exit()

    # Description
    print('blur video')
    print('  video time  : %d' % video_time)
    print('  block row   : %d' % row)
    print('        column: %d' % col)
    print('        scale : %.1f' % scale)
    print('  ved file: %s' % ved_file)
    print('  vmd file: %s' % vmd_file)
    print('  vbd file: %s' % vbd_file)
    
    t = time()

    # Read ved file
    with open(ved_file, 'rb') as ved:

        with open(pbved_file, 'wb') as pbved:
            while True:
                s = ved.read(4)
                if len(s) == 0: break
                size = struct.unpack('>I', s)[0]
                data = ved.read(size)
                
                frame = decode(np.fromstring(data, dtype=np.uint8))

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # detect face & lp or random pick
                rs= face(frame, cascades[0]) + license_plate(frame, cascades[2])

                # write vbd file
                s = set()
                for (x, y, w, h) in rs:
                    dx, dy = int(col * x / width), int(row * y / height)
                    ddx, ddy = int(col * (x + w) / width), int(row * (y + h) / height)

                    a = np.array([ x + dx for x in range(ddx - dx + 1) ])
                    for i in range(ddy - dy + 1):
                        a += col
                        s.update(map(str, a.tolist()))

                vbd.write(",".join(list(s)) + '\n')

                # blur
                for i in s:
                    if not (0 <= i < row * col):
                        print('warning: blur index - out of range', i)
                        continue
                    r, c = int(i) // col, int(i) % col
                    x1, y1 = w * c // col, h * r // row
                    x2, y2 = w * (c + 1) // col, h * (r + 1) // row

                    shrinked = cv2.resize(getROI(frame, x1, y1, x2, y2), None, fx=1.0 / scale, fy=1.0 / scale, interpolation=cv2.INTER_NEAREST)
                    setROI(frame, x1, y1, x1 + shrinked.shape[1], y1 + shrinked.shape[0], shrinked)

                e = encode(frame)
                
                # write pbved file
                pbved.write(struct.pack('>I', len(e)))
                pbved.write(e)

    print('  pbved file: %s' % pbved_file)
    print('')
    print('  elapsed time: %.3f' % (time() - t))
    print('')




# main
if __name__ == '__main__':
    # python blur.py (ved file) [(vbd file) [(blurred ved file)]]


    # video encoding file path
    ved_path = '../data/video/'
    
    # video meta data file path
    vmd_path = '../data/meta/'

    # video blur data file path
    vbd_path = '../data/blur/'
    
    
    if 2 <= len(sys.argv) <= 4:
        # video encoding file
        ved_file = ext(filename(sys.argv[1]), 'ved')

        # video meta data file
        vmd_file = ext(filename(sys.argv[1]), 'vmd')

        # video blur data file
        if len(sys.argv) == 2:
            vbd_file = ext(ved_file, 'vbd')
        else:
            vbd_file = ext(filename(sys.argv[2]), 'vbd')

        # partial blurred video encoding file
        if len(sys.argv) == 3:
            pbved_file = ext(filename(sys.argv[1]) + '_blur', '.ved')
        else:
            pbved_file = ext(filename(sys.argv[3]), 'ved')
            if ved_file == pbved_file:
                print('same file name')
                exit(1)

        # partial blurred video meta data file
        pbvmd_file = ext(pbved_file, 'vmd')

        
        _blur(ved_path + ved_file, vmd_path + vmd_file, vbd_path + vbd_file, ved_path + pbved_file, vmd_path + pbvmd_file)
    else:
        print('python blur.py (original ved file) [(vbd file) [(blurred ved file)]]')





            
