##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
## Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
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

# SPI protocol decoder

import sigrokdecode as srd

'''
Protocol output format:

SPI packet:
[<cmd>, <data1>, <data2>]

Commands:
 - 'DATA': <data1> contains the MISO data, <data2> contains the MOSI data.
   The data is _usually_ 8 bits (but can also be fewer or more bits).
   Both data items are Python numbers, not strings.
 - 'CS CHANGE': <data1> is the old CS# pin value, <data2> is the new value.
   Both data items are Python numbers (0/1), not strings.

Examples:
 ['CS-CHANGE', 1, 0]
 ['DATA', 0xff, 0x3a]
 ['DATA', 0x65, 0x00]
 ['CS-CHANGE', 0, 1]
'''

# Key: (CPOL, CPHA). Value: SPI mode.
# Clock polarity (CPOL) = 0/1: Clock is low/high when inactive.
# Clock phase (CPHA) = 0/1: Data is valid on the leading/trailing clock edge.
spi_mode = {
    (0, 0): 0, # Mode 0
    (0, 1): 1, # Mode 1
    (1, 0): 2, # Mode 2
    (1, 1): 3, # Mode 3
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'spi'
    name = 'SPI'
    longname = 'Serial Peripheral Interface'
    desc = 'Full-duplex, synchronous, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['spi']
    probes = [
        {'id': 'miso', 'name': 'MISO',
         'desc': 'SPI MISO line (Master in, slave out)'},
        {'id': 'mosi', 'name': 'MOSI',
         'desc': 'SPI MOSI line (Master out, slave in)'},
        {'id': 'sck', 'name': 'CLK', 'desc': 'SPI clock line'},
    ]
    optional_probes = [
        {'id': 'cs', 'name': 'CS#', 'desc': 'SPI chip-select line'},
    ]
    options = {
        'cs_polarity': ['CS# polarity', 'active-low'],
        'cpol': ['Clock polarity', 0],
        'cpha': ['Clock phase', 0],
        'bitorder': ['Bit order within the SPI data', 'msb-first'],
        'wordsize': ['Word size of SPI data', 8], # 1-64?
        'format': ['Data format', 'hex'],
    }
    annotations = [
        ['MISO/MOSI data', 'MISO/MOSI SPI data'],
        ['MISO data', 'MISO SPI data'],
        ['MOSI data', 'MOSI SPI data'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self):
        self.oldsck = 1
        self.bitcount = 0
        self.mosidata = 0
        self.misodata = 0
        self.bytesreceived = 0
        self.startsample = -1
        self.samplenum = -1
        self.cs_was_deasserted_during_data_word = 0
        self.oldcs = -1
        self.oldpins = None
        self.state = 'IDLE'

    def start(self):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'spi')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'spi')

    def report(self):
        return 'SPI: %d bytes received' % self.bytesreceived

    def putpw(self, data):
        self.put(self.startsample, self.samplenum, self.out_proto, data)

    def putw(self, data):
        self.put(self.startsample, self.samplenum, self.out_ann, data)

    def handle_bit(self, miso, mosi, sck, cs):
        # If this is the first bit, save its sample number.
        if self.bitcount == 0:
            self.startsample = self.samplenum
            if self.have_cs:
                active_low = (self.options['cs_polarity'] == 'active-low')
                deasserted = cs if active_low else not cs
                if deasserted:
                    self.cs_was_deasserted_during_data_word = 1

        ws = self.options['wordsize']

        # Receive MOSI bit into our shift register.
        if self.options['bitorder'] == 'msb-first':
            self.mosidata |= mosi << (ws - 1 - self.bitcount)
        else:
            self.mosidata |= mosi << self.bitcount

        # Receive MISO bit into our shift register.
        if self.options['bitorder'] == 'msb-first':
            self.misodata |= miso << (ws - 1 - self.bitcount)
        else:
            self.misodata |= miso << self.bitcount

        self.bitcount += 1

        # Continue to receive if not enough bits were received, yet.
        if self.bitcount != ws:
            return

        self.putpw(['DATA', self.mosidata, self.misodata])
        self.putw([0, ['%02X/%02X' % (self.mosidata, self.misodata)]])
        self.putw([1, ['%02X' % self.misodata]])
        self.putw([2, ['%02X' % self.mosidata]])

        if self.cs_was_deasserted_during_data_word:
            self.putw([3, ['CS# was deasserted during this data word!']])

        # Reset decoder state.
        self.mosidata = self.misodata = self.bitcount = 0

        # Keep stats for summary.
        self.bytesreceived += 1

    def find_clk_edge(self, miso, mosi, sck, cs):
        if self.have_cs and self.oldcs != cs:
            # Send all CS# pin value changes.
            self.put(self.samplenum, self.samplenum, self.out_proto,
                     ['CS-CHANGE', self.oldcs, cs])
            self.oldcs = cs
            # Reset decoder state when CS# changes (and the CS# pin is used).
            self.mosidata = self.misodata = self.bitcount= 0

        # Ignore sample if the clock pin hasn't changed.
        if sck == self.oldsck:
            return

        self.oldsck = sck

        # Sample data on rising/falling clock edge (depends on mode).
        mode = spi_mode[self.options['cpol'], self.options['cpha']]
        if mode == 0 and sck == 0:   # Sample on rising clock edge
            return
        elif mode == 1 and sck == 1: # Sample on falling clock edge
            return
        elif mode == 2 and sck == 1: # Sample on falling clock edge
            return
        elif mode == 3 and sck == 0: # Sample on rising clock edge
            return

        # Found the correct clock edge, now get the SPI bit(s).
        self.handle_bit(miso, mosi, sck, cs)

    def decode(self, ss, es, data):
        # TODO: Either MISO or MOSI could be optional. CS# is optional.
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (miso, mosi, sck, cs) = pins, pins
            self.have_cs = (cs in (0, 1))

            # State machine.
            if self.state == 'IDLE':
                self.find_clk_edge(miso, mosi, sck, cs)
            else:
                raise Exception('Invalid state: %s' % self.state)

