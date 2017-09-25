import os



# filename
def filename(file):
    return os.path.basename(file)



# ext
def ext(file, default):
    path, ext = os.path.splitext(file)
    if ext != default:
        file = '{path}.{ext}'.format(path=path, ext=default)
    return file



# usage
def usage(name, func, param):
    print('usage:')
    for i in range(len(func)):
        print('python3 {name}.py {func} {param}'.format(name=name, func=func[i], param=param[i]))



# ROI
def setROI(image, x1, y1, x2, y2, roi):
    image[y1:y2, x1:x2] = roi


def getROI(image, x1, y1, x2, y2):
    return image[y1:y2, x1:x2]



# parse
def parse(data):
    parsed = {}

    for l in data.splitlines():
        word = l.split('=', 1)
        if len(word) < 2: continue
        parsed[word[0]] = word[1]

    return parsed
