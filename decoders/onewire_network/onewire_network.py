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

# Annotation feed formats
ANN_NETWORK   = 0
ANN_TRANSPORT = 1

# a dictionary of ROM commands and their names
rom_command = {0x33: "READ ROM",
               0x0f: "CONDITIONAL READ ROM",
               0xcc: "SKIP ROM",
               0x55: "MATCH ROM",
               0xf0: "SEARCH ROM",
               0xec: "CONDITIONAL SEARCH ROM",
               0x3c: "OVERDRIVE SKIP ROM",
               0x6d: "OVERDRIVE MATCH ROM"}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire_network'
    name = '1-Wire network layer'
    longname = '1-Wire serial communication bus'
    desc = 'Bidirectional, half-duplex, asynchronous serial bus.'
    license = 'gplv2+'
    inputs = ['onewire_link']
    outputs = ['onewire_network']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Network', 'Network layer events (device addressing)'],
        ['Transport', 'Transport layer events'],
    ]

    def __init__(self, **kwargs):
        # Event timing variables
        self.net_beg = 0
        self.net_end = 0
        # Network layer variables
        self.state   = 'COMMAND'
        self.bit_cnt = 0
        self.search  = "P"
        self.data_p  = 0x0
        self.data_n  = 0x0
        self.data    = 0x0
        self.net_rom = 0x0000000000000000

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire_network')
        self.out_ann   = self.add(srd.OUTPUT_ANN  , 'onewire_network')

    def report(self):
        pass

    def decode(self, ss, es, data):
        [code, val] = data

        # State machine.
        if (code == "RESET"):
            self.state = "COMMAND"
            self.search = "P"
            self.bit_cnt = 0
        elif (code == "BIT"):
            if (self.state == "COMMAND"):
                # Receiving and decoding a ROM command
                if (self.onewire_collect(8, val, ss, es)):
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK,
                      ['ROM COMMAND: 0x%02x \'%s\'' % (self.data, rom_command[self.data])]])
                    if   (self.data == 0x33):  # READ ROM
                        self.state = "GET ROM"
                    elif (self.data == 0x0f):  # CONDITIONAL READ ROM
                        self.state = "GET ROM"
                    elif (self.data == 0xcc):  # SKIP ROM
                        self.state = "TRANSPORT"
                    elif (self.data == 0x55):  # MATCH ROM
                        self.state = "GET ROM"
                    elif (self.data == 0xf0):  # SEARCH ROM
                        self.state = "SEARCH ROM"
                    elif (self.data == 0xec):  # CONDITIONAL SEARCH ROM
                        self.state = "SEARCH ROM"
                    elif (self.data == 0x3c):  # OVERDRIVE SKIP ROM
                        self.state = "TRANSPORT"
                    elif (self.data == 0x69):  # OVERDRIVE MATCH ROM
                        self.state = "GET ROM"
            elif (self.state == "GET ROM"):
                # A 64 bit device address is selected
                # family code (1B) + serial number (6B) + CRC (1B)
                if (self.onewire_collect(64, val, ss, es)):
                    self.net_rom = self.data & 0xffffffffffffffff
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK, ['ROM: 0x%016x' % self.net_rom]])
                    self.state = "TRANSPORT"
            elif (self.state == "SEARCH ROM"):
                # A 64 bit device address is searched for
                # family code (1B) + serial number (6B) + CRC (1B)
                if (self.onewire_search(64, val, ss, es)):
                    self.net_rom = self.data & 0xffffffffffffffff
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK, ['ROM: 0x%016x' % self.net_rom]])
                    self.state = "TRANSPORT"
            elif (self.state == "TRANSPORT"):
                # The transport layer is handled in byte sized units
                if (self.onewire_collect(8, val, ss, es)):
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK  , ['TRANSPORT: 0x%02x' % self.data]])
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_TRANSPORT, ['TRANSPORT: 0x%02x' % self.data]])
                    self.put(self.net_beg, self.net_end, self.out_proto, ['transfer', self.data])
                    # TODO: Sending translort layer data to 1-Wire device models
            else:
                raise Exception('Invalid state: %s' % self.state)


    # Link/Network layer data collector
    def onewire_collect (self, length, val, ss, es):
        # Storing the sampe this sequence begins with
        if (self.bit_cnt == 1):
            self.net_beg = ss
        self.data = self.data & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
        self.bit_cnt  = self.bit_cnt + 1
        # Storing the sampe this sequence ends with
        # In case the full length of the sequence is received, return 1
        if (self.bit_cnt == length):
            self.net_end  = es
            self.data = self.data & ((1<<length)-1)
            self.bit_cnt  = 0
            return (1)
        else:
            return (0)

    # Link/Network layer search collector
    def onewire_search (self, length, val, ss, es):
        # Storing the sampe this sequence begins with
        if ((self.bit_cnt == 0) and (self.search == "P")):
            self.net_beg = ss
        # Master receives an original address bit
        if   (self.search == "P"):
          self.data_p = self.data_p & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
          self.search = "N"
        # Master receives a complemented address bit
        elif (self.search == "N"):
          self.data_n = self.data_n & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
          self.search = "D"
        # Master transmits an address bit
        elif (self.search == "D"):
          self.data   = self.data   & ~(1 << self.bit_cnt) | (val << self.bit_cnt)
          self.search = "P"
          self.bit_cnt    = self.bit_cnt + 1
        # Storing the sampe this sequence ends with
        # In case the full length of the sequence is received, return 1
        if (self.bit_cnt == length):
            self.net_end = es
            self.data_p = self.data_p & ((1<<length)-1)
            self.data_n = self.data_n & ((1<<length)-1)
            self.data   = self.data   & ((1<<length)-1)
            self.search = "P"
            self.bit_cnt    = 0
            return (1)
        else:
            return (0)
