##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
## Copyright (C) 2012-2014 Uwe Hermann <uwe@hermann-uwe.de>
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

'''
OUTPUT_PYTHON format:

SPI packet:
[<cmd>, <data1>, <data2>]

Commands:
 - 'DATA': <data1> contains the MISO data, <data2> contains the MOSI data.
   The data is _usually_ 8 bits (but can also be fewer or more bits).
   Both data items are Python numbers (not strings), or None if the respective
   probe was not supplied.
 - 'BITS': <data1>/<data2> contain a list of bit values in this MISO/MOSI data
   item, and for each of those also their respective start-/endsample numbers.
 - 'CS CHANGE': <data1> is the old CS# pin value, <data2> is the new value.
   Both data items are Python numbers (0/1), not strings.

Examples:
 ['CS-CHANGE', 1, 0]
 ['DATA', 0xff, 0x3a]
 ['BITS', [[1, 80, 82], [1, 83, 84], [1, 85, 86], [1, 87, 88],
           [1, 89, 90], [1, 91, 92], [1, 93, 94], [1, 95, 96]],
          [[0, 80, 82], [0, 83, 84], [1, 85, 86], [1, 87, 88],
           [1, 89, 90], [0, 91, 92], [1, 93, 94], [0, 95, 96]]]
 ['DATA', 0x65, 0x00]
 ['DATA', 0xa8, None]
 ['DATA', None, 0x55]
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
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock'},
    ]
    optional_probes = [
        {'id': 'miso', 'name': 'MISO', 'desc': 'Master in, slave out'},
        {'id': 'mosi', 'name': 'MOSI', 'desc': 'Master out, slave in'},
        {'id': 'cs', 'name': 'CS#', 'desc': 'Chip-select'},
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
        ['miso-data', 'MISO data'],
        ['mosi-data', 'MOSI data'],
        ['miso-bits', 'MISO bits'],
        ['mosi-bits', 'MOSI bits'],
        ['warnings', 'Human-readable warnings'],
    ]
    annotation_rows = (
        ('miso-data', 'MISO data', (0,)),
        ('miso-bits', 'MISO bits', (2,)),
        ('mosi-data', 'MOSI data', (1,)),
        ('mosi-bits', 'MOSI bits', (3,)),
        ('other', 'Other', (4,)),
    )

    def __init__(self):
        self.samplerate = None
        self.oldclk = 1
        self.bitcount = 0
        self.mosidata = 0
        self.misodata = 0
        self.mosibits = []
        self.misobits = []
        self.startsample = -1
        self.samplenum = -1
        self.cs_was_deasserted_during_data_word = 0
        self.oldcs = -1
        self.oldpins = None
        self.have_cs = None
        self.have_miso = None
        self.have_mosi = None
        self.state = 'IDLE'

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_bitrate = self.register(srd.OUTPUT_META,
                meta=(int, 'Bitrate', 'Bitrate during transfers'))

    def putpw(self, data):
        self.put(self.startsample, self.samplenum, self.out_python, data)

    def putw(self, data):
        self.put(self.startsample, self.samplenum, self.out_ann, data)

    def putmisobit(self, i, data):
        self.put(self.misobits[i][1], self.misobits[i][2], self.out_ann, data)

    def putmosibit(self, i, data):
        self.put(self.mosibits[i][1], self.mosibits[i][2], self.out_ann, data)

    def reset_decoder_state(self):
        self.misodata = 0 if self.have_miso else None
        self.mosidata = 0 if self.have_mosi else None
        self.misobits = [] if self.have_miso else None
        self.mosibits = [] if self.have_mosi else None
        self.bitcount = 0

    def handle_bit(self, miso, mosi, clk, cs):
        # If this is the first bit of a dataword, save its sample number.
        if self.bitcount == 0:
            self.startsample = self.samplenum
            if self.have_cs:
                active_low = (self.options['cs_polarity'] == 'active-low')
                deasserted = cs if active_low else not cs
                if deasserted:
                    self.cs_was_deasserted_during_data_word = 1

        ws = self.options['wordsize']

        # Receive MOSI bit into our shift register.
        if self.have_mosi:
            if self.options['bitorder'] == 'msb-first':
                self.mosidata |= mosi << (ws - 1 - self.bitcount)
            else:
                self.mosidata |= mosi << self.bitcount

        # Receive MISO bit into our shift register.
        if self.have_miso:
            if self.options['bitorder'] == 'msb-first':
                self.misodata |= miso << (ws - 1 - self.bitcount)
            else:
                self.misodata |= miso << self.bitcount

        if self.have_miso:
            self.misobits.append([miso, self.samplenum, -1])
        if self.have_mosi:
            self.mosibits.append([mosi, self.samplenum, -1])
        if self.bitcount != 0:
            if self.have_miso:
                self.misobits[self.bitcount - 1][2] = self.samplenum
                self.putmisobit(self.bitcount - 1, [3, ['%d' % miso]])
            if self.have_mosi:
                self.mosibits[self.bitcount - 1][2] = self.samplenum
                self.putmosibit(self.bitcount - 1, [2, ['%d' % mosi]])

        self.bitcount += 1

        # Continue to receive if not enough bits were received, yet.
        if self.bitcount != ws:
            return

        si = self.mosidata if self.have_mosi else None
        so = self.misodata if self.have_miso else None
        si_bits = self.mosibits if self.have_mosi else None
        so_bits = self.misobits if self.have_miso else None

        # Pass MOSI and MISO to the next PD up the stack.
        self.putpw(['DATA', si, so])
        self.putpw(['BITS', si_bits, so_bits])

        # Annotations.
        if self.have_miso:
            self.putw([0, ['%02X' % self.misodata]])
        if self.have_mosi:
            self.putw([1, ['%02X' % self.mosidata]])

        # Meta bitrate.
        elapsed = 1 / float(self.samplerate) * (self.samplenum - self.startsample + 1)
        bitrate = int(1 / elapsed * self.options['wordsize'])
        self.put(self.startsample, self.samplenum, self.out_bitrate, bitrate)

        if self.have_cs and self.cs_was_deasserted_during_data_word:
            self.putw([4, ['CS# was deasserted during this data word!']])

        self.reset_decoder_state()

    def find_clk_edge(self, miso, mosi, clk, cs):
        if self.have_cs and self.oldcs != cs:
            # Send all CS# pin value changes.
            self.put(self.samplenum, self.samplenum, self.out_python,
                     ['CS-CHANGE', self.oldcs, cs])
            self.oldcs = cs
            # Reset decoder state when CS# changes (and the CS# pin is used).
            self.reset_decoder_state()

        # Ignore sample if the clock pin hasn't changed.
        if clk == self.oldclk:
            return

        self.oldclk = clk

        # Sample data on rising/falling clock edge (depends on mode).
        mode = spi_mode[self.options['cpol'], self.options['cpha']]
        if mode == 0 and clk == 0:   # Sample on rising clock edge
            return
        elif mode == 1 and clk == 1: # Sample on falling clock edge
            return
        elif mode == 2 and clk == 1: # Sample on falling clock edge
            return
        elif mode == 3 and clk == 0: # Sample on rising clock edge
            return

        # Found the correct clock edge, now get the SPI bit(s).
        self.handle_bit(miso, mosi, clk, cs)

    def decode(self, ss, es, data):
        if self.samplerate is None:
            raise Exception("Cannot decode without samplerate.")
        # Either MISO or MOSI can be omitted (but not both). CS# is optional.
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (clk, miso, mosi, cs) = pins, pins
            self.have_miso = (miso in (0, 1))
            self.have_mosi = (mosi in (0, 1))
            self.have_cs = (cs in (0, 1))

            # State machine.
            if self.state == 'IDLE':
                self.find_clk_edge(miso, mosi, clk, cs)
            else:
                raise Exception('Invalid state: %s' % self.state)

