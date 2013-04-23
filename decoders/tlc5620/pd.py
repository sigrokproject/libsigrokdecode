##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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

# Texas Instruments TLC5620 protocol decoder

import sigrokdecode as srd

dacs = {
    0: 'DACA',
    1: 'DACB',
    2: 'DACC',
    3: 'DACD',
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'tlc5620'
    name = 'TI TLC5620'
    longname = 'Texas Instruments TLC5620'
    desc = 'Texas Instruments TLC5620 8-bit quad DAC.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['tlc5620']
    probes = [
        {'id': 'clk', 'name': 'CLK', 'desc': 'Serial interface clock'},
        {'id': 'data', 'name': 'DATA', 'desc': 'Serial interface data'},
    ]
    optional_probes = [
        {'id': 'load', 'name': 'LOAD', 'desc': 'Serial interface load control'},
        {'id': 'ldac', 'name': 'LDAC', 'desc': 'Load DAC'},
    ]
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.oldpins = self.oldclk = self.oldload = self.oldldac = None
        self.datapin = None
        self.bits = []
        self.ss_dac = self.es_dac = 0
        self.ss_gain = self.es_gain = 0
        self.ss_value = self.es_value = 0
        self.dac_select = self.gain = self.dac_value = None

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'tlc5620')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'tlc5620')

    def report(self):
        pass

    def handle_11bits(self):
        s = "".join(str(i) for i in self.bits[:2])
        self.dac_select = dacs[int(s, 2)]
        self.put(self.ss_dac, self.es_dac, self.out_ann,
                 [0, ['DAC select: %s' % self.dac_select]])

        self.gain = 1 + self.bits[2]
        self.put(self.ss_gain, self.es_gain, self.out_ann,
                 [0, ['Gain: x%d' % self.gain]])

        s = "".join(str(i) for i in self.bits[3:])
        self.dac_value = int(s, 2)
        self.put(self.ss_value, self.es_value, self.out_ann,
                 [0, ['DAC value: %d' % self.dac_value]])

    def handle_falling_edge_load(self):
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [0, ['Setting %s value to %d (x%d gain)' % \
                 (self.dac_select, self.dac_value, self.gain)]])

    def handle_falling_edge_ldac(self):
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [0, ['Falling edge on LDAC pin']])

    def handle_new_dac_bit(self):
        self.bits.append(self.datapin)

        # Wait until we have read 11 bits, then parse them.
        l, s = len(self.bits), self.samplenum
        if l == 1:
            self.ss_dac = s
        elif l == 2:
            self.es_dac = self.ss_gain = s
        elif l == 3:
            self.es_gain = self.ss_value = s
        elif l == 11:
            self.es_value = s
            self.handle_11bits()
            self.bits = []

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (clk, self.datapin, load, ldac) = pins, pins

            # DATA is shifted in the DAC on the falling CLK edge (MSB-first).
            # A falling edge of LOAD will latch the data.

            if self.oldload == 1 and load == 0:
                self.handle_falling_edge_load()
            if self.oldldac == 1 and ldac == 0:
                self.handle_falling_edge_ldac()
            if self.oldclk == 1 and clk == 0:
                self.handle_new_dac_bit()

            self.oldclk = clk
            self.oldload = load
            self.oldldac = ldac

