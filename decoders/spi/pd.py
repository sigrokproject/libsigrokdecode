##
## This file is part of the sigrok project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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

# Key: (CPOL, CPHA). Value: SPI mode.
# Clock polarity (CPOL) = 0/1: Clock is low/high when inactive.
# Clock phase (CPHA) = 0/1: Data is valid on the leading/trailing clock edge.
spi_mode = {
    (0, 0): 0, # Mode 0
    (0, 1): 1, # Mode 1
    (1, 0): 2, # Mode 2
    (1, 1): 3, # Mode 3
}

# Annotation formats
ANN_HEX = 0

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
        {'id': 'cs', 'name': 'CS#', 'desc': 'SPI CS (chip select) line'},
    ]
    optional_probes = [] # TODO
    options = {
        'cs_polarity': ['CS# polarity', 'active-low'],
        'cpol': ['Clock polarity', 0],
        'cpha': ['Clock phase', 0],
        'bitorder': ['Bit order within the SPI data', 'msb-first'],
        'wordsize': ['Word size of SPI data', 8], # 1-64?
    }
    annotations = [
        ['Hex', 'SPI data bytes in hex format'],
    ]

    def __init__(self):
        self.oldsck = 1
        self.bitcount = 0
        self.mosidata = 0
        self.misodata = 0
        self.bytesreceived = 0
        self.samplenum = -1
        self.cs_was_deasserted_during_data_word = 0
        self.oldcs = -1
        self.oldpins = None

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'spi')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'spi')

    def report(self):
        return 'SPI: %d bytes received' % self.bytesreceived

    def decode(self, ss, es, data):
        # TODO: Either MISO or MOSI could be optional. CS# is optional.
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (miso, mosi, sck, cs) = pins, pins

            if self.oldcs != cs:
                # Send all CS# pin value changes.
                self.put(self.samplenum, self.samplenum, self.out_proto,
                         ['CS-CHANGE', self.oldcs, cs])
                self.put(self.samplenum, self.samplenum, self.out_ann,
                         [0, ['CS-CHANGE: %d->%d' % (self.oldcs, cs)]])
                self.oldcs = cs

            # Ignore sample if the clock pin hasn't changed.
            if sck == self.oldsck:
                continue

            self.oldsck = sck

            # Sample data on rising/falling clock edge (depends on mode).
            mode = spi_mode[self.options['cpol'], self.options['cpha']]
            if mode == 0 and sck == 0:   # Sample on rising clock edge
                    continue
            elif mode == 1 and sck == 1: # Sample on falling clock edge
                    continue
            elif mode == 2 and sck == 1: # Sample on falling clock edge
                    continue
            elif mode == 3 and sck == 0: # Sample on rising clock edge
                    continue

            # If this is the first bit, save its sample number.
            if self.bitcount == 0:
                self.start_sample = self.samplenum
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
                continue

            self.put(self.start_sample, self.samplenum, self.out_proto,
                     ['DATA', self.mosidata, self.misodata])
            self.put(self.start_sample, self.samplenum, self.out_ann,
                     [ANN_HEX, ['MOSI: 0x%02x, MISO: 0x%02x' % (self.mosidata,
                     self.misodata)]])

            if self.cs_was_deasserted_during_data_word:
                self.put(self.start_sample, self.samplenum, self.out_ann,
                         [ANN_HEX, ['WARNING: CS# was deasserted during this '
                         'SPI data byte!']])

            # Reset decoder state.
            self.mosidata = 0
            self.misodata = 0
            self.bitcount = 0

            # Keep stats for summary.
            self.bytesreceived += 1

