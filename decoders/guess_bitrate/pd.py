##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2013-2016 Uwe Hermann <uwe@hermann-uwe.de>
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
    id = 'guess_bitrate'
    name = 'Guess bitrate'
    longname = 'Guess bitrate/baudrate'
    desc = 'Guess the bitrate/baudrate of a UART (or other) protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['guess_bitrate']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('bitrate', 'Bitrate / baudrate'),
    )

    def putx(self, data):
        self.put(self.ss_edge, self.samplenum, self.out_ann, data)

    def __init__(self):
        self.ss_edge = None
        self.first_transition = True
        self.bitwidth = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            # Wait for any transition/edge on the data line.
            self.wait({0: 'e'})

            # Get the smallest distance between two transitions
            # and use that to calculate the bitrate/baudrate.
            if self.first_transition:
                self.ss_edge = self.samplenum
                self.first_transition = False
            else:
                b = self.samplenum - self.ss_edge
                if self.bitwidth is None or b < self.bitwidth:
                    self.bitwidth = b
                    bitrate = int(float(self.samplerate) / float(b))
                    self.putx([0, ['%d' % bitrate]])
                self.ss_edge = self.samplenum
