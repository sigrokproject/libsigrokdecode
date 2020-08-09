##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019-2020 Philip Åkesson <philip.akesson@gmail.com>
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

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'sdq'
    name = 'SDQ'
    longname = 'Texas Instruments SDQ'
    desc = 'Texas Instruments SDQ. The SDQ protocol is also used by Apple.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'sdq', 'name': 'SDQ', 'desc': 'Single wire SDQ data line.'},
    )
    options = (
        {'id': 'bitrate', 'desc': 'Bit rate', 'default': 98425},
    )
    annotations = (
        ('bit', 'Bit'),
        ('byte', 'Byte'),
        ('break', 'Break'),
    )
    annotation_rows = (
        ('bits', 'Bits', (0,)),
        ('bytes', 'Bytes', (1,)),
        ('breaks', 'Breaks', (2,)),
    )

    def puts(self, data):
        self.put(self.startsample, self.samplenum, self.out_ann, data)

    def putetu(self, data):
        self.put(self.startsample, self.startsample + int(self.bit_width), self.out_ann, data)

    def putbetu(self, data):
        self.put(self.bytepos, self.startsample + int(self.bit_width), self.out_ann, data)

    def bits2num(self, bitlist):
        number = 0
        for i in range(len(bitlist)):
            number += bitlist[i] * 2**i
        return number

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.state = 'INIT'
        self.startsample = 0
        self.bits = []
        self.bytepos = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            self.bit_width = float(self.samplerate) / float(self.options['bitrate'])
            self.half_bit_width = self.bit_width / 2.0
            self.break_threshold = self.bit_width * 1.2 # Break if the line is low for longer than this

    def handle_bit(self, bit):
        self.bits.append(bit)
        self.putetu([0, ['Bit: %d' % bit, '%d' % bit]])

        if len(self.bits) == 8:
            byte = self.bits2num(self.bits)
            self.putbetu([1, ['Byte: %#04x' % byte, '%#04x' % byte]])
            self.bits = []
            self.bytepos = 0
    
    def handle_break(self):
        self.puts([2, ['Break', 'BR']])
        self.bits = []
        self.startsample = self.samplenum
        self.bytepos = 0

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            if self.state == 'INIT':
                sdq, = self.wait({0: 'h'}) # Wait until the line is high before starting
                self.state = 'DATA'

            elif self.state == 'DATA':
                sdq, = self.wait({0: 'f'}) # Falling edge

                self.startsample = self.samplenum
                if self.bytepos == 0:
                    self.bytepos = self.samplenum

                sdq, = self.wait({0: 'r'}) # Rising edge

                delta = self.samplenum - self.startsample
                if delta > self.break_threshold:
                    self.state = 'BREAK'
                elif delta > self.half_bit_width:
                    self.handle_bit(0)
                else:
                    self.handle_bit(1)

            elif self.state == 'BREAK':
                self.handle_break()
                self.state = 'DATA'

