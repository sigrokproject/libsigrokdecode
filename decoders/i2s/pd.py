##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012 Joel Holdsworth <joel@airwebreathe.org.uk>
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

# I2S protocol decoder

import sigrokdecode as srd

'''
Protocol output format:

Packet:
[<ptype>, <pdata>]

<ptype>, <pdata>:
 - 'DATA', [<channel>, <value>]

<channel>: 'L' or 'R'
<value>: integer
'''

class Decoder(srd.Decoder):
    api_version = 1
    id = 'i2s'
    name = 'I2S'
    longname = 'Integrated Interchip Sound'
    desc = 'Serial bus for connecting digital audio devices.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2s']
    probes = [
        {'id': 'sck', 'name': 'SCK', 'desc': 'Bit clock line'},
        {'id': 'ws', 'name': 'WS', 'desc': 'Word select line'},
        {'id': 'sd', 'name': 'SD', 'desc': 'Serial data line'},
    ]
    optional_probes = []
    options = {}
    annotations = [
        ['left', 'Left channel'],
        ['right', 'Right channel'],
        ['warnings', 'Warnings'],
    ]

    def __init__(self, **kwargs):
        self.samplerate = None
        self.oldsck = 1
        self.oldws = 1
        self.bitcount = 0
        self.data = 0
        self.samplesreceived = 0
        self.first_sample = None
        self.start_sample = None
        self.wordlength = -1

    def start(self):
        self.out_proto = self.add(srd.OUTPUT_PYTHON, 'i2s')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'i2s')

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putpb(self, data):
        self.put(self.start_sample, self.samplenum, self.out_proto, data)

    def putb(self, data):
        self.put(self.start_sample, self.samplenum, self.out_ann, data)

    def report(self):

        # Calculate the sample rate.
        samplerate = '?'
        if self.start_sample != None and \
            self.first_sample != None and \
            self.start_sample > self.first_sample:
            samplerate = '%d' % (self.samplesreceived *
                self.samplerate / (self.start_sample -
                self.first_sample))

        return 'I2S: %d %d-bit samples received at %sHz' % \
            (self.samplesreceived, self.wordlength, samplerate)

    def decode(self, ss, es, data):
        if self.samplerate is None:
            raise Exception("Cannot decode without samplerate.")
        for self.samplenum, (sck, ws, sd) in data:

            # Ignore sample if the bit clock hasn't changed.
            if sck == self.oldsck:
                continue

            self.oldsck = sck
            if sck == 0:   # Ignore the falling clock edge.
                continue

            self.data = (self.data << 1) | sd
            self.bitcount += 1

            # This was not the LSB unless WS has flipped.
            if ws == self.oldws:
                continue

            # Only submit the sample, if we received the beginning of it.
            if self.start_sample != None:
                self.samplesreceived += 1

                idx = 0 if self.oldws else 1
                c1 = 'Left channel' if self.oldws else 'Right channel'
                c2 = 'Left' if self.oldws else 'Right'
                c3 = 'L' if self.oldws else 'R'
                v = '%08x' % self.data
                self.putpb(['DATA', [c3, self.data]])
                self.putb([idx, ['%s: %s' % (c1, v), '%s: %s' % (c2, v),
                                 '%s: %s' % (c3, v), c3]])

                # Check that the data word was the correct length.
                if self.wordlength != -1 and self.wordlength != self.bitcount:
                    self.putb([2, ['Received %d-bit word, expected %d-bit '
                                   'word' % (self.bitcount, self.wordlength)]])

                self.wordlength = self.bitcount

            # Reset decoder state.
            self.data = 0
            self.bitcount = 0
            self.start_sample = self.samplenum

            # Save the first sample position.
            if self.first_sample == None:
                self.first_sample = self.samplenum

            self.oldws = ws

