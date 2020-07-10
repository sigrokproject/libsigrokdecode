##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Uli Huber
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

import re
import sigrokdecode as srd

ann_hdrbit, ann_databit, ann_paritybit, ann_bitlegende, ann_pos, ann_warning = range(6)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'xy2-100'
    name = 'XY2-100'
    longname = 'XY2-100 Galvo Protocol'
    desc = 'Serial protocol for Galvo positioning'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'clk', 'name': 'D0', 'desc': 'Clock','default': 0},
        {'id': 'sync', 'name': 'D1', 'desc': 'Sync','default': 1},
        {'id': 'PosX', 'name': 'D2', 'desc': 'X/Y/Z','default': 2},
    )

    annotations = (
        ('hdrbit', 'Header bit'),
        ('databit', 'Data bit'),
        ('paritybit', 'Parity bit'),
        ('bitlegende', 'Bit Legende'),
        ('position', 'Position Data'),
        ('warning', 'Human-readable warnings'),
    )
    annotation_rows = (
        ('bits', 'Bits', (ann_hdrbit, ann_databit, ann_paritybit)),
        ('legende', 'Legende', (ann_bitlegende,)),
        ('positions', 'Position', (ann_pos,)),
        ('warnings', 'Warnings', (ann_warning,)),
    )

    def __init__(self):
        self.samplerate = None
        self.reset()

    def reset(self):
        self.hdrbits = []
        self.databits = []
        self.paritybits = []

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putbit(self, ss, es, typ, value):
        self.put(ss, es, self.out_ann, [typ, ['%s' % (value)]])

    def decode(self):
        headerstart = 0
        datastart = 0
        dataend = 0
        lastsample = 0
        while True:
            # Wait for any edge CLK  or SYNC
            clk, sync, PosX = self.wait({0: 'r'})
            bitstart = self.samplenum
            bitend = bitstart+(bitstart-lastsample)

            # start data collection
            if sync == 1:
                # wait for falling edge clk
                clk, sync, PosX = self.wait({0: 'f'})
                if len(self.hdrbits) < 3:
                    if len(self.hdrbits) == 0:
                        headerstart = bitstart
                        self.hdrbits = [(PosX, bitstart, self.samplenum)] + self.hdrbits
                        self.putbit(bitstart, bitend, ann_hdrbit, PosX)
                else:
                    if len(self.databits) == 0:
                        datastart = bitstart
                    self.databits = [(PosX, bitstart, self.samplenum)] + self.databits
                    #self.putbit(bitstart, self.samplenum+1, ann_databit, PosX)
                    self.putbit(bitstart,bitend, ann_databit, PosX)
                    dataend = bitend

            # get parity bit, calculate position
            elif sync == 0:
                clk, sync, PosX = self.wait({0: 'f'})
                self.paritybits = [PosX]
                self.putbit(dataend, bitend, ann_paritybit, PosX)
                self.put(dataend,bitend, self.out_ann, [ann_bitlegende, ['Parity' ]])
                self.put(headerstart,datastart, self.out_ann, [ann_bitlegende, ['Header' ]])
                self.put(datastart, dataend, self.out_ann, [ann_bitlegende, ['Position' ]])

                par=0
                for x in self.hdrbits:
                    par ^= x[0]&1
                positionX = 0
                stelle = 0
                for x in self.databits:
                    par ^= x[0]&1
                    if x[0]  == 1:
                        positionX = positionX + (1 << stelle)
                    stelle += 1

                self.put(datastart, dataend, self.out_ann,  [ann_pos, ['%02d' % (positionX)]])
                check = 'NOK'
                if PosX == par:
                    check = 'OK'
                self.put(dataend, bitend, self.out_ann,  [ann_pos, ['%02s' % (check)]])

                #self.put(datastart, self.samplenum, self.out_ann,
                    #[ann_warning, ['%s: %02X' % ('WARNUNG: ', 4711)]])

                self.databits = []
                self.hdrbits = []

            lastsample = bitstart
