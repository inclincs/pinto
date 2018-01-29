import sys
import os
import io
import math
import struct
import numpy
import cv2

from functools import reduce

from pinto import PintoConfiguration, PintoMeta, PintoVideo, PintoDetect, PintoBlock, error, h_pixelate
from jpeg import Bitstream



def detect(image, row, column, mode, unit=16):
	pinto_blocks = []

	areas = []
	for m in PintoDetect.modes[mode.lower()]:
		areas += m[0](image, m[1])

	width, height = image.shape[1::-1]

	row = 1 if row < 1 else math.ceil(height / unit) if row > math.ceil(height / unit) else row
	column = 1 if column < 1 else math.ceil(width / unit) if column > math.ceil(width / unit) else column

	jrow = math.ceil(height / unit)
	jcolumn = math.ceil(width / unit)

	s = set()
	for (x, y, w, h) in areas:
		sci = PintoBlock.index(x // unit, jcolumn, column)
		sri = PintoBlock.index(y // unit, jrow, row)
		eci = PintoBlock.index((x + w - 1) // unit, jcolumn, column) + 1
		eri = PintoBlock.index((y + h - 1) // unit, jrow, row) + 1
		xv, yv = numpy.meshgrid(numpy.arange(sci, eci), numpy.arange(sri * column, eri * column, column))
		s.update((xv + yv).flatten().tolist())

	for index in list(s):
		ri, ci = index // column, index % column
		sx = PintoBlock.position(ci, column, width, unit)
		ex = PintoBlock.position(ci + 1, column, width, unit)
		sy = PintoBlock.position(ri, row, height, unit)
		ey = PintoBlock.position(ri + 1, row, height, unit)
		pinto_blocks.append({ 'index': index, 'data': image[sy:ey, sx:ex].copy() })

	return pinto_blocks

def lossless_encode(image):
	success, encoded = cv2.imencode('.png', image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
	return None if not success else encoded.tostring()

def modify(jpeg, pinto_blocks, row, column, unit=16):
	byte2int = lambda bytes: int.from_bytes(bytes, byteorder='big')
	nibble = lambda byte: (byte >> 4, byte & 0x0F)

	coefficient_lookup_table = lambda v, l: v if v >= 1 << l - 1 else v - (1 << l) + 1

	DC, AC = 0, 1
	LUMINANCE, CHROMINANCE = 0, 1
	Y = LUMINANCE
	Cb = Cr = I = Q = CHROMINANCE

	COMPONENT_ID = { 1: Y, 2: Cb, 3: Cr, 4: I, 5: Q }


	# decode information data
	jd = jpeg_data = {}

	reader = io.BytesIO(jpeg)
	while True:
		b = reader.read(1)
		if not b: break

		b = byte2int(b)
		if b == 0xFF:
			b = byte2int(reader.read(1))
			if b == 0xD8:
				jd['SOI'] = { 'offset': reader.tell()-2 }
				# print('SOI')

			elif 0xE0 <= b <= 0xEF:
				app = 'APP{APP_INDEX}'.format(APP_INDEX=(b - 0xE0))
				jd[app] = { 'offset': reader.tell()-2 }
				# print(app)
				size = byte2int(reader.read(2))

				jd[app]['data'] = reader.read(size - 2)

			elif b == 0xDB:
				if 'DQT' not in jd: jd['DQT'] = { 'offset': reader.tell()-2, 'data': {} }
				# print('DQT')
				size = byte2int(reader.read(2))
				
				while size > 2:
					qt = {}
					qt['precision'], qt['id'] = nibble(byte2int(reader.read(1)))
					qt['table'] = reader.read((qt['precision'] + 1) * 64)
					size -= 1 + (qt['precision'] + 1) * 64
					jd['DQT']['data'][qt['id']] = qt

			elif 0xC0 <= b <= 0xCF and b != 0xC4 and b != 0xC8 and b != 0xCC:
				jd['SOF'] = { 'offset': reader.tell()-2, 'data': {} }
				# print('SOF {SOF_INDEX}'.format(SOF_INDEX=(b - 0xC0)))
				size = byte2int(reader.read(2))
				
				jd['SOF']['data']['precision'] = sof_precision = byte2int(reader.read(1))
				jd['SOF']['data']['height'] = sof_height = byte2int(reader.read(2))
				jd['SOF']['data']['width'] = sof_width = byte2int(reader.read(2))
				jd['SOF']['data']['component count'] = byte2int(reader.read(1))
				jd['SOF']['data']['components'] = []
				for i in range((size - 8) // 3):
					sof_component = {}
					sof_component['component id'] = byte2int(reader.read(1)) # 1 = Y, 2 = Cb, 3 = Cr, 4 = I, 5 = Q
					sof_vertical, sof_horizontal = nibble(byte2int(reader.read(1))) # bit 0-3 vertical, 4-7 horizontal
					sof_component['sampling factors'] = { 'vertical': sof_vertical, 'horizontal': sof_horizontal }
					sof_component['quantization table id'] = byte2int(reader.read(1))
					jd['SOF']['data']['components'].append(sof_component)


			elif b == 0xC4:
				if 'DHT' not in jd: jd['DHT'] = { 'offset': reader.tell()-2, 'data': { LUMINANCE: {}, CHROMINANCE: {} } }
				# print('DHT')
				size = byte2int(reader.read(2))

				while size > 2:
					ht = {}
					ht['type'], ht['id'] = nibble(byte2int(reader.read(1)))

					ht['code count'] = [ n for n in reader.read(16) ]
					total = reduce(lambda x, y: x + y, ht['code count'])

					if total > 256: error('total code count > 256')

					ht['value'] = [ v for v in reader.read(total) ]
					ht['table'] = {}
					code = index = 0
					for depth in range(16):
						for _ in range(ht['code count'][depth]):
							ht['table'][(code, depth + 1)] = ht['value'][index]
							index += 1
							code += 1
						code <<= 1
					size -= 17 + total

					jd['DHT']['data'][ht['id']][ht['type']] = ht

			elif b == 0xDA:
				jd['SOS'] = { 'offset': reader.tell()-2, 'data': {} }
				# print('SOS')
				size = byte2int(reader.read(2))

				jd['SOS']['data']['component count'] = byte2int(reader.read(1))
				jd['SOS']['data']['components'] = []
				for i in range(jd['SOS']['data']['component count']):
					sos_component = {}
					sos_component['component id'] = byte2int(reader.read(1))
					sos_component['huffman table id'] = nibble(byte2int(reader.read(1)))[::-1] # bit 0-3 AC table, 4-7 DC table
					jd['SOS']['data']['components'].append(sos_component)

				reader.read(3) # skip 3 bytes

				jd['DATA'] = { 'offset': reader.tell(), 'data': b'' }

			elif b == 0x00:
				if 'DATA' in jd:
					jd['DATA']['data'] += bytes([0xFF])

			elif b == 0xD9:
				jd['EOI'] = { 'offset': reader.tell()-2 }
				# print('EOI')

			else:
				error('not expected marker: {0:X}'.format(read))
		else:
			if 'DATA' in jd: jd['DATA']['data'] += bytes([b])


	# decode image data
	width, height = jd['SOF']['data']['width'], jd['SOF']['data']['height']

	jrow = math.ceil(height / unit)
	jcolumn = math.ceil(width / unit)

	jb_index = lambda pb_i, pb_n, px_n, jb_u: math.floor(pb_i * px_n / pb_n / jb_u)

	s = set()
	for pinto_block in pinto_blocks:
		index = pinto_block['index']
		ri, ci = index // column, index % column
		sci = jb_index(ci, column, width, unit)
		eci = jb_index(ci + 1, column, width, unit)
		sri = jb_index(ri, row, height, unit)
		eri = jb_index(ri + 1, row, height, unit)
		xv, yv = numpy.meshgrid(numpy.arange(sci, eci), numpy.arange(sri * jcolumn, eri * jcolumn, jcolumn))
		s.update((xv + yv).flatten().tolist())
	detected = list(s)

	bs_reader = Bitstream(jd['DATA']['data'])
	bs_writer = Bitstream()
	mcus = []
	mcu = []
	du = []

	sof_components = jd['SOF']['data']['components']
	sos_components = jd['SOS']['data']['components']

	components = []
	for i in range(len(sof_components)):
		sc, fc = sos_components[i], sof_components[i]

		component = {}
		component['table'] = { t: jd['DHT']['data'][sc['huffman table id'][t]][t]['table'] for t in (DC, AC) }
		component['itable'] = { t: { v: k for k, v in component['table'][t].items() } for t in (DC, AC) }
		component['id'] = sc['component id']

		for _ in range(fc['sampling factors']['vertical'] * fc['sampling factors']['horizontal']):
			components.append(component)

	diff = { k: 0 for k in COMPONENT_ID }

	c = 0
	d = 0

	while True:
		try:
			bit = bs_reader.read()
		except: break

		c = (c << 1) | bit
		d += 1

		if len(du) == 0:
			ht = components[len(mcu)]['table'][DC]

			if (c, d) in ht:
				# DC: (length:huff) (value:dc_table)
				length = ht[(c, d)]

				if length == 0:
					value = 0
				else:
					temp = bs_reader.read(length)
					value = coefficient_lookup_table(temp, length)

				if len(mcus) in detected:
					bs_writer.write(*components[len(mcu)]['itable'][DC][0])
					diff[components[len(mcu)]['id']] += value
				else:
					if diff[components[len(mcu)]['id']] == 0:
						bs_writer.write(c, d)
						if length > 0: bs_writer.write(temp, length)
					else:
						new_value = value + diff[components[len(mcu)]['id']]
						if new_value == 0:
							bs_writer.write(*components[len(mcu)]['itable'][DC][0])
						else:
							length = int(math.log(abs(new_value), 2)) + 1
							value = new_value if new_value > 0 else new_value - 1 + (1 << length)
							bs_writer.write(*components[len(mcu)]['itable'][DC][length])
							bs_writer.write(value, length)
						diff[components[len(mcu)]['id']] = 0

				du.append(value if len(mcus) == 0 else value + mcus[-1][len(mcu)][0])

				d = c = 0
		elif len(du) < 64:
			ht = components[len(mcu)]['table'][AC]

			if (c, d) in ht:
				# AC: ((zeros, length):huff) (value:dc_table)
				if len(mcus) not in detected: bs_writer.write(c, d)

				temp = ht[(c, d)]

				if temp == 0:
					du += [0] * (64 - len(du))
				elif temp == 0xF0:
					du += [0] * 16
				else:
					zeros, length = temp >> 4, temp & 0x0F

					temp = bs_reader.read(length)
					if len(mcus) not in detected: bs_writer.write(temp, length)

					value = coefficient_lookup_table(temp, length)
					du += [0] * zeros
					du.append(value)

				d = c = 0
		if len(du) >= 64:
			if len(mcus) in detected: bs_writer.write(*components[len(mcu)]['itable'][AC][0])

			mcu.append(du)
			du = []

		if len(mcu) == len(components):
			mcus.append(mcu)
			mcu = []


	pinto_block = { 'indices': b'', 'encoded data': b'' }
	for pinto_block in pinto_blocks:
		pinto_block['indices'] += struct.pack('>H', pblock['index'])
		pinto_block['encoded data'] += struct.pack('>I', len(pblock['encoded data'])) + pblock['encoded data']
	pinto_block_data = struct.pack('>H', len(pinto_block['indices'])) + pinto_block['indices'] + pinto_block['encoded data']

	modified_jpeg = jpeg[:jd['DATA']['offset']] + bs_writer.result().replace(b'\xFF', b'\xFF\x00') + jpeg[jd['EOI']['offset']:]
	return modified_jpeg + pinto_block_data

def pixelate(pv_name, ppv_name, mode):
	pm = PintoMeta.load(PintoConfiguration.pm_path(pv_name))
	PintoMeta.save(PintoConfiguration.pm_path(ppv_name), pm)

	with PintoVideo(PintoConfiguration.pv_path(pv_name), 'rb') as pv:
		with PintoVideo(PintoConfiguration.pv_path(ppv_name), 'wb') as ppv:
			for jpeg in pv:

				# jpeg -(decode)-> image
				image = cv2.imdecode(numpy.fromstring(jpeg, dtype=numpy.int8), cv2.IMREAD_UNCHANGED)

				# image -(detect)-> pinto blocks
				pinto_blocks = detect(image, pm.row, pm.column, mode)

				# pinto block -(h pixelate)-(lossless encode)-> encoded pinto block
				for pinto_block in pinto_blocks:
					pinto_block['encoded data'] = lossless_encode(h_pixelate(pinto_block['data'], pm.intensity))

				# jpeg + pinto blocks -(erase)-(wrap)-> pixelated jpeg
				pixelated_jpeg = modify(jpeg, pinto_blocks, pm.row, pm.column) if len(pinto_blocks) > 0 else jpeg

				ppv.write(pixelated_jpeg)



if __name__ == '__main__':
	if len(sys.argv) == 4:
		pv_name, pixelated_pv_name, mode = sys.argv[1:]

		pixelate(pv_name, pixelated_pv_name, mode)
	else:
		print('python3 {file} (name) (pixelated name) (none | lp | face | all)'.format(file=sys.argv[0]))