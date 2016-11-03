##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Daniel Schulte <trilader@schroedingers-bit.net>
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

class Ann:
    START, STOP, PARITY, WORD = range(4)

class Decoder(srd.Decoder):
    api_version = 2
    id = 'ps2'
    name = 'PS/2'
    longname = 'PS/2'
    desc = 'PS/2 keyboard/mouse interface.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['ps2']
    channels = (
        {'id': 'clk', 'name': 'Clock', 'desc': 'Clock line'},
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('start-bit', 'Start bit'),
        ('stop-bit', 'Stop bit'),
        ('parity-bit', 'Parity bit'),
        ('word', 'Word')
    )

    def __init__(self):
        self.bits = []
        self.prev_pins = None
        self.prev_clock = None
        self.samplenum = 0
        self.ss_word = None
        self.clock_was_high = False

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def handle_bits(self, datapin):
        # Ignore non start condition bits (useful during keyboard init).
        if len(self.bits) == 0 and datapin == 1:
            return

        # If this is the first bit in a word, save its sample number.
        if len(self.bits) == 0:
            self.ss_word = self.samplenum

        self.bits.append(datapin)

        # Find all 11 bits. Start + 8 data + odd parity + stop.
        if len(self.bits) < 11:
            return

        # Extract data word.
        word = 0
        for i in range(8):
            word |= (self.bits[i + 1] << i)

        bit_start, bit_stop, bit_parity = self.bits[0], \
            self.bits[10], self.bits[9]

        bitstring = ''.join([str(i) for i in self.bits])
        parity_ok = (bin(word).count('1') + bit_parity) % 2 == 1

        if bit_start == 0 and bit_stop == 1 and parity_ok:
            self.put(self.ss_word, self.samplenum, self.out_ann, [Ann.WORD,
                     ['OK: %X (%s)' % (word, bitstring)]])
        else:
            self.put(self.ss_word, self.samplenum, self.out_ann, [Ann.WORD,
                     ['Fail: %X (%s)' % (word, bitstring)]])

        self.bits, self.ss_word = [], 0

    def find_clk_edge(self, clock_pin, data_pin):
        # Ignore sample if the clock pin hasn't changed.
        if clock_pin == self.prev_clock:
            return
        self.prev_clock = clock_pin

        # Sample on falling clock edge.
        if clock_pin == 1:
            return

        # Found the correct clock edge, now get the bits.
        self.handle_bits(data_pin)

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:
            clock_pin, data_pin = pins[0], pins[1]

            # Ignore identical samples.
            if self.prev_pins == pins:
                continue
            self.prev_pins = pins

            if clock_pin == 0 and not self.clock_was_high:
                continue
            self.clock_was_high = True

            self.find_clk_edge(clock_pin, data_pin)
