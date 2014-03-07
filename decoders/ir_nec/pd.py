##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Gump Yang <gump.yang@gmail.com>
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

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'ir_nec'
    name = 'IR NEC'
    longname = 'IR NEC'
    desc = 'NEC infrared remote control protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['ir_nec']
    probes = [
        {'id': 'ir', 'name': 'IR', 'desc': 'Data line'},
    ]
    optional_probes = []
    options = {
        'polarity': ['Polarity', 'active-low'],
    }
    annotations = [
        ['bit', 'Bit'],
        ['lc', 'Leader code'],
        ['info', 'Info'],
        ['error', 'Error'],
    ]
    annotation_rows = (
        ('bits', 'Bits', (0,)),
        ('fields', 'Fields', (1, 2, 3)),
    )

    def putx(self, data):
        self.put(self.ss_start, self.samplenum, self.out_ann, data)

    def putb(self, data):
        self.put(self.ss_bit, self.samplenum, self.out_ann, data)

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.ss_bit = self.ss_start = 0
        self.data = self.count = self.active = self.old_ir = None

    def start(self):
        # self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.active = 0 if self.options['polarity'] == 'active-low' else 1
        self.old_ir = 1 if self.active == 0 else 0

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
        self.margin = int(self.samplerate * 0.0001) - 1 # 0.1ms
        self.lc = int(self.samplerate * 0.0135) - 1 # 13.5ms
        self.rc = int(self.samplerate * 0.01125) - 1 # 11.25ms
        self.dazero = int(self.samplerate * 0.001125) - 1 # 1.125ms
        self.daone = int(self.samplerate * 0.00225) - 1 # 2.25ms

    def handle_bits(self, tick):
        ret = 0xff
        if tick in range(self.dazero - self.margin, self.dazero + self.margin):
            ret = 0
        elif tick in range(self.daone - self.margin, self.daone + self.margin):
            ret = 1

        if ret < 2:
            self.putb([0, ['%d' % ret]])
            self.data = self.data * 2 + ret
            self.count = self.count + 1

        self.ss_bit = self.samplenum
        return ret

    def data_judge(self):
        ret, name = (self.data >> 8) & (self.data & 0xff), self.state.title()
        if ret == 0:
            self.putx([2, ['%s: 0x%02x' % (name, self.data >> 8)]])
        else:
            self.putx([3, ['%s error: 0x%04x' % (name, self.data)]])
        self.data = self.count = 0
        self.ss_bit = self.ss_start = self.samplenum
        return ret

    def decode(self, ss, es, data):
        if self.samplerate is None:
            raise Exception("Cannot decode without samplerate.")
        for (self.samplenum, pins) in data:
            self.ir = pins[0]

            # Wait for an "active" edge (default: falling edge).
            if self.old_ir == self.ir or self.ir != self.active:
                self.old_ir = self.ir
                continue

            b = self.samplenum - self.ss_bit

            # State machine.
            if self.state == 'IDLE':
                if b in range(self.lc - self.margin, self.lc + self.margin):
                    self.putx([1, ['Leader code', 'Leader', 'LC', 'L']])
                    self.data = self.count = 0
                    self.state = 'ADDRESS'
                elif b in range(self.rc - self.margin, self.rc + self.margin):
                    self.putx([1, ['Repeat code', 'Repeat', 'RC', 'R']])
                    self.data = self.count = 0
                self.ss_bit = self.ss_start = self.samplenum
            elif self.state == 'ADDRESS':
                self.handle_bits(b)
                if self.count > 15:
                    self.state = 'COMMAND' if self.data_judge() == 0 else 'IDLE'
            elif self.state == 'COMMAND':
                self.handle_bits(b)
                if self.count > 15:
                    self.data_judge()
                    self.state = 'IDLE'

            self.old_ir = self.ir

