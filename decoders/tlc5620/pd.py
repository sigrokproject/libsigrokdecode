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

import sigrokdecode as srd

dacs = {
    0: 'DACA',
    1: 'DACB',
    2: 'DACC',
    3: 'DACD',
}

class Decoder(srd.Decoder):
    api_version = 2
    id = 'tlc5620'
    name = 'TI TLC5620'
    longname = 'Texas Instruments TLC5620'
    desc = 'Texas Instruments TLC5620 8-bit quad DAC.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['tlc5620']
    channels = (
        {'id': 'clk', 'name': 'CLK', 'desc': 'Serial interface clock'},
        {'id': 'data', 'name': 'DATA', 'desc': 'Serial interface data'},
    )
    optional_channels = (
        {'id': 'load', 'name': 'LOAD', 'desc': 'Serial interface load control'},
        {'id': 'ldac', 'name': 'LDAC', 'desc': 'Load DAC'},
    )
    annotations = (
        ('dac-select', 'DAC select'),
        ('gain', 'Gain'),
        ('value', 'DAC value'),
        ('data-latch', 'Data latch point'),
        ('ldac-fall', 'LDAC falling edge'),
    )

    def __init__(self, **kwargs):
        self.oldpins = self.oldclk = self.oldload = self.oldldac = None
        self.datapin = None
        self.bits = []
        self.ss_dac = self.es_dac = 0
        self.ss_gain = self.es_gain = 0
        self.ss_value = self.es_value = 0
        self.dac_select = self.gain = self.dac_value = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def handle_11bits(self):
        s = ''.join(str(i) for i in self.bits[:2])
        self.dac_select = s = dacs[int(s, 2)]
        self.put(self.ss_dac, self.es_dac, self.out_ann,
                 [0, ['DAC select: %s' % s, 'DAC sel: %s' % s,
                      'DAC: %s' % s, 'D: %s' % s, s, s[3]]])

        self.gain = g = 1 + self.bits[2]
        self.put(self.ss_gain, self.es_gain, self.out_ann,
                 [1, ['Gain: x%d' % g, 'G: x%d' % g, 'x%d' % g]])

        s = ''.join(str(i) for i in self.bits[3:])
        self.dac_value = v = int(s, 2)
        self.put(self.ss_value, self.es_value, self.out_ann,
                 [2, ['DAC value: %d' % v, 'Value: %d' % v, 'Val: %d' % v,
                      'V: %d' % v, '%d' % v]])

    def handle_falling_edge_load(self):
        s, v, g = self.dac_select, self.dac_value, self.gain
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [3, ['Setting %s value to %d (x%d gain)' % (s, v, g),
                      '%s=%d (x%d gain)' % (s, v, g)]])

    def handle_falling_edge_ldac(self):
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [4, ['Falling edge on LDAC pin', 'LDAC fall', 'LDAC']])

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
