import cv2
import numpy as np

from time import time


# blur all
def blur_all(image, row, col, scale, blur):
    h, w = image.shape[:2]
    
    nw, nh = w // scale, h // scale
    bw, bh = w // col, h // row

    blurred = np.zeros((nh, nw, 3), np.uint8)
    for c in range(col):
        for r in range(row):
            x1, y1 = c * bw, r * bh
            x2, y2 = x1 + bw, y1 + bh
            if x2 > w: x2 = w
            if y2 > h: y2 = h
            roi = getROI(image, x1, y1, x2, y2)
            shrinked = blur(roi, scale, True)
            setROI(blurred, x1 // scale, y1 // scale, x2 // scale, y2 // scale, shrinked)
    return blurred

# blur part
def blur_part(image, indices, row, col, scale):
    h, w = image.shape[:2]
    nw, nh = w // scale, h // scale
    bw, bh = w // col, h // row

    blurred = np.zeros((nh, nw, 3), np.uint8)
    for i in indices:
        r, c = i // col, i % col
        x1, y1 = c * bw, r * bh
        x2, y2 = x1 + bw, y1 + bh
        if x2 > w: x2 = w
        if y2 > h: y2 = h
        roi = getROI(image, x1, y1, x2, y2)
        shrinked = blur(roi, scale)
        setROI(blurred, x1, y1, x2, y2, shrinked)
    return blurred

# scale
def scale(image, scale_factor):
    return cv2.resize(image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_NEAREST)

# blur
def blur(image, scale_factor, shrink=False):
    s = scale(image, 1 / (scale_factor ** 2))
    print(s.shape)
    return scale(s, scale_factor if shrink else scale_factor ** 2)
            
