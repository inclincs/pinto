import cv2

import picamera
import picamera.array
from picamera.array import PiRGBArray

import numpy as np

from multiprocessing import Process, Queue

from time import time

from . import codec

import hashlib

    

def process(file, q):
    with open(file, 'wb') as f:
        while True:
            try:
                i = q.get()
                if i == None: break

                e = i
                
                f.write((len(e)).to_bytes(4, byteorder='big'))
                f.write(e.tostring())
            except:
               break



class Output(object):
    def __init__(self, camera, q, store):
        self.camera = camera
        self.q = q
        self.store = store

        self.frames = []

        
    def write(self, b):
        t = time()
        
        f = picamera.array.bytes_to_rgb(b, self.camera.resolution)

        
        self.q.put(cv2.imencode('.png', f)[1])
##        self.q.put(f)
            if self.store: self.frames.append(f)
        
        print('time save', time() - t)


    def flush(self):
        self.q.put(None)


class Output_Hash(object):
    def __init__(self, camera, h_file):
        self.camera = camera
        self.h_file = h_file

        self.h_obj = hashlib.new('sha256')

        
    def write(self, b):
##        t = time()
        
        f = picamera.array.bytes_to_rgb(b, self.camera.resolution)
        height, width = f.shape[:2]
        s = cv2.resize(f, (int(width * 0.5), int(height * 0.5)))
        
        self.h_obj.update(bytes(cv2.resize(f, (320, 180))))
        
##        print('time hash', time() - t)        


    def flush(self):
        with open(self.h_file, 'w') as f:
            f.write(self.h_obj.hexdigest())



def capture(file, duration, result=False):
    with picamera.PiCamera() as cam:
        cam.resolution = (1280, 720)
        cam.framerate = 20
        
        q = Queue()

        p = Process(target=process, args=(file, q))
        p.start()

        output = Output(cam, q, result)
        output_hash = Output_Hash(cam, file[:-4] + '.vhd')
        
        cam.start_recording(output, format='bgr')
        cam.start_recording(output_hash, format='bgr', splitter_port=2)

        t = time()
        while time() - t <= duration:
            cam.wait_recording(0.5)

        cam.stop_recording()
        cam.stop_recording(splitter_port=2)

        p.join()

        # hash save

        if result: return output.frames
