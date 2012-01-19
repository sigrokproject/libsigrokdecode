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

import sigrokdecode as srd

# Chip-select options
ACTIVE_LOW = 0
ACTIVE_HIGH = 1

# Clock polarity options
CPOL_0 = 0 # Clock is low when inactive
CPOL_1 = 1 # Clock is high when inactive

# Clock phase options
CPHA_0 = 0 # Data is valid on the leading clock edge
CPHA_1 = 1 # Data is valid on the trailing clock edge

# Bit order options
MSB_FIRST = 0
LSB_FIRST = 1

# Key: (CPOL, CPHA). Value: SPI mode.
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
    desc = '...desc...'
    longdesc = '...longdesc...'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['spi']
    probes = [
        {'id': 'mosi', 'name': 'MOSI',
         'desc': 'SPI MOSI line (Master out, slave in)'},
        {'id': 'miso', 'name': 'MISO',
         'desc': 'SPI MISO line (Master in, slave out)'},
        {'id': 'sck', 'name': 'CLK', 'desc': 'SPI clock line'},
        {'id': 'cs', 'name': 'CS#', 'desc': 'SPI CS (chip select) line'},
    ]
    options = {
        'cs_polarity': ['CS# polarity', ACTIVE_LOW],
        'cpol': ['Clock polarity', CPOL_0],
        'cpha': ['Clock phase', CPHA_0],
        'bitorder': ['Bit order within the SPI data', MSB_FIRST],
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

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'spi')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'spi')

    def report(self):
        return 'SPI: %d bytes received' % self.bytesreceived

    def decode(self, ss, es, data):
        # HACK! At the moment the number of probes is not handled correctly.
        # E.g. if an input file (-i foo.sr) has more than two probes enabled.
        # for (samplenum, (mosi, sck, x, y, z, a)) in data:
        # for (samplenum, (cs, miso, sck, mosi, wp, hold)) in data:
        for (samplenum, (cs, miso, sck, mosi, wp, hold)) in data:

            self.samplenum += 1 # FIXME

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
                self.start_sample = samplenum
                active_low = (self.options['cs_polarity'] == ACTIVE_LOW)
                deasserted = cs if active_low else not cs
                if deasserted:
                    self.cs_was_deasserted_during_data_word = 1

            # Receive MOSI bit into our shift register.
            if self.options['bitorder'] == MSB_FIRST:
                self.mosidata |= mosi << (self.options['wordsize'] - 1 - self.bitcount)
            else:
                self.mosidata |= mosi << self.bitcount

            # Receive MISO bit into our shift register.
            if self.options['bitorder'] == MSB_FIRST:
                self.misodata |= miso << (self.options['wordsize'] - 1 - self.bitcount)
            else:
                self.misodata |= miso << self.bitcount

            self.bitcount += 1

            # Continue to receive if not a byte yet.
            if self.bitcount != self.options['wordsize']:
                continue

            self.put(self.start_sample, self.samplenum, self.out_proto,
                     ['data', self.mosidata, self.misodata])
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

