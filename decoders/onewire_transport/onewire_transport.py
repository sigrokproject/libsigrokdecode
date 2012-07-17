##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Iztok Jeras <iztok.jeras@gmail.com>
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

# 1-Wire protocol decoder

import sigrokdecode as srd

# a dictionary of FUNCTION commands and their names
command = {0x44: "TEMPERATURE CONVERSION",
           0xbe: "READ SCRATCHPAD"}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire_transport'
    name = '1-Wire transport layer'
    longname = '1-Wire serial communication bus'
    desc = 'Bidirectional, half-duplex, asynchronous serial bus.'
    license = 'gplv2+'
    inputs = ['onewire_network']
    outputs = []
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Transport', 'Transport layer events'],
    ]

    def __init__(self, **kwargs):
        # Event timing variables
        self.trn_beg = 0
        self.trn_end = 0
        # Transport layer variables
        self.state   = 'ROM'
        self.rom     = 0x0000000000000000

    def start(self, metadata):
        self.out_ann   = self.add(srd.OUTPUT_ANN  , 'onewire_transport')

    def report(self):
        pass

    def decode(self, ss, es, data):
        [code, val] = data

        # State machine.
        if (code == "RESET/PRESENCE"):
            self.put(ss, es, self.out_ann, [0, ['RESET/PRESENCE: %s' % ('True' if val else 'False')]])
            self.state = "ROM"
        elif (code == "ROM"):
            self.rom = val
            self.put(ss, es, self.out_ann, [0, ['ROM: 0x%016x' % (val)]])
            self.state = "COMMAND"
        elif (code == "DATA"):
            if (self.state == "COMMAND"):
                    if (val in command):
                        self.put(ss, es, self.out_ann, [0, ['FUNCTION COMMAND: 0x%02x \'%s\'' % (val, command[val])]])
                        self.state = command[val]
                    else:
                        self.put(ss, es, self.out_ann, [0, ['FUNCTION COMMAND: 0x%02x \'%s\'' % (val, 'UNRECOGNIZED')]])
                        self.state = "UNRECOGNIZED"
            elif (self.state == "READ SCRATCHPAD"):
                self.put(ss, es, self.out_ann, [0, ['SCRATCHPAD DATA: 0x%02x' % (val)]])
            elif (self.state == "TEMPERATURE CONVERSION"):
                self.put(ss, es, self.out_ann, [0, ['TEMPERATURE CONVERSION STATUS: 0x%02x' % (val)]])
            elif (self.state == "UNRECOGNIZED"):
                self.put(ss, es, self.out_ann, [0, ['UNRECOGNIZED: 0x%02x' % (val)]])
            else:
                raise Exception('Invalid state: %s' % self.state)
