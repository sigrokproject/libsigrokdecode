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
command = {
    # scratchpad
    0x4e: "WRITE SCRATCHPAD",
    0xbe: "READ SCRATCHPAD",
    0x48: "COPY SCRATCHPAD",
    # thermometer
    0x44: "CONVERT TEMPERATURE",
    0xb4: "READ POWER MODE",
    0xb8: "RECALL EEPROM",
    0xf5: "PIO ACCESS READ",
    0xA5: "PIO ACCESS WRITE",
    0x99: "CHAIN",
    # memory
    0xf0: "READ MEMORY",
    0xa5: "EXTENDED READ MEMORY",
    0x0f: "WRITE MEMORY",
    0x55: "WRITE STATUS",
    0xaa: "READ STATUS",
    0xf5: "CHANNEL ACCESS"
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'maxim_ds28ea00'
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
            elif (self.state == "CONVERT TEMPERATURE"):
                self.put(ss, es, self.out_ann, [0, ['TEMPERATURE CONVERSION STATUS: 0x%02x' % (val)]])
            elif (self.state in command.values()):
                self.put(ss, es, self.out_ann, [0, ['TODO "%s": 0x%02x' % (self.state, val)]])
            elif (self.state == "UNRECOGNIZED"):
                self.put(ss, es, self.out_ann, [0, ['UNRECOGNIZED COMMAND: 0x%02x' % (val)]])
            else:
                raise Exception('Invalid state: %s' % self.state)
