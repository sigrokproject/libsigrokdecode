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

# TODO: Return two buffers, one with structured data for the GUI to parse
#       and display, and one with human-readable ASCII output.

def decode(inbuf):
	"""I2C protocol decoder"""

	# FIXME: This should be passed in as metadata, not hardcoded here.
	signals = (2, 5)
	channels = 8

	o = wr = ack = d = ''
	bitcount = data = 0
	IDLE, START, ADDRESS, DATA = range(4)
	state = IDLE

	# Get the bit number (and thus probe index) of the SCL/SDA signals.
	scl_bit, sda_bit = signals

	# Get SCL/SDA bit values (0/1 for low/high) of the first sample.
	s = ord(inbuf[0])
	oldscl = (s & (1 << scl_bit)) >> scl_bit
	oldsda = (s & (1 << sda_bit)) >> sda_bit

	# Loop over all samples.
	# TODO: Handle LAs with more/less than 8 channels.
	for samplenum, s in enumerate(inbuf[1:]): # We skip the first byte...
 
		s = ord(s) # FIXME

		# Get SCL/SDA bit values (0/1 for low/high).
		scl = (s & (1 << scl_bit)) >> scl_bit
		sda = (s & (1 << sda_bit)) >> sda_bit

		# TODO: Wait until the bus is idle (SDA = SCL = 1) first?

		# START condition (S): SDA = falling, SCL = high
		if (oldsda == 1 and sda == 0) and scl == 1:
			o += "%d\t\tSTART\n" % samplenum
			state = ADDRESS
			bitcount = data = 0

		# Data latching by transmitter: SCL = low
		elif (scl == 0):
			pass # TODO

		# Data sampling of receiver: SCL = rising
		elif (oldscl == 0 and scl == 1):
			bitcount += 1

			# o += "%d\t\tRECEIVED BIT %d:  %d\n" % \
			# 	(samplenum, 8 - bitcount, sda)

			# Address and data are transmitted MSB-first.
			data <<= 1
			data |= sda

			if bitcount != 9:
				continue

			# We received 8 address/data bits and the ACK/NACK bit.
			data >>= 1 # Shift out unwanted ACK/NACK bit here.
			# o += "%d\t\t%s: " % (samplenum, state)
			o += "%d\t\tTODO:STATE: " % samplenum
			ack = (sda == 1) and 'NACK' or 'ACK'
			d = (state == ADDRESS) and (data & 0xfe) or data
			wr = ''
			if state == ADDRESS:
				wr = (data & 1) and ' (W)' or ' (R)'
				state = DATA
			o += "0x%02x%s (%s)\n" % (d, wr, ack)
			bitcount = data = 0

		# STOP condition (P): SDA = rising, SCL = high
		elif (oldsda == 0 and sda == 1) and scl == 1:
			o += "%d\t\tSTOP\n" % samplenum
			state = IDLE

		# Save current SDA/SCL values for the next round.
		oldscl = scl
		oldsda = sda

	return o

# This is just a draft.
def register():
	return {
		'id': 'i2c',
		'name': 'I2C',
		'desc': 'Inter-Integrated Circuit (I2C) bus',
		'func': 'decode',
		'inputformats': ['raw'],
		'signalnames':  {
				'SCL': 'Serial clock line',
				'SDA': 'Serial data line',
				},
		'outputformats': ['i2c', 'ascii'],
	}

# Use psyco (if available) as it results in huge performance improvements.
try:
	import psyco
	psyco.bind(decode)
except ImportError:
	pass

