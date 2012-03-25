##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

# Transition counter protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'transitioncounter'
    name = 'Transition counter'
    longname = 'Pin transition counter'
    desc = 'Counts rising/falling edges in the signal.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['transitioncounts']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['TODO', 'TODO'],
    ]

    def __init__(self, **kwargs):
        self.channels = -1
        self.lastsample = None

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'transitioncounter')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'transitioncounter')

    def report(self):
        pass

    def decode(self, ss, es, data):

        for (samplenum, s) in data:

            # ...
            if self.channels == -1:
                self.channels = len(s)
                self.oldbit = [0] * self.channels
                self.transitions = [0] * self.channels
                self.rising = [0] * self.channels
                self.falling = [0] * self.channels

            # Optimization: Skip identical samples (no transitions).
            if self.lastsample == s:
                continue

            # Upon the first sample, store the initial values.
            if self.lastsample == None:
                self.lastsample = s
                for i in range(self.channels):
                    self.oldbit[i] = self.lastsample[i]

            # Iterate over all channels/probes in this sample.
            # Count rising and falling edges for each channel.
            for i in range(self.channels):
                curbit = s[i]
                # Optimization: Skip identical bits (no transitions).
                if self.oldbit[i] == curbit:
                    continue
                elif (self.oldbit[i] == 0 and curbit == 1):
                    self.rising[i] += 1
                elif (self.oldbit[i] == 1 and curbit == 0):
                    self.falling[i] += 1
                self.oldbit[i] = curbit

            # Save the current sample as 'lastsample' for the next round.
            self.lastsample = s

        # Total number of transitions = rising + falling edges.
        for i in range(self.channels):
            self.transitions[i] = self.rising[i] + self.falling[i]

        # TODO: Which output format?
        # TODO: How to only output something after the last chunk of data?
        outdata = []
        for i in range(self.channels):
            outdata.append([self.transitions[i], self.rising[i],
                            self.falling[i]])

        if outdata != []:
            # self.put(0, 0, self.out_proto, out_proto)
            self.put(0, 0, self.out_ann, [0, [str(outdata)]])

