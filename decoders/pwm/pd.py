##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Torsten Duwe <duwe@suse.de>
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
    api_version = 2
    id = 'pwm'
    name = 'PWM'
    longname = 'Pulse-width modulation'
    desc = 'Analog level encoded in duty cycle percentage.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['pwm']
    channels = (
        {'id': 'pwm', 'name': 'PWM in', 'desc': 'Modulation pulses'},
    )
    options = (
        {'id': 'new_cycle_edge', 'desc': 'New cycle on which edge',
            'default': 'rising', 'values': ('rising', 'falling')},
    )
    annotations = (
        ('value', 'PWM value'),
    )
    binary = (
        ('raw', 'RAW file'),
    )

    def __init__(self, **kwargs):
        self.ss = self.es = -1
        self.high = 1
        self.low = 1
        self.lastedge = 0
        self.oldpin = 0
        self.startedge = 0
        self.num_cycles = 0

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_bin = self.register(srd.OUTPUT_BINARY)
        self.out_freq = self.register(srd.OUTPUT_META,
            meta=(int, 'Frequency', 'PWM base (cycle) frequency'))
        self.startedge = 0
        if self.options['new_cycle_edge'] == 'falling':
            self.startedge = 1

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def putp(self, data):
        self.put(self.ss, self.es, self.out_python, data)

    def putb(self, data):
        self.put(self.num_cycles, self.num_cycles, self.out_bin, data)

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:
            # Ignore identical samples early on (for performance reasons).
            if self.oldpin == pins[0]:
                continue

            if self.oldpin == 0: # Rising edge.
                self.low = self.samplenum - self.lastedge
            else:
                self.high = self.samplenum - self.lastedge

            if self.oldpin == self.startedge:
                self.es = self.samplenum # This interval ends at this edge.
                if self.ss >= 0: # Have we completed a hi-lo sequence?
                    self.putx([0, ["%d%%" % ((100 * self.high) // (self.high + self.low))]])
                    self.putb((0, bytes([(256 * self.high) // (self.high + self.low)])))
                self.num_cycles += 1
            else:
                # Mid-interval.
                # This interval started at the previous edge.
                self.ss = self.lastedge

            self.lastedge = self.samplenum
            self.oldpin = pins[0]
