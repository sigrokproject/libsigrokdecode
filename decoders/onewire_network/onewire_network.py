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

# 1-Wire protocol decoder (network layer)

import sigrokdecode as srd

# Dictionary of ROM commands and their names, next state.
command = {
    0x33: ['READ ROM'              , 'GET ROM'   ],
    0x0f: ['CONDITIONAL READ ROM'  , 'GET ROM'   ],
    0xcc: ['SKIP ROM'              , 'TRANSPORT' ],
    0x55: ['MATCH ROM'             , 'GET ROM'   ],
    0xf0: ['SEARCH ROM'            , 'SEARCH ROM'],
    0xec: ['CONDITIONAL SEARCH ROM', 'SEARCH ROM'],
    0x3c: ['OVERDRIVE SKIP ROM'    , 'TRANSPORT' ],
    0x6d: ['OVERDRIVE MATCH ROM'   , 'GET ROM'   ],
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire_network'
    name = '1-Wire network layer'
    longname = '1-Wire serial communication bus (network layer)'
    desc = 'Bidirectional, half-duplex, asynchronous serial bus.'
    license = 'gplv2+'
    inputs = ['onewire_link']
    outputs = ['onewire_network']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Network', 'Network layer events (device addressing)'],
    ]

    def __init__(self, **kwargs):
        # Event timing variables
        self.net_beg = 0
        self.net_end = 0
        # Network layer variables
        self.state = 'COMMAND'
        self.bit_cnt = 0
        self.search = 'P'
        self.data_p = 0x0
        self.data_n = 0x0
        self.data = 0x0
        self.net_rom = 0x0000000000000000

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire_network')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'onewire_network')

    def report(self):
        pass

    def putx(self, data):
        # Helper function for most annotations.
        self.put(self.net_beg, self.net_end, self.out_ann, data)

    def puty(self, data):
        # Helper function for most protocol packets.
        self.put(self.net_beg, self.net_end, self.out_proto, data)

    def decode(self, ss, es, data):
        code, val = data

        # State machine.
        if code == 'RESET/PRESENCE':
            self.search = 'P'
            self.bit_cnt = 0
            self.put(ss, es, self.out_ann,
                     [0, ['RESET/PRESENCE: %s' % ('True' if val else 'False')]])
            self.put(ss, es, self.out_proto, ['RESET/PRESENCE', val])
            self.state = 'COMMAND'
        elif code == 'BIT':
            if self.state == 'COMMAND':
                # Receiving and decoding a ROM command.
                if self.onewire_collect(8, val, ss, es):
                    if self.data in command:
                        self.putx([0, ['ROM COMMAND: 0x%02x \'%s\''
                                  % (self.data, command[self.data][0])]])
                        self.state = command[self.data][1]
                    else:
                        self.putx([0, ['ROM COMMAND: 0x%02x \'%s\''
                                  % (self.data, 'UNRECOGNIZED')]])
                        self.state = 'COMMAND ERROR'
            elif self.state == 'GET ROM':
                # A 64 bit device address is selected.
                # Family code (1B) + serial number (6B) + CRC (1B)
                if self.onewire_collect(64, val, ss, es):
                    self.net_rom = self.data & 0xffffffffffffffff
                    self.putx([0, ['ROM: 0x%016x' % self.net_rom]])
                    self.puty(['ROM', self.net_rom])
                    self.state = 'TRANSPORT'
            elif self.state == 'SEARCH ROM':
                # A 64 bit device address is searched for.
                # Family code (1B) + serial number (6B) + CRC (1B)
                if self.onewire_search(64, val, ss, es):
                    self.net_rom = self.data & 0xffffffffffffffff
                    self.putx([0, ['ROM: 0x%016x' % self.net_rom]])
                    self.puty(['ROM', self.net_rom])
                    self.state = 'TRANSPORT'
            elif self.state == 'TRANSPORT':
                # The transport layer is handled in byte sized units.
                if self.onewire_collect(8, val, ss, es):
                    self.putx([0, ['DATA: 0x%02x' % self.data]])
                    self.puty(['DATA', self.data])
            elif self.state == 'COMMAND ERROR':
                # Since the command is not recognized, print raw data.
                if self.onewire_collect(8, val, ss, es):
                    self.putx([0, ['ROM ERROR DATA: 0x%02x' % self.data]])
            else:
                raise Exception('Invalid state: %s' % self.state)

    # Link/Network layer data collector.
    def onewire_collect(self, length, val, ss, es):
        # Storing the sample this sequence begins with.
        if self.bit_cnt == 1:
            self.net_beg = ss
        self.data = self.data & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
        self.bit_cnt += 1
        # Storing the sample this sequence ends with.
        # In case the full length of the sequence is received, return 1.
        if self.bit_cnt == length:
            self.net_end = es
            self.data = self.data & ((1 << length) - 1)
            self.bit_cnt = 0
            return 1
        else:
            return 0

    # Link/Network layer search collector.
    def onewire_search(self, length, val, ss, es):
        # Storing the sample this sequence begins with.
        if (self.bit_cnt == 0) and (self.search == 'P'):
            self.net_beg = ss

        if self.search == 'P':
            # Master receives an original address bit.
            self.data_p = self.data_p & ~(1 << self.bit_cnt) | \
                          (val << self.bit_cnt)
            self.search = 'N'
        elif self.search == 'N':
            # Master receives a complemented address bit.
            self.data_n = self.data_n & ~(1 << self.bit_cnt) | \
                          (val << self.bit_cnt)
            self.search = 'D'
        elif self.search == 'D':
            # Master transmits an address bit.
            self.data = self.data & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
            self.search = 'P'
            self.bit_cnt += 1

        # Storing the sample this sequence ends with.
        # In case the full length of the sequence is received, return 1.
        if self.bit_cnt == length:
            self.net_end = es
            self.data_p = self.data_p & ((1 << length) - 1)
            self.data_n = self.data_n & ((1 << length) - 1)
            self.data = self.data & ((1 << length) - 1)
            self.search = 'P'
            self.bit_cnt = 0
            return 1
        else:
            return 0
