##
## This file is part of the sigrok project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
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
    id = 'spi'
    name = 'SPI'
    desc = '...desc...'
    longname = 'Serial Peripheral Interface (SPI) bus'
    longdesc = '...longdesc...'
    author = 'Gareth McMullin'
    email = 'gareth@blacksphere.co.nz'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['spi']
    probes = [
        {'id': 'sdata', 'name': 'DATA', 'desc': 'SPI data line (MISO or MOSI)'},
        {'id': 'sck', 'name': 'CLK', 'desc': 'SPI clock line'},
    ]
    options = {}

    def __init__(self):
        self.oldsck = 1
        self.rxcount = 0
        self.rxdata = 0
        self.bytesreceived = 0

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'spi')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'spi')

    def report(self):
        return 'SPI: %d bytes received' % self.bytesreceived

    def decode(self, timeoffset, duration, data):
        # HACK! At the moment the number of probes is not handled correctly.
        # E.g. if an input file (-i foo.sr) has more than two probes enabled.
        for (samplenum, (sdata, sck, x, y, z, a)) in data:

            # Sample SDATA on rising SCK
            if sck == self.oldsck:
                continue
            self.oldsck = sck
            if not sck:
                continue

            # If this is first bit, save timestamp
            if self.rxcount == 0:
                self.time = timeoffset # FIXME
            # Receive bit into our shift register
            if sdata:
                self.rxdata |= 1 << (7 - self.rxcount)
            self.rxcount += 1
            # Continue to receive if not a byte yet
            if self.rxcount != 8:
                continue
            # Received a byte, pass up to sigrok
            outdata = {'time':self.time,
                'duration':timeoffset + duration - self.time,
                'data':self.rxdata,
                'display':('%02X' % self.rxdata),
                'type':'spi',
            }
            # self.put(0, 0, self.out_proto, out_proto)
            self.put(0, 0, self.out_ann, outdata)
            # Reset decoder state
            self.rxdata = 0
            self.rxcount = 0
            # Keep stats for summary
            self.bytesreceived += 1

