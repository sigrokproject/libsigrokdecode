##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021 Karl Palsson <karlp@etactica.com>
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included in all
## copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.

import math
import sigrokdecode as srd
from .lists import *

class Decoder(srd.Decoder):
    api_version = 3
    id = 'atm90e3x'
    name = 'ATM90E3x'
    longname = 'Microchip/Atmel ATM90E3x'
    desc = 'Poly phase multifunction energy metering IC protocol.'
    license = 'mit'
    inputs = ['spi']
    outputs = []
    tags = ['Analog/digital', 'IC', 'Sensor']
    annotations = (
        ('read', 'Register read'),
        ('write', 'Register write'),
    )
    annotation_rows = (
        ('reads', 'Reads', (0,)),
        ('writes', 'Writes', (1,)),
    )
    options = (
        { 'id': 'chip_type', 'desc': 'Chip Type', 'default': 'ATM90E36', 'values': ('ATM90E36', 'ATM90E32') },
    )

    def reset_data(self):
        self.mosi_bytes, self.miso_bytes = [], []

    def __init__(self):
        self.reset()

    def reset(self):
        self.ss_cmd, self.es_cmd = 0, 0
        self.reset_data()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        if self.options['chip_type'] == 'ATM90E36':
            self.regs = regs_atm90e36
        else:
            self.regs = regs_atm90e32

    def putx(self, data):
        self.put(self.ss_cmd, self.es_cmd, self.out_ann, data)

    def decode(self, ss, es, data):
        ptype = data[0]
        if ptype == 'CS-CHANGE':
            # CS is _required_ on ATM90E3x, and defines transactions.
            # If we transition high mid-stream, toss out our data and restart.
            cs_old, cs_new = data[1:]
            if cs_old is not None and cs_old == 0 and cs_new == 1:
                self.reset_data()
            return

        # Don't care about anything else.
        if ptype != 'DATA':
            return
        mosi, miso = data[1:]

        if len(self.mosi_bytes) == 0:
            self.ss_cmd = ss
        self.mosi_bytes.append(mosi)
        self.miso_bytes.append(miso)

        # A transfer is 4 bytes, command, 10bit register addr, plus 16bit data
        if len(self.mosi_bytes) != 4:
            return
        self.es_cmd = es

        self.cmd = self.mosi_bytes[0] << 8 | self.mosi_bytes[1] & 0xff
        read, reg = self.cmd & 0x8000, self.cmd & 0x3ff
        rblob = self.regs.get(reg)
        if not rblob:
            # we know all transactions are 32bit, just fallback name
            rblob = ("?%x?" % reg),

        valo = self.mosi_bytes[2] << 8 | self.mosi_bytes[3]
        vali = self.miso_bytes[2] << 8 | self.miso_bytes[3]

        if read:
            self.putx([0, ['%s: %#x' % (rblob[0], vali)]])
        else:
            self.putx([1, ['%s: %#x' % (rblob[0], valo)]])

        self.reset_data()
