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

def decode(inbuf):
	"""Counts the low->high and high->low transitions in the specified
	   channel(s) of the signal."""

	outbuf = ''

	# FIXME: Get the data in the correct format in the first place.
	inbuf = [ord(x) for x in inbuf]

	# TODO: Don't hardcode the number of channels.
	channels = 8

	oldbit = [0] * channels
	transitions = [0] * channels
	rising = [0] * channels
	falling = [0] * channels

	# print len(inbuf)
	# print type(inbuf)

	# Presets...
	oldbyte = inbuf[0]
	for i in range(channels):
		oldbit[i] = (oldbyte & (1 << i)) >> i

	# Loop over all samples.
	# TODO: Handle LAs with more/less than 8 channels.
	for s in inbuf:
		# Optimization: Skip identical bytes (no transitions).
		if oldbyte == s:
			continue
		for i in range(channels):
			curbit = (s & (1 << i)) >> i
			# Optimization: Skip identical bits (no transitions).
			if oldbit[i] == curbit:
				continue
			elif (oldbit[i] == 0 and curbit == 1):
				rising[i] += 1
			elif (oldbit[i] == 1 and curbit == 0):
				falling[i] += 1
			oldbit[i] = curbit

	# Total number of transitions is the sum of rising and falling edges.
	for i in range(channels):
		transitions[i] = rising[i] + falling[i]

	outbuf += "Rising edges:  "
	for i in range(channels):
		outbuf += str(rising[i]) + " "
	outbuf += "\nFalling edges: "
	for i in range(channels):
		outbuf += str(falling[i]) + " "
	outbuf += "\nTransitions:   "
	for i in range(channels):
		outbuf += str(transitions[i]) + " "
	outbuf += "\n"

	return outbuf

def register():
	return {
		'id': 'transitioncounter',
		'name': 'Transition counter',
		'desc': 'TODO',
		'func': 'decode',
		'inputformats': ['raw'],
		'signalnames': {}, # FIXME
		'outputformats': ['transitioncounts'],
	}

# Use psyco (if available) as it results in huge performance improvements.
try:
	import psyco
	psyco.bind(decode)
except ImportError:
	pass

