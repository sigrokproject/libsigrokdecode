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

import sigrok

class Sample():
    def __init__(self, data):
        self.data = data
    def probe(self, probe):
        s = self.data[int(probe / 8)] & (1 << (probe % 8))
        return True if s else False

def sampleiter(data, unitsize):
    for i in range(0, len(data), unitsize):
        yield(Sample(data[i:i+unitsize]))

class Decoder(sigrok.Decoder):
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
    # Probe names with a set of defaults
    probes = {'sdata':0, 'sck':1}
    options = {}

    def __init__(self):
        self.probes = Decoder.probes.copy()
        self.oldsck = True
        self.rxcount = 0
        self.rxdata = 0
        self.bytesreceived = 0
        self.output_protocol = None
        self.output_annotation = None

    def start(self, metadata):
        self.unitsize = metadata['unitsize']
        # self.output_protocol = self.output_new(2)
        self.output_annotation = self.output_new(1)

    def report(self):
        return 'SPI: %d bytes received' % self.bytesreceived

    def decode(self, timeoffset, duration, data):
        # We should accept a list of samples and iterate...
        for sample in sampleiter(data, self.unitsize):

            sck = sample.probe(self.probes['sck'])
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
            sdata = sample.probe(self.probes['sdata'])
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
            # self.put(self.output_protocol, 0, 0, out_proto)
            self.put(self.output_annotation, 0, 0, outdata)
            # Reset decoder state
            self.rxdata = 0
            self.rxcount = 0
            # Keep stats for summary
            self.bytesreceived += 1

