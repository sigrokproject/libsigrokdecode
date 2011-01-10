##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

#
# I2C protocol decoder
#

#
# The Inter-Integrated Circuit (I2C) bus is a bidirectional, multi-master
# bus using two signals (SCL = serial clock line, SDA = serial data line).
#
# There can be many devices on the same bus. Each device can potentially be
# master or slave (and that can change during runtime). Both slave and master
# can potentially play the transmitter or receiver role (this can also
# change at runtime).
#
# Possible maximum data rates:
#  - Standard mode: 100 kbit/s
#  - Fast mode: 400 kbit/s
#  - Fast-mode Plus: 1 Mbit/s
#  - High-speed mode: 3.4 Mbit/s
#
# START condition (S): SDA = falling, SCL = high
# Repeated START condition (Sr): same as S
# STOP condition (P): SDA = rising, SCL = high
#
# All data bytes on SDA are exactly 8 bits long (transmitted MSB-first).
# Each byte has to be followed by a 9th ACK/NACK bit. If that bit is low,
# that indicates an ACK, if it's high that indicates a NACK.
#
# After the first START condition, a master sends the device address of the
# slave it wants to talk to. Slave addresses are 7 bits long (MSB-first).
# After those 7 bits, a data direction bit is sent. If the bit is low that
# indicates a WRITE operation, if it's high that indicates a READ operation.
#
# Later an optional 10bit slave addressing scheme was added.
#
# Documentation:
# http://www.nxp.com/acrobat/literature/9398/39340011.pdf (v2.1 spec)
# http://www.nxp.com/acrobat/usermanuals/UM10204_3.pdf (v3 spec)
# http://en.wikipedia.org/wiki/I2C
#

# TODO: Look into arbitration, collision detection, clock synchronisation, etc.
# TODO: Handle clock stretching.
# TODO: Handle combined messages / repeated START.
# TODO: Implement support for 7bit and 10bit slave addresses.
# TODO: Implement support for inverting SDA/SCL levels (0->1 and 1->0).
# TODO: Implement support for detecting various bus errors.

#
# I2C output format:
#
# The output consists of a (Python) list of I2C "packets", each of which
# has an (implicit) index number (its index in the list).
# Each packet consists of a Python dict with certain key/value pairs.
#
# TODO: Make this a list later instead of a dict?
#
# 'type': (string)
#   - 'S' (START condition)
#   - 'Sr' (Repeated START)
#   - 'AR' (Address, read)
#   - 'AW' (Address, write)
#   - 'DR' (Data, read)
#   - 'DW' (Data, write)
#   - 'P' (STOP condition)
# 'range': (tuple of 2 integers, the min/max samplenumber of this range)
#   - (min, max)
#   - min/max can also be identical.
# 'data': (actual data as integer ???) TODO: This can be very variable...
# 'ann': (string; additional annotations / comments)
#
# Example output:
# [{'type': 'S',  'range': (150, 160), 'data': None, 'ann': 'Foobar'},
#  {'type': 'AW', 'range': (200, 300), 'data': 0x50, 'ann': 'Slave 4'},
#  {'type': 'DW', 'range': (310, 370), 'data': 0x00, 'ann': 'Init cmd'},
#  {'type': 'AR', 'range': (500, 560), 'data': 0x50, 'ann': 'Get stat'},
#  {'type': 'DR', 'range': (580, 640), 'data': 0xfe, 'ann': 'OK'},
#  {'type': 'P',  'range': (650, 660), 'data': None, 'ann': None}]
#
# Possible other events:
#   - Error event in case protocol looks broken:
#     [{'type': 'ERROR', 'range': (min, max),
#	'data': TODO, 'ann': 'This is not a Microchip 24XX64 EEPROM'},
#     [{'type': 'ERROR', 'range': (min, max),
#	'data': TODO, 'ann': 'TODO'},
#   - TODO: Make list of possible errors accessible as metadata?
#
# TODO: I2C address of slaves.
# TODO: Handle multiple different I2C devices on same bus
#       -> we need to decode multiple protocols at the same time.
# TODO: range: Always contiguous? Splitted ranges? Multiple per event?
#

#
# I2C input format:
#
# signals:
# [[id, channel, description], ...] # TODO
#
# Example:
# {'id': 'SCL', 'ch': 5, 'desc': 'Serial clock line'}
# {'id': 'SDA', 'ch': 7, 'desc': 'Serial data line'}
# ...
#
# {'inbuf': [...],
#  'signals': [{'SCL': }]}
#

