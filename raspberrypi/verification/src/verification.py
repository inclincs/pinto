import sys
import struct
import numpy
import cv2

from pinto import PintoConfiguration, PintoMeta, PintoVideo, PintoHash, PintoBlock, error, h_pixelate



def verify(ph_name, ppv_name):
	unit = 16

	ph = PintoHash.load(PintoConfiguration.ph_path(ph_name))

	pph = PintoHash()
	ppm = PintoMeta.load(PintoConfiguration.pm_path(ppv_name))

	with PintoVideo(PintoConfiguration.pv_path(ppv_name), 'rb') as ppv:
		for data in ppv:
			index = data.find(b'\xFF\xD9')
			if index < 0: error('cannot find jpeg data')

			jpeg, pixelated = (data, None) if len(data[index+2:]) == 0 else (data[:index+2], data[index+2:])

			frame = cv2.imdecode(numpy.fromstring(jpeg, dtype=numpy.uint8), cv2.IMREAD_UNCHANGED)
			width, height = frame.shape[1::-1]

			if pixelated:
				size, pixelated = struct.unpack('>H', pixelated[:2])[0], pixelated[2:]
				pb['count'] = size // 2

				indices, encoded = pixelated[:size], pixelated[size:]
				while len(indices) > 0:
					pb['indices'].append(struct.unpack('>H', indices[:2])[0])
					indices = indices[2:]
				
				while len(encoded) > 0:
					size, encoded = struct.unpack('>I', encoded[:4])[0], encoded[4:]
					data, encoded = encoded[:size], encoded[size:]
					pb['encoded data'].append(data)

				if pb['count'] != len(pb['indices']):  error('count and number of indices is not same')
				if pb['count'] != len(pb['encoded data']): error('count and number of encoded data is not same')

				for i in range(pb['count']):
					ri, ci = pb['indices'][i] // pm.column, pb['indices'][i] % pm.column
					sx = PintoBlock.position(ci, pm.column, width, unit)
					ex = PintoBlock.position(ci + 1, pm.column, width, unit)
					sy = PintoBlock.position(ri, pm.row, height, unit)
					ey = PintoBlock.position(ri + 1, pm.row, height, unit)
					frame[sy:ey, sx:ex] = cv2.imdecode(numpy.fromstring(pb['encoded data'][i], dtype=numpy.uint8), cv2.IMREAD_UNCHANGED)
			
			i = 0
			x1, y1, x2, y2 = 0, 0, 0, 0
			for r in range(ppm.row):
				x1, y1, x2, y2 = 0, y2, 0, PintoBlock.position(r + 1, ppm.row, height, unit)
				for c in range(ppm.column):
					x1, x2 = x2, PintoBlock.position(c + 1, ppm.column, width, unit)
					if i in pb['indices']:
						pph.update(hashlib.sha1(frame[y1:y2, x1:x2]).digest())
					else:
						pph.update(hashlib.sha1(h_pixelate(frame[y1:y2, x1:x2], ppm.intensity)).digest())
					i += 1


	if ph.digest == pph.digest:
		print('same')
	else:
		print('not same')



if __name__ == '__main__':
	if len(sys.argv) == 3:
		ph_name, pixelated_name = sys.argv[1:]

		verify(ph_name, pixelated_name)
	else:
		print('python3 {file} (name) (pixelated name)'.format(file=sys.argv[0]))