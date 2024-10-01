##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021 Piotr Esden-Tempski <piotr@esden.net>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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
from functools import reduce

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'rgb_led_apa102'
    name = 'RGB LED (APA102)'
    longname = 'RGB LED string decoder (APA102)'
    desc = 'RGB LED string protocol (APA102).'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = []
    tags = ['Display', 'IC']
    channels = (
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock'},
        {'id': 'dat', 'name': 'DAT', 'desc': 'Data'},
    )
    annotations = (
        ('bit', 'Raw Bits'),
        ('start', 'Start Frame'),
        ('led', 'LED Frame'),
        ('end', 'End Frame'),
        ('glob', 'Global Brighness'),
        ('rgb', 'RGB'),
    )
    annotation_rows = (
        ('bits', 'Raw Bits', (0,)),
        ('frames', 'Frames', (1, 2, 3)),
        ('vals', 'Global Brightness and RGB values', (4, 5)),
    )
    binary = (
        ('all', 'All binary data'),
        ('led', 'Global Brightness and RGB data'),
        ('glob', 'Global Brightness'),
        ('rgb', 'RGB Data'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.bits = []
        self.frame = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def decode(self):
        bits = []
        word = 0x00000000
        synced = False
        while True:
            # Wait for the clock rising edge
            (clk, dat) = self.wait({0: 'r'})

            # Annotate raw bits
            if bits:
                self.put(bits[-1][0], self.samplenum, self.out_ann, [0, ['%d' % bits[-1][1]]])

            # Wait for first sync
            if not synced \
               and len(bits) == 32 \
               and word == 0:
                synced = True
                self.put(bits[0][0], self.samplenum, self.out_ann, [1, ['Start Frame', 'Start', 'ST', 'S']])
                self.put(bits[0][0], self.samplenum, self.out_binary, [0, word.to_bytes(4, byteorder='big')])
                bits.clear()
            elif synced and len(bits) == 32:
                if word == 0x00000000:
                        self.put(bits[0][0], self.samplenum, self.out_ann, [1, ['Start Frame', 'Start', 'ST', 'S']])
                elif 0xE0000000 <= word <= 0xFFFFFFFE:
                        # Annotations
                        self.put(bits[0][0], self.samplenum, self.out_ann, [2, ['LED Frame', 'LED', 'L']])
                        glob = '0x%02X' % ((word >> 24) & 0x1F)
                        self.put(bits[0][0], bits[8][0], self.out_ann, [4, ['Global Brightness ' + glob,  'Global ' + glob, 'Glob ' + glob, glob]])
                        rgb = '0x%06X' % ((word & 0xFF) << 16 | (word & 0xFF00) | ((word >> 16) & 0xFF))
                        self.put(bits[8][0], self.samplenum, self.out_ann, [5, ['RGB ' + rgb, rgb]])
                        # Binary data
                        glob = ((word >> 24) & 0x1F).to_bytes(1, byteorder='big')
                        self.put(bits[0][0], bits[8][0], self.out_binary, [2, glob])
                        rgb = ((word & 0xFF) << 16 | (word & 0xFF00) | ((word >> 16) & 0xFF)).to_bytes(3, byteorder='big')
                        self.put(bits[8][0], self.samplenum, self.out_binary, [3, rgb])
                        self.put(bits[0][0], self.samplenum, self.out_binary, [1, b"".join([glob, rgb])])
                elif word == 0xFFFFFFFF:
                        self.put(bits[0][0], self.samplenum, self.out_ann, [3, ['End Frame', 'End', 'E']])
                self.put(bits[0][0], self.samplenum, self.out_binary, [0, word.to_bytes(4, byteorder='big')])
                bits.clear()


            # Advance bit acquisition
            bits.append([self.samplenum, dat])
            if len(bits) > 32:
                bits.pop(0)

            word = ((word << 1) | dat) & 0xFFFFFFFF
