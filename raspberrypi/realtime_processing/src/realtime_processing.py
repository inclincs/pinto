# -*- coding: utf8 -*-

import sys
import os
import io

import cv2
import picamera
import numpy as np
import hashlib
import struct
import socket

from time import time, localtime, strftime

from multiprocessing import Process, Queue

from lib.pinto.codec import decode
from lib.pinto.common import filename, ext, getROI, parse


def _realtime_processing(ved_path, vmd_path, vhd_path, video_time, row, col, scale):
    print('realtime processing')
##    print('  video encoding file path : %s' % ved_path)
##    print('  video meta data file path: %s' % vmd_path)
##    print('  video hash data file path: %s' % vhd_path)
    print('  video time  : %d' % video_time)
    print('  block row   : %d' % row)
    print('        column: %d' % col)
    print('        scale : %.1f' % scale)
    print('')
    
    t = time()
    
    # Camera
    with picamera.PiCamera() as camera:
        camera.resolution = (1280, 720)
        camera.framerate = 25

        # Queue : process, timestamp
        q = Queue()
        q_timestamp = Queue()

        # Process : process, timestamp
        p = Process(target=process, args=(q, q_timestamp, ved_path, vmd_path, video_time, row, col, scale))
        p_timestamp = Process(target=timestamp, args=(q_timestamp, vhd_path))
        p.start()
        p_timestamp.start()

        # stream
        stream = Stream(q, video_time, row, col, scale, 1000)

        camera.start_recording(stream, format='mjpeg')

        try:
            while stream.recording:
                camera.wait_recording(1)
        except KeyboardInterrupt:
            pass
        
        camera.stop_recording()

    print('')
    print('  elapsed time: %.3f' % (time() - t))
    print('')




def process(q, q_timestamp, ved_path, vmd_path, video_time, row, col, scale):
    try:
        while True:
            i = q.get()
            if type(i) == str:
                t, d = i[0], i[1:]
                if t == '0':
                    # start video
                    name = d
                    ved = open(os.path.join(ved_path, name) + '.ved', 'wb')
                    vmd = open(os.path.join(vmd_path, name) + '.vmd', 'w')
                    print('  record %s' % (name))
                elif t == '1':
                    # end video
                    frame_count, digest = str(d).split(',')
                    q_timestamp.put(name + digest)
                    if ved: ved.close()
                    if vmd:
                        vmd.write('video_time=' + str(video_time) + '\n')
                        vmd.write('row=' + str(row) + '\n')
                        vmd.write('column=' + str(col) + '\n')
                        vmd.write('scale=' + str(scale) + '\n')
                        vmd.write('frame_count=' + str(frame_count) + '\n')
                        vmd.close()
                    print('%f' % (int(frame_count) / float(video_time)))
            elif type(i) == bytes:
                # video data
                ved.write(struct.pack('>I', len(i)))
                ved.write(i)
            elif i == None:
                q_timestamp.put(None)
                break
            
    except KeyboardInterrupt:
        ved.close()
        vmd.close()



def timestamp(q, vhd_path):
    HOST = '192.168.0.1'
    PORT = 21740
    BUFSIZE = 1024
    ADDR = (HOST, PORT)

    try:
        while True:
            i = q.get()
            if i == None: break
            name, digest = i[:19], i[19:]
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientSocket.settimeout(1)
            with open(os.path.join(vhd_path, name) + '.vhd', 'w') as vhd:
                try:
                    clientSocket.connect(ADDR)
                except Exception as e:
##                    print('  Server is not connected(%s:%s)' % ADDR)
                    vhd.write('digest=' + digest + '\n')
                    continue
                
                clientSocket.send(digest.encode('utf-8'))
                response = clientSocket.recv(BUFSIZE)
                time, sign = response.decode('utf-8').split('\n', 1)
                vhd.write('digest=' + digest + '\n')
                vhd.write('time=' + time + '\n')
                vhd.write('sign=' + sign + '\n')
    except Exception as e:
        print(e)
        clientSocket.close()

        

class Stream(io.BytesIO):
    def __init__(self, q, video_time, row, col, scale, record_count):
        self.q = q

        self.video_time = video_time
        self.row = row
        self.col = col
        self.scale = scale

        self.time = time()
        
        self.q.put('0' + strftime('%Y-%m-%d_%H:%M:%S', localtime()))
        self.hash = hashlib.new('sha256')
        self.count = 0
        
        self.recording = True
        self.record_count = record_count



    def write(self, s):
        if not self.recording: return
        if time() - self.time > self.video_time:
            self.time += self.video_time
            
            self.q.put('1' + str(self.count) + ',' + self.hash.hexdigest())
            self.record_count -= 1

            if self.record_count <= 0:
                self.recording = False
                return
            
            self.q.put('0' + strftime('%Y-%m-%d_%H:%M:%S', localtime()))
            self.hash = hashlib.new('sha256')
            self.count = 0
        
        self.q.put(s)
        
        frame = decode(np.fromstring(s, dtype=np.uint8))
        
        row, col, scale = self.row, self.col, self.scale
        h, w = frame.shape[:2]
        
        for r in range(row):
            for c in range(col):
                x1, y1 = w * c // col, h * r // row
                x2, y2 = w * (c + 1) // col, h * (r + 1) // row
                shrinked = cv2.resize(getROI(frame, x1, y1, x2, y2), None, fx=1.0 / scale, fy=1.0 / scale, interpolation=cv2.INTER_NEAREST)
                self.hash.update(bytes(shrinked))

        self.count += 1



    def flush(self):
        self.q.put(None)







# main
if __name__ == '__main__':
    # python capture_2.py (video time) (row) (column) (scale)

    
    # video encoding file path
    ved_path = '../data/video/'
    
    # video meta data file path
    vmd_path = '../data/meta/'
    
    # video hash data file path
    vhd_path = '../data/fingerprint/'

    
    if len(sys.argv) == 5:
        video_time = int(sys.argv[1])
        row = int(sys.argv[2])
        col = int(sys.argv[3])
        scale = float(sys.argv[4])
        
        _realtime_processing(ved_path, vmd_path, vhd_path, video_time, row, col, scale)

    else:
        print('python realtime_processing.py (video time) (row) (column) (scale)')

















    
