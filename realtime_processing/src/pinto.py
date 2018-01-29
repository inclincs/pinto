import sys
import os
import datetime
import struct
import hashlib
import numpy
import cv2



time2str = lambda t: datetime.datetime.fromtimestamp(t).strftime("%Y%m%d_%H%M%S")


pixelate_mask = numpy.tile(numpy.array([0b11000000, 0b11100000, 0b11100000], dtype=numpy.uint8), (1, 10)).reshape((10, 3))
pixelate_value = numpy.zeros((10, 3), dtype=numpy.uint8)

def h_pixelate(block, intensity):
	global pixelate_mask, pixelate_value
	digest = int.from_bytes(hashlib.sha256(block.copy(order='C')).digest(), byteorder='big')
	pixelated = cv2.resize(block, (max(10, block.shape[1] // intensity), max(1, block.shape[0] // intensity)), interpolation=cv2.INTER_NEAREST)
	pixelate_value[0, 0] = (digest >> 0) 	& 0b00111111
	pixelate_value[0, 1] = (digest >> 6) 	& 0b00011111
	pixelate_value[0, 2] = (digest >> 11) 	& 0b00011111
	pixelate_value[1, 0] = (digest >> 16) 	& 0b00111111
	pixelate_value[1, 1] = (digest >> 22) 	& 0b00011111
	pixelate_value[1, 2] = (digest >> 27) 	& 0b00011111
	pixelate_value[2, 0] = (digest >> 32) 	& 0b00111111
	pixelate_value[2, 1] = (digest >> 38) 	& 0b00011111
	pixelate_value[2, 2] = (digest >> 43) 	& 0b00011111
	pixelate_value[3, 0] = (digest >> 48) 	& 0b00111111
	pixelate_value[3, 1] = (digest >> 54) 	& 0b00011111
	pixelate_value[3, 2] = (digest >> 59) 	& 0b00011111
	pixelate_value[4, 0] = (digest >> 64) 	& 0b00111111
	pixelate_value[4, 1] = (digest >> 70) 	& 0b00011111
	pixelate_value[4, 2] = (digest >> 75) 	& 0b00011111
	pixelate_value[5, 0] = (digest >> 80) 	& 0b00111111
	pixelate_value[5, 1] = (digest >> 86) 	& 0b00011111
	pixelate_value[5, 2] = (digest >> 91) 	& 0b00011111
	pixelate_value[6, 0] = (digest >> 96) 	& 0b00111111
	pixelate_value[6, 1] = (digest >> 102) 	& 0b00011111
	pixelate_value[6, 2] = (digest >> 107) 	& 0b00011111
	pixelate_value[7, 0] = (digest >> 112) 	& 0b00111111
	pixelate_value[7, 1] = (digest >> 118) 	& 0b00011111
	pixelate_value[7, 2] = (digest >> 123) 	& 0b00011111
	pixelate_value[8, 0] = (digest >> 128) 	& 0b00111111
	pixelate_value[8, 1] = (digest >> 134) 	& 0b00011111
	pixelate_value[8, 2] = (digest >> 139) 	& 0b00011111
	pixelate_value[9, 0] = (digest >> 144) 	& 0b00111111
	pixelate_value[9, 1] = (digest >> 150) 	& 0b00011111
	pixelate_value[9, 2] = (digest >> 155) 	& 0b00011111
	nb[0, :10, :] = (nb[0, :10, :] & pixelate_mask) | pixelate_value
	return nb


def error(message):
	print('error: {message}'.format(message=message))
	exit(1)


class AbstractVideoRecorder(threading.Thread):

	def __init__(self, camera):
		super().__init__()

		self.resolution = (camera['width'], camera['height'])
		self.framerate = camera['framerate']
		self.format = camera['format']

		self.queue = Queue()
		

	def run(self):
		with picamera.PiCamera() as camera:
			camera.resolution = self.resolution
			camera.framerate = self.framerate

			camera.start_recording(self, format=self.format)

			while True:
				video_file = self.queue.get()
				if not video_file: break

				self.begin(video_file)

				while self.queue.qsize() == 0: camera.wait_recording(0.1)
				
				self.end()

			camera.stop_recording()


	def begin(self, video_file):
		raise Exception()
		exit(1)


	def write(self, data):
		raise Exception()
		exit(1)


	def end(self):
		raise Exception()
		exit(1)


	def record(self, video_file):
		self.queue.put(video_file)


class PintoDetect:
	face = lambda frame, cascade: list(cascade.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE))
	license_plate = lambda frame, cascade: list(cascade.detectMultiScale(frame, scaleFactor=1.3, minNeighbors=5, minSize=(60, 10), flags=cv2.CASCADE_DO_CANNY_PRUNING))

	cascades = [ cv2.CascadeClassifier(x) for x in [ 'xml/face.xml', 'xml/eu.xml', 'xml/kr.xml' ] ]
	functions = [ face, license_plate, license_plate ]
	modes = {
		'none': [],
		'lp': [ (functions[x], cascades[x]) for x in (1, 2) ],
		'face': [ (functions[x], cascades[x]) for x in (0, ) ],
		'all': [ (functions[x], cascades[x]) for x in (0, 1, 2) ]
	}


class PintoBlock:
	position = lambda pb_i, pb_n, px_n, jb_u: math.floor(pb_i * px_n / pb_n / jb_u) * jb_u
	index = lambda jb_i, jb_n, pb_n: abs(pb_n - 1 - (jb_n - 1 - (jb_i % jb_n) + (jb_i // jb_n) * jb_n) * pb_n // jb_n)


class PintoHash:

	def __init__(self, digest=None, time=None, sign=None):
		self.hash = hashlib.new('sha1')
		self.digest = digest
		self.time = time
		self.sign = sign

	def __repr__(self):
		return str(self.__dict__)


	def update(self, data):
		self.hash.update(data)
		self.digest = self.hash.hexdigest()
		

	def timestamp(self):
		self.digest = self.hash.hexdigest()

		# connect timestamp server
		client = socket.socket()
		client.connect(('127.0.0.1', 9999))

		# send digest to timestamp server
		client.send(self.digest)

		# receive time, sign from timestamp server
		self.time = client.read(10)
		self.time = time2str(time.time())
		self.sign = client.read(32)
		self.sign = ''

		# disconnect
		client.close()


	@staticmethod
	def load(name):
		data = {}

		with open('{name}.ph'.format(name=name), 'r') as ph:
			while True:
				line = ph.readline()
				if not line: break

				key, value = line.strip().split('=')
				data[key] = value

		order = { 'digest': str, 'time': str, 'sign': str }
		arguments = [ v(data[k]) for k, v in order.items() ]

		return PintoHash(*arguments)

	@staticmethod
	def save(name, hash):
		with open('{name}.ph'.format(name=name), 'w') as ph:
			hash.timestamp()
			data = [ '{key}={value}'.format(key=k, value=v) for k, v in hash.__dict__.items() if k in ['digest', 'time', 'sign'] ]
			ph.write('\n'.join(data))


class PintoMeta:
	
	def __init__(self, video_time, row, column, intensity, frame_count):
		self.video_time = int(video_time)
		self.row = int(row)
		self.column = int(column)
		self.intensity = float(intensity)
		self.frame_count = int(frame_count)

	def __repr__(self):
		return str(self.__dict__)


	@staticmethod
	def load(name):
		data = {}

		with open('{name}.pm'.format(name=name), 'r') as pm:
			while True:
				line = pm.readline()
				if not line: break

				key, value = line.strip().split('=')
				data[key] = value

		if 'scale' in data: data['intensity'] = data['scale']

		order = { 'video_time': int, 'row': int, 'column': int, 'intensity': float, 'frame_count': int }
		arguments = [ v(data[k]) for k, v in order.items() ]

		return PintoMeta(*arguments)

	@staticmethod
	def save(name, meta):
		with open('{name}.pm'.format(name=name), 'w') as pm:
			data = [ '{key}={value}'.format(key=k, value=v) for k, v in meta.__dict__.items() ]
			pm.write('\n'.join(data))


class PintoVideo:

	def __init__(self, name, mode):
		self.name = name
		self.mode = mode
		self.file = open('{name}.pv'.format(name=self.name), self.mode)

	def __repr__(self):
		return 'Pinto Video: {name}.pv'.format(name=self.name)

	def __enter__(self):
		return self

	def __exit__(self, type, value, trackback):
		self.close()

	def __iter__(self):
		return self

	def __next__(self):
		data = self.read()
		if not data: raise StopIteration()
		return data


	def read(self):
		if self.mode != 'rb': raise Exception('mode is not \'rb\'')

		size = self.file.read(4)
		if not size: return None

		return None if not size else self.file.read(int.from_bytes(size, byteorder='big'))

	def write(self, data):
		if self.mode != 'wb': raise Exception('mode is not \'wb\'')

		self.file.write(struct.pack('>I', len(data)) + data)

	def close(self):
		self.file.close()


class PintoTimer:

	def __init__(self, target, interval, time_func):
		self.start_time = time_func()
		self.end_time = self.start_time + target
		self.intermediate_time = self.start_time + interval
		self.interval = interval
		self.time_func = time_func

	def __iter__(self):
		return self

	def __next__(self):
		if self.expired(): raise StopIteration()
		return self.update()


	def update(self):
		if self.time_func() > self.intermediate_time:
			self.intermediate_time += self.interval
			return True
		return False

	def expired(self):
		return self.end_time == self.start_time or self.end_time < self.intermediate_time


class PintoConfiguration:

	pinto_path = '.'

	pv_path = lambda n: os.path.join(pinto_path, 'video', n)
	pm_path = lambda n: os.path.join(pinto_path, 'meta', n)
	ph_path = lambda n: os.path.join(pinto_path, 'hash', n)

	path = { 'pv': pv_path, 'pm': pm_path, 'ph': ph_path }

	camera = { 'width': 1280, 'height': 720, 'framerate': 30, 'format': 'mjpeg' }


	@staticmethod
	def load():
		with open(os.path.join(pinto_path, 'config.txt'), 'r') as config:
			while True:
				line = config.readline()
				if not line: break

				key, value = line.strip().split('=')
				data[key] = value

			if 'scale' in data: data['intensity'] = data['scale']

			order = { 'path': str, 'video_time': int, 'row': int, 'column': int, 'intensity': float }
		return { k: v(data[k]) for k, v in order.items() }

	@staticmethod
	def save(data):
		with open(os.path.join(pinto_path, 'config.txt'), 'w') as config:
			config.write('\n'.join([ '{key}={value}'.format(key=k, value=v) for k, v in data.__dict__.items() ]))


if __name__ == '__main__':
	if len(sys.argv) == 2 and sys.argv[1] == 'install':
		os.makedirs('data/video')
		os.makedirs('data/meta')
		os.makedirs('data/hash')
		os.makedirs('src')
		os.makedirs('src/xml')

		os.system('mv *.xml src/xml')
		os.system('mv *.py src')

		configuration = { 'path': os.path.dirname(os.path.abspath(__file__)), 'video_time': 60, 'row': 10, 'column': 10, 'intensity': 12 }

		with open('config.txt', 'w') as config:
			config.write('\n'.join([ '{key}={value}'.format(key=k, value=v) for k, v in configuration.__dict__.items() ]))

	elif len(sys.argv) == 3 and sys.argv[1] == 'configure':
		if sys.argv[2] == 'list':
			print(PintoConfiguration.load())
		else:
			key, value = line.strip().split('=')
			if key in [ 'path', 'video_time', 'row', 'column', 'intensity' ] and len(value) > 0:
				data = PintoConfiguration.load()
				data[key] = value
				PintoConfiguration.save(data)
			else:
				print('cannot configure it')
	else:
		print('python3 {file} install'.format(file=sys.argv[0]))
		print('python3 {file} configure list'.format(file=sys.argv[0]))
		print('python3 {file} configure (key)=(value)'.format(file=sys.argv[0]))