##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Federico Cerutti <federico@ceres-c.it>
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

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>:
 - 'RESET'  (Reset/Abort condition)
 - 'ATR'    (ATR data from card)
 - 'CMD'    (Command from reader)
 - 'DATA'   (Data from card)

<pdata> is the data to/from the card
For 'RESET' <pdata> is None.
'''

# CMD: [annotation-type-index, long annotation, short annotation]
proto = {
    'RESET':           [0, 'Reset',         'R'],
    'ATR':             [1, 'ATR',           'ATR'],
    'CMD':             [2, 'Command',       'C'],
    'DATA':            [3, 'Data',          'D'],
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'sle44xx'
    name = 'SLE 44xx'
    longname = 'SLE44xx protocol'
    desc = 'SLE 4418/28/32/42 memory card serial protocol'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['sle44xx']
    channels = (
        {'id': 'rst', 'name': 'RST', 'desc': 'Reset line'},
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock line'},
        {'id': 'io', 'name': 'I/O', 'desc': 'I/O data line'},
    )
    annotations = (
        ('reset', 'Reset'),
        ('atr', 'ATR'),
        ('cmd', 'Command'),
        ('data', 'Data exchange'),
        ('bit', 'Bit'),
    )
    annotation_rows = (
        ('bits', 'Bits', (4,)),
        ('data', 'Data', (1, 2, 3)),
        ('interrupts', 'Interrupts', (0,)),
    )
    binary = (
        ('send-data', 'Send data'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.ss = self.es = self.ss_byte = -1
        self.bitcount = 0
        self.databyte = 0
        self.bits = []
        self.cmd = 'RESET'

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def putp(self, data):
        self.put(self.ss, self.es, self.out_python, data)

    def putb(self, data):
        self.put(self.ss, self.es, self.out_binary, data)

    def handle_reset(self, pins):
        self.ss, self.es = self.samplenum, self.samplenum
        cmd = 'RESET' # No need to set the global self.cmd as this command is atomic
        self.putp([cmd, None])
        self.putx([proto[cmd][0], proto[cmd][1:]])
        self.bitcount = self.databyte = 0
        self.bits = []
        self.cmd = 'ATR' # Next data bytes will be ATR

    def handle_command(self, pins):
        rst, clk, io = pins
        self.ss, self.es = self.samplenum, self.samplenum
        # If I/O is rising -> command START
        # if I/O is falling -> command STOP and response data incoming
        self.cmd = 'CMD' if (io == 0) else 'DATA'
        self.bitcount = self.databyte = 0
        self.bits = []

    # Gather 8 bits of data
    def handle_data(self, pins):
        rst, clk, io = pins

        # Data is transmitted LSB-first.
        self.databyte |= (io << self.bitcount)

        # Remember the start of the first data/address bit.
        if self.bitcount == 0:
            self.ss_byte = self.samplenum

        # Store individual bits and their start/end samplenumbers.
        # In the list, index 0 represents the LSB (SLE44xx transmits LSB-first).
        self.bits.insert(0, [io, self.samplenum, self.samplenum])
        if self.bitcount > 0:
            self.bits[1][2] = self.samplenum
        if self.bitcount == 7:
            self.bitwidth = self.bits[1][2] - self.bits[2][2]
            self.bits[0][2] += self.bitwidth

        # Return if we haven't collected all 8 bits, yet.
        if self.bitcount < 7:
            self.bitcount += 1
            return

        self.ss, self.es = self.ss_byte, self.samplenum + self.bitwidth

        self.putb([0, bytes([self.databyte])])

        for bit in self.bits:
            self.put(bit[1], bit[2], self.out_ann, [4, ['%d' % bit[0]]])

        self.putx([proto[self.cmd][0], ['%s: %02X' % (proto[self.cmd][1], self.databyte),
                   '%s: %02X' % (proto[self.cmd][2], self.databyte), '%02X' % self.databyte]])

        # Done with this packet.
        self.bitcount = self.databyte = 0
        self.bits = []

    def decode(self):
        while True:
            pins = self.wait([{0: 'r'}, {0: 'l', 1: 'r'}, {1: 'h', 2: 'f'}, {1: 'h', 2: 'r'}])
            if self.matched[0]: # RESET condition (R): RST = rising
                self.handle_reset(pins)
            elif self.matched[1]: # Incoming data (D): RST = low, CLK = rising.
                self.handle_data(pins)
            elif self.matched[2]: # Command mode START: CLK = high, I/O = falling.
                self.handle_command(pins)
            elif self.matched[3]: # Command mode STOP: CLK = high, I/O = rising.
                self.handle_command(pins)