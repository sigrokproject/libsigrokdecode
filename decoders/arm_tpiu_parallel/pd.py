##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021 Steffen Mauch <steffen.mauch@gmail.com>
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

class Decoder(srd.Decoder):
    api_version = 3
    id = 'arm_tpiu_parallel'
    name = 'ARM TPIU Parallel'
    longname = 'ARM Trace Port Interface Unit'
    desc = 'Transform parallel bit stream (trace port) into TPIU formatted trace data for TPIU decoder.'
    license = 'gplv2+'
    inputs = ['parallel']
    outputs = ['uart']  # Emulate uart output so that arm_tpiu can stack.
    tags = ['Debug/trace']
    annotations = (
        ('uart', 'Stream data'),
    )
    annotation_rows = (
        ('streams', 'info', (0,)),
    )
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.buf = []
        self.foundSync = 0
        self.bitCnt = 0
        self.lastPos = 0
        return
    
    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
    
    def process_frame(self, buf):
        return
        
    def bitsToBytes(self, a):
        a = [0] * (8 - len(a) % 8) + a # adding in extra 0 values to make a multiple of 8 bits
        s = ''.join(str(x) for x in a)[::-1] # reverses and joins all bits
        returnInts = []
        for i in range(0,len(s),8):
             returnInts.append(int(s[i:i+8],2)) # goes 8 bits at a time to save as ints
        return returnInts[0]
    
    def show( self, ss, es, data):
        self.put(ss, es, self.out_ann, [0, ['0x%02x' % data]])
        self.put(ss, es, self.out_python, ['DATA', 0, (data, True)])
        
    def decode(self, ss, es, data):
        ptype, bit = data
        if ptype != 'ITEM':
            return
        
        len = es-ss
        # cope with 1, 2 and 4 bit wide traceport configuration
        bitList = [1 if bit[0] & (1 << n) else 0 for n in range(bit[1])]
        self.buf = self.buf[(-32+bit[1]):] + bitList
        if self.buf == [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0]:
            self.put(es-1, es, self.out_ann, [0, ['SYNCFRAME']])
            if self.foundSync == 1:
                byte = self.bitsToBytes( self.buf[-8:] )
                self.show(self.lastPos, es-1, byte)
            self.foundSync = 1
            self.bitCnt = 0
            self.lastPos = es
        elif self.foundSync == 1:
            self.bitCnt = self.bitCnt + 1
            if self.bitCnt == 8:
                self.bitCnt = 0
                byte = self.bitsToBytes( self.buf[-8:] )
                self.show(self.lastPos, es, byte)
                self.lastPos = es
        