def decode(inbuf):
	"""I2C protocol decoder"""

	# FIXME: Get the data in the correct format in the first place.
	inbuf = [ord(x) for x in inbuf]

	# FIXME: This should be passed in as metadata, not hardcoded here.
	metadata = {
	  'numchannels': 8,
	  'signals': {
	      'scl': {'ch': 5, 'name': 'SCL', 'desc': 'Serial clock line'},
	      'sda': {'ch': 7, 'name': 'SDA', 'desc': 'Serial data line'},
	    },
	}

	out = []
	o = ack = d = ''
	bitcount = data = 0
	wr = startsample = -1
	IDLE, START, ADDRESS, DATA = range(4)
	state = IDLE

	# Get the channel/probe number of the SCL/SDA signals.
	scl_bit = metadata['signals']['scl']['ch']
	sda_bit = metadata['signals']['sda']['ch']

	# Get SCL/SDA bit values (0/1 for low/high) of the first sample.
	s = inbuf[0]
	oldscl = (s & (1 << scl_bit)) >> scl_bit
	oldsda = (s & (1 << sda_bit)) >> sda_bit

	# Loop over all samples.
	# TODO: Handle LAs with more/less than 8 channels.
	for samplenum, s in enumerate(inbuf[1:]): # We skip the first byte...
		# Get SCL/SDA bit values (0/1 for low/high).
		scl = (s & (1 << scl_bit)) >> scl_bit
		sda = (s & (1 << sda_bit)) >> sda_bit

		# TODO: Wait until the bus is idle (SDA = SCL = 1) first?

		# START condition (S): SDA = falling, SCL = high
		if (oldsda == 1 and sda == 0) and scl == 1:
			o = {'type': 'S', 'range': (samplenum, samplenum),
			     'data': None, 'ann': None},
			out.append(o)
			state = ADDRESS
			bitcount = data = 0

		# Data latching by transmitter: SCL = low
		elif (scl == 0):
			pass # TODO

		# Data sampling of receiver: SCL = rising
		elif (oldscl == 0 and scl == 1):
			if startsample == -1:
				startsample = samplenum
			bitcount += 1

			# out.append("%d\t\tRECEIVED BIT %d:  %d\n" % \
			# 	(samplenum, 8 - bitcount, sda))

			# Address and data are transmitted MSB-first.
			data <<= 1
			data |= sda

			if bitcount != 9:
				continue

			# We received 8 address/data bits and the ACK/NACK bit.
			data >>= 1 # Shift out unwanted ACK/NACK bit here.
			ack = (sda == 1) and 'N' or 'A'
			d = (state == ADDRESS) and (data & 0xfe) or data
			if state == ADDRESS:
				wr = (data & 1) and 1 or 0
				state = DATA
			o = {'type': state,
			     'range': (startsample, samplenum - 1),
			     'data': d, 'ann': None}
			if state == ADDRESS and wr == 1:
				o['type'] = 'AW'
			elif state == ADDRESS and wr == 0:
				o['type'] = 'AR'
			elif state == DATA and wr == 1:
				o['type'] = 'DW'
			elif state == DATA and wr == 0:
				o['type'] = 'DR'
			out.append(o)
			o = {'type': ack, 'range': (samplenum, samplenum),
			     'data': None, 'ann': None}
			out.append(o)
			bitcount = data = startsample = 0
			startsample = -1

		# STOP condition (P): SDA = rising, SCL = high
		elif (oldsda == 0 and sda == 1) and scl == 1:
			o = {'type': 'P', 'range': (samplenum, samplenum),
			     'data': None, 'ann': None},
			out.append(o)
			state = IDLE
			wr = -1

		# Save current SDA/SCL values for the next round.
		oldscl = scl
		oldsda = sda

	# FIXME: Just for testing...
	return str(out)

def register():
	return {
		'id': 'i2c',
		'name': 'I2C',
		'desc': 'Inter-Integrated Circuit (I2C) bus',
		'inputformats': ['raw'],
		'signalnames':  {
				'SCL': 'Serial clock line',
				'SDA': 'Serial data line',
				},
		'outputformats': ['i2c'],
	}

# Use psyco (if available) as it results in huge performance improvements.
try:
	import psyco
	psyco.bind(decode)
except ImportError:
	pass

