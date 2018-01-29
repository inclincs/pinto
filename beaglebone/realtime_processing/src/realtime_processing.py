import os
import time
import threading

from pinto import PintoConfiguration, PintoMeta, PintoHash, PintoBlock, PintoTimer, AbstractVideoRecorder, time2str, error, h_pixelate



class PintoVideoRecorder(AbstractVideoRecorder):

	def __init__(self, camera, path, meta):
		super().__init__()

		self.pv_path, self.pm_path, self.ph_path = path

		self.video_time = meta.video_time
		self.row = meta.row
		self.column = meta.column
		self.intensity = meta.intensity

		self.lock = threading.Lock()

		self.pv = None
		self.ph = None
		self.video_file = ''
		self.frame_count = 0


	def begin(self, video_file):
		self.pv = PintoVideo(self.pv_path(video_file), 'wb')
		self.ph = PintoHash()
		self.video_file = video_file
		self.frame_count = 0


	def write(self, data):
		with self.lock:
			if self.pv:
				self.pv.write(data)

				frame = cv2.imdecode(numpy.fromstring(data, dtype=numpy.uint8), cv2.IMREAD_UNCHANGED)
				width, height = frame.shape[1::-1]

				x1, y1, x2, y2 = 0, 0, 0, 0
				for r in range(self.row):
					x1, y1, x2, y2 = 0, y2, 0, PintoBlock.position(r + 1, self.row, height, 16)
					for c in range(self.column):
						x1, x2 = x2, PintoBlock.position(c + 1, self.column, width, 16)
						self.ph.update(hashlib.sha1(h_pixelate(frame[y1:y2, x1:x2], self.intensity)).digest())

				self.frame_count += 1


	def end(self):
		with self.lock:
			self.pv.close()

			pm = PintoMeta(self.video_time, self.row, self.column, self.intensity, self.frame_count)
			PintoMeta.save(self.pm_path(self.video_file), pm)

			PintoHash.save(self.ph_path(self.video_file), self.ph)

			self.pv = None
			self.ph = None
			self.video_file = ''
			self.frame_count = 0

def record(camera, path, meta):
	recorder = PintoVideoRecorder(camera, path, meta)
	recorder.start()

	try:
		for updated in Timer(0, meta.video_time, time.time):
			if updated: recorder.record(time2str(time.time()))
	except KeyboardInterrupt as e:
		pass

	recorder.record(None)



if __name__ == '__main__':
	if len(sys.argv) == 5:
		camera = PintoConfiguration.camera
		path = list(PintoConfiguration.path.values())
		meta = PintoMeta(*sys.argv[1:], 0)

		record(camera, path, meta)
	else:
		print('python3 {file} (video time) (row) (column) (intensity)'.format(file=sys.argv[0]))