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
    id = 'ir_nec6122'
    name = 'IR NEC 6122'
    longname = '1-Wire Infrared remote controller NEC 6122'
    desc = 'Unidirectional, asynchronous serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['ir_nec6122']
    probes = [
        {'id': 'ir', 'name': 'IR', 'desc': 'Data line'},
    ]
    optional_probes = []
    options = {
        'level': ['Tirgger Level L/H', 0],
        'cnt_peroid': ['Peroid time (us)', 13500],
        'cnt_repeat': ['Repeat time (us)', 11250],
        'cnt_repeat_end': ['Repeat end time (us)', 562],
        'cnt_accuracy': ['Accuracy range (us)', 100],
        'cnt_dazero': ['Data 0 time (us)', 1125],
        'cnt_daone': ['Data 1 time (us)', 2250],
        'polarity': ['Polarity', 'active-low'],
            }
    annotations = [
        ['bit', 'Bit'],
        ['preoid', 'Preoid'],
        ['info', 'Info'],
        ['error', 'Error'],
    ]
    annotation_rows = (
        ('fields', 'Fields', (1, 2, 3, 4, 5, 6)),
        ('bits', 'Bits', (0,)),
    )

    def putx(self, data):
        self.put(self.ss_edge, self.samplenum, self.out_ann, data)

    def putx(self, data):
        self.put(self.ss_start, self.samplenum, self.out_ann, data)

    def putb(self, data):
        self.put(self.ss_bit, self.samplenum, self.out_ann, data)

    def __init__(self, **kwargs):
        self.olddata = None
        self.ss_edge = 0
        self.ss_bit = 0
        self.first_transition = True
        self.bitwidth = None
        self.state = 'IDLE'
        self.data = 0;
        self.count = 0;
        self.ss_start = 0
        self.act_polar = 0

    def start(self):
        # self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.act_polar = 1 if self.options['polarity'] == 'active-low' else 0
        self.old_ir = self.act_polar 

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
        samplerate = float(self.samplerate)

        x = float(self.options['cnt_accuracy']) / 1000000.0
        self.margin = int(samplerate * x) - 1
        x = float(self.options['cnt_peroid']) / 1000000.0
        self.preoid = int(samplerate * x) - 1
        x = float(self.options['cnt_repeat']) / 1000000.0
        self.repeat = int(samplerate * x) - 1
        x = float(self.options['cnt_repeat_end']) / 1000000.0
        self.repeat_end = int(samplerate * x) - 1
        x = float(self.options['cnt_dazero']) / 1000000.0
        self.dazero = int(samplerate * x) - 1
        x = float(self.options['cnt_daone']) / 1000000.0
        self.daone = int(samplerate * x) - 1
        x = float(10000) / 1000000.0
        self.end = int(samplerate * x) - 1

    def handle_bits(self, tick):
        ret = 0xff
        if tick in range(self.dazero - self.margin,
                self.dazero + self.margin):
            ret = 0
        elif tick in range(self.daone - self.margin,
                self.daone + self.margin):
            ret = 1

        if ret < 2:
            self.putb([0, ['%d' % ret]])
            self.data = self.data * 2 + ret
            self.count = self.count + 1

        self.ss_bit = self.samplenum
        return ret;

    def data_judge(self, name):
        buf = int((self.data & 0xff00) / 0x100)
        nbuf = int(self.data & 0xff)
        ret = buf & nbuf
        if ret == 0:
            self.putx([2, ['%s: 0x%02x' % (name, buf)]])
        else:
            self.putx([3, ['%s Error: 0x%04x' % (name, self.data)]])
            
        self.data = self.count = 0
        self.ss_bit = self.ss_start = self.samplenum
        return ret

    def decode(self, ss, es, data):
        if self.samplerate is None:
            raise Exception("Cannot decode without samplerate.")
        for (self.samplenum, pins) in data:
            self.ir = pins[0]
            
            # Wait for any edge (rising or falling).
            if self.old_ir == self.ir:
                continue

            if self.old_ir == self.act_polar:
                b = self.samplenum - self.ss_bit
                # State machine.
                if self.state == 'IDLE':
                    if b in range(self.preoid - self.margin, 
                            self.preoid + self.margin):
                        self.putx([1, ['Preoid', 'Pre', 'P']])
                        self.data = self.count = 0
                        self.state = 'ADDRESS'
                    elif b in range(self.repeat - self.margin,
                            self.repeat + self.margin):
                        self.putx([1, ['Repeat', 'Rep', 'R']])
                        self.data = self.count = 0
                    self.ss_bit = self.ss_start = self.samplenum
                elif self.state == 'ADDRESS':
                    self.handle_bits(b)
                    if self.count > 15:
                        if self.data_judge(self.state) == 0:
                            self.state = 'CODE'
                        else:
                            self.state = 'IDLE'
                elif self.state == 'CODE':
                    self.handle_bits(b)
                    if self.count > 15:
                        self.data_judge(self.state)
                        self.state = 'IDLE'

            self.old_ir = self.ir

