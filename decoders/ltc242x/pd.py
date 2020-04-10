##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Analog Devices Inc.
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

channel_format = ['Channel %d', 'Ch %d', '%d']
input_voltage_format = ['%fV', '%fV', '%.6fV', '%.2fV']

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ltc242x'
    name = 'LTC242x'
    longname = 'Linear Technology LTC242x'
    desc = 'Linear Technology LTC2421/LTC2422 1-/2-channel 20-bit ADC.'
    license = 'gplv2+'
    inputs = ['spi']
    outputs = []
    tags = ['IC', 'Analog/digital']
    annotations = (
        ('channel', 'Channel'),
        ('input', 'Input voltage'),
    )
    annotation_rows = (
        ('channel', 'Channel', (0,)),
        ('input', 'Input voltage', (1,)),
    )
    options = (
        {'id': 'vref', 'desc': 'Reference voltage (V)', 'default': 1.5},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.data = 0
        self.ss, self.es = 0, 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def handle_channel(self, data):
        channel = (data & (1 << 22)) >> 22
        ann = []
        for format in channel_format:
            ann.append(format % channel)

        self.put(self.ss, self.es, self.out_ann, [0, ann])

    def handle_input_voltage(self, data):
        input_voltage = data & 0x3FFFFF
        input_voltage = -(2**21 - input_voltage)
        input_voltage = (input_voltage / 0xfffff) * self.options['vref']
        ann = []
        for format in input_voltage_format:
            ann.append(format % input_voltage)

        self.put(self.ss, self.es, self.out_ann, [1, ann])

    def decode(self, ss, es, data):
        ptype = data[0]

        if ptype == 'CS-CHANGE':
            cs_old, cs_new = data[1:]
            if cs_old is not None and cs_old == 0 and cs_new == 1:
                self.es = es
                self.data >>= 1
                self.handle_channel(self.data)
                self.handle_input_voltage(self.data)

                self.data = 0
            elif cs_old is not None and cs_old == 1 and cs_new == 0:
                self.ss = ss

        elif ptype == 'BITS':
            miso = data[2]
            for bit in reversed(miso):
                self.data = self.data | bit[0]

                self.data <<= 1
