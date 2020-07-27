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

class Pin:
    RST, CLK, IO, = range(3)

class Ann:
    BIT, ATR, CMD, DATA, RESET, = range(5)

class Bin:
    SEND_DATA, = range(1)

# CMD: [annotation class index, annotation texts for zoom levels]
proto = {
    'BIT':   [Ann.BIT,   '{bit}',],
    'ATR':   [Ann.ATR,   'Answer To Reset: {data:02x}', 'ATR: {data:02x}', '{data:02x}',],
    'CMD':   [Ann.CMD,   'Command: {data:02x}', 'Cmd: {data:02x}', '{data:02x}',],
    'DATA':  [Ann.DATA,  'Data: {data:02x}', '{data:02x}',],
    'RESET': [Ann.RESET, 'Reset', 'R',],
}

def lookup_proto_ann_txt(cmd, variables):
    ann = proto.get(cmd, None)
    if ann is None:
        return None, []
    cls, texts = ann[0], ann[1:]
    texts = [t.format(**variables) for t in texts]
    return cls, texts

class Decoder(srd.Decoder):
    api_version = 3
    id = 'sle44xx'
    name = 'SLE 44xx'
    longname = 'SLE44xx memory card'
    desc = 'SLE 4418/28/32/42 memory card serial protocol'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Memory']
    channels = (
        {'id': 'rst', 'name': 'RST', 'desc': 'Reset line'},
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock line'},
        {'id': 'io', 'name': 'I/O', 'desc': 'I/O data line'},
    )
    annotations = (
        ('bit', 'Bit'),
        ('atr', 'ATR'),
        ('cmd', 'Command'),
        ('data', 'Data exchange'),
        ('reset', 'Reset'),
    )
    annotation_rows = (
        ('bits', 'Bits', (Ann.BIT,)),
        ('fields', 'Fields', (Ann.ATR, Ann.CMD, Ann.DATA)),
        ('interrupts', 'Interrupts', (Ann.RESET,)),
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
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def putb(self, data):
        self.put(self.ss, self.es, self.out_binary, data)

    def handle_reset(self, pins):
        self.ss, self.es = self.samplenum, self.samplenum
        self.cmd = 'RESET'
        cls, texts = lookup_proto_ann_txt(self.cmd, {})
        self.putx([cls, texts])
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

        self.putb([Bin.SEND_DATA, bytes([self.databyte])])

        for bit_val, bit_ss, bit_es in self.bits:
            cls, texts = lookup_proto_ann_txt('BIT', {'bit': bit_val})
            self.put(bit_ss, bit_es, self.out_ann, [cls, texts])

        cls, texts = lookup_proto_ann_txt(self.cmd, {'data': self.databyte})
        self.putx([cls, texts])

        # Done with this packet.
        self.bitcount = self.databyte = 0
        self.bits = []

    def decode(self):
        while True:
            # Signal conditions tracked by the protocol decoder:
            # - RESET condition (R): RST = rising
            # - Incoming data (D): RST = low, CLK = rising.
            # - Command mode START: CLK = high, I/O = falling.
            # - Command mode STOP: CLK = high, I/O = rising.
            (COND_RESET, COND_DATA, COND_CMD_START, COND_CMD_STOP,) = range(4)
            conditions = [
                {Pin.RST: 'r'},
                {Pin.RST: 'l', Pin.CLK: 'r'},
                {Pin.CLK: 'h', Pin.IO: 'f'},
                {Pin.CLK: 'h', Pin.IO: 'r'},
            ]
            pins = self.wait(conditions)
            if self.matched[COND_RESET]:
                self.handle_reset(pins)
            elif self.matched[COND_DATA]:
                self.handle_data(pins)
            elif self.matched[COND_CMD_START]:
                self.handle_command(pins)
            elif self.matched[COND_CMD_STOP]:
                self.handle_command(pins)
