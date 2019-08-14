##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Comlab AG
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
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from common.srdhelper import bitpack

NUM_CHANNELS = 12

'''
OUTPUT_PYTHON format:

Packet:
[<item>, <itembitsize>]

<item>:
 - A single item (a number). It can be of arbitrary size. The max. number
   of bits in this item is specified in <itembitsize>.

<itembitsize>:
 - The size of an item (in bits). For a 4-bit parallel bus this is 4,
   for a 16-bit parallel bus this is 16, and so on.
'''

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'vector_slicer'
    name = 'vector slicer'
    longname = 'vector slicer'
    desc = 'Take a slice of a vector.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['vector_slice']
    tags = ['VectorSlicer']
    optional_channels = tuple([{'id': 'd%d' % i, 'name': 'D%d' % i, 'desc': 'Data line %d' % i} for i in range(NUM_CHANNELS)])
    options = (
        {'id': 'index',  'desc': 'index in vector of bottom (lsb) bit',           'default': 0},
        {'id': 'length', 'desc': 'number of bits in vector to decode as integer', 'default': 8},
    )
    annotations = ()
    annotation_rows = ()

    def reset(self):
        pass

    def __init__(self):
        self.reset()

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)

        left = self.options['index']
        if left < 0:
            left = 0
        length = self.options['length']
        if length <= 1:
            raise ChannelError('length has to be at least 2')

        mask = 1
        for i in range(0, length-1):
            mask = (mask << 1) | mask;

        self.left = left
        self.length = length
        self.mask = mask

        self.first = True

    def decode_pins(self, pins, idx_strip):
        bits = [0 if idx is None else pins[idx] for idx in self.idx_channels]
        item = bitpack(bits[0:idx_strip])

        item = (item >> self.left) & self.mask

        if not self.first:
            if item != self.last_item:
                self.put(self.ss_item, self.samplenum, self.out_python, [self.last_item, self.length])
                self.ss_item = self.samplenum
        else:
            self.ss_item = self.samplenum
        self.last_item = item
        self.first = False

    def decode(self):
        # Determine which channels have input data.
        max_possible = len(self.optional_channels)
        self.idx_channels = [
            idx if self.has_channel(idx) else None
            for idx in range(max_possible)
        ]
        has_channels = [idx for idx in self.idx_channels if idx is not None]
        if not has_channels:
            raise ChannelError('At least one channel has to be supplied.')
        max_connected = max(has_channels)

        conds = [{idx: 'e'} for idx in has_channels]
        idx_strip = max_connected + 1

        # Keep processing the input stream. Assume "always zero" for
        # not-connected input lines.
        self.decode_pins(self.wait(), idx_strip)
        while True:
            self.decode_pins(self.wait(conds), idx_strip)

