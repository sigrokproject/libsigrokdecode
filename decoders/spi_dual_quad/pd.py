##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2023 Marc Font Freixa <mfont@bz17.dev>
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
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from collections import namedtuple

Data = namedtuple('Data', ['ss', 'es', 'val'])

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <data1>, <data2>]

<ptype>:
 - 'DATA': <data1> contains the spi data.
   The data is _usually_ 8 bits (but can also be fewer or more bits).
   Both data items are Python numbers (not strings), or None if the respective
   channel was not supplied.
 - 'BITS': <data1>/<data2> contain a list of bit values in this sio0/sio1/sio2/sio3 data
   item, and for each of those also their respective start-/endsample numbers.
 - 'CS-CHANGE': <data1> is the old CS# pin value, <data2> is the new value.
   Both data items are Python numbers (0/1), not strings. At the beginning of
   the decoding a packet is generated with <data1> = None and <data2> being the
   initial state of the CS# pin or None if the chip select pin is not supplied.
 - 'TRANSFER': <data1> contain a list of Data() namedtuples for each
   byte transferred during this block of CS# asserted time. Each Data() has
   fields ss, es, and val.

Examples:
 ['CS-CHANGE', None, 1]
 ['CS-CHANGE', 1, 0]
 ['DATA', 0xff]
 ['BITS', [[1, 80, 82], [1, 83, 84], [1, 85, 86], [1, 87, 88],
           [1, 89, 90], [1, 91, 92], [1, 93, 94], [1, 95, 96]],
          [[0, 80, 82], [1, 83, 84], [0, 85, 86], [1, 87, 88],
           [1, 89, 90], [1, 91, 92], [0, 93, 94], [0, 95, 96]]]
 ['DATA', 0x65]
 ['DATA', 0xa8]
 ['DATA', 0x55]
 ['CS-CHANGE', 0, 1]
 ['TRANSFER', [Data(ss=80, es=96, val=0xff), ...]]
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

ann_spi_data, ann_spi_sio0, ann_spi_sio1, ann_spi_sio2, ann_spi_sio3, ann_spi_other, ann_spi_xfer = range(7)

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'spi-dual-quad'
    name = 'SPI Dual/Quad'
    longname = 'Dual/Quad Serial Peripheral Interface'
    desc = 'Full-duplex, synchronous, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['spi']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock'},
        {'id': 'sio0', 'name': 'SIO0', 'desc': 'SPI Input/Output 0'},
        {'id': 'sio1', 'name': 'SIO1', 'desc': 'SPI Input/Output 1'},
    )
    optional_channels = (
        {'id': 'sio2', 'name': 'SIO2', 'desc': 'SPI Input/Output 2'},
        {'id': 'sio3', 'name': 'SIO3', 'desc': 'SPI Input/Output 3'},
        {'id': 'cs', 'name': 'CS#', 'desc': 'Chip-select'},
    )
    options = (
        {'id': 'cs_polarity', 'desc': 'CS# polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high')},
        {'id': 'cpol', 'desc': 'Clock polarity', 'default': 0,
            'values': (0, 1)},
        {'id': 'cpha', 'desc': 'Clock phase', 'default': 0,
            'values': (0, 1)},
        {'id': 'bitorder', 'desc': 'Bit order',
            'default': 'msb-first', 'values': ('msb-first', 'lsb-first')},
        {'id': 'wordsize', 'desc': 'Word size', 'default': 8},
    )
    annotations = (
        ('spi-data', 'SPI data'),
        ('sio0-bit', 'SIO0 bit'),
        ('sio1-bit', 'SIO1 bit'),
        ('sio2-bit', 'SIO2 bit'),
        ('sio3-bit', 'SIO3 bit'),
        ('warning', 'Warning'),
        ('spi-transfer', 'SPI transfer'),
    )
    annotation_rows = (
        ('sio0-bits', 'SIO0 bits', (ann_spi_sio0,)),
        ('sio1-bits', 'SIO1 bits', (ann_spi_sio1,)),
        ('sio2-bits', 'SIO2 bits', (ann_spi_sio2,)),
        ('sio3-bits', 'SIO3 bits', (ann_spi_sio3,)),
        ('spi-data-vals', 'SPI data', (ann_spi_data,)),
        ('spi-transfers', 'SPI transfers', (ann_spi_xfer,)),
        ('other', 'Other', (ann_spi_other,)),
    )
    binary = (
        ('spi-data', 'SPI Data'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.bitcount = 0
        self.spidata = 0
        self.sio0bits = []
        self.sio1bits = []
        self.sio2bits = []
        self.sio3bits = []
        self.spibytes = []
        self.ss_block = -1
        self.ss_transfer = -1
        self.cs_was_deasserted = False
        self.have_cs = None
        self.is_quad = None

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_bitrate = self.register(srd.OUTPUT_META,
                meta=(int, 'Bitrate', 'Bitrate during transfers'))
        self.bw = (self.options['wordsize'] + 7) // 8

    def metadata(self, key, value):
       if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putw(self, data):
        self.put(self.ss_block, self.samplenum, self.out_ann, data)

    def putdata(self):
        # Pass sio0/sio1/sio2/sio3 bits and then data to the next PD up the stack.
        data = self.spidata
        sio0_bits = self.sio0bits
        sio1_bits = self.sio1bits
        sio2_bits = self.sio2bits
        sio3_bits = self.sio3bits

        ss, es = self.sio0bits[-1][1], self.sio0bits[0][2]
        bdata = data.to_bytes(self.bw, byteorder='big')
        self.put(ss, es, self.out_binary, [0, bdata])
        if self.is_quad:
            self.put(ss, es, self.out_python, ['BITS', sio3_bits, sio2_bits, sio1_bits, sio0_bits])
        else:
            self.put(ss, es, self.out_python, ['BITS', sio1_bits, sio0_bits])
        self.put(ss, es, self.out_python, ['DATA', data])

        self.spibytes.append(Data(ss=ss, es=es, val=data))

        # Bit annotations.
        for bit in self.sio0bits:
            self.put(bit[1], bit[2], self.out_ann, [ann_spi_sio0, ['%d' % bit[0]]])
        for bit in self.sio1bits:
            self.put(bit[1], bit[2], self.out_ann, [ann_spi_sio1, ['%d' % bit[0]]])

        if self.is_quad:
            for bit in self.sio2bits:
                self.put(bit[1], bit[2], self.out_ann, [ann_spi_sio2, ['%d' % bit[0]]])
            for bit in self.sio3bits:
                self.put(bit[1], bit[2], self.out_ann, [ann_spi_sio3, ['%d' % bit[0]]])

        # Dataword annotations.
        self.put(ss, es, self.out_ann, [ann_spi_data, ['%02X' % self.spidata]])

    def reset_decoder_state(self):
        self.spidata = 0
        self.sio0bits = []
        self.sio1bits = []
        self.sio2bits = []
        self.sio3bits = []
        self.bitcount = 0

    def cs_asserted(self, cs):
        active_low = (self.options['cs_polarity'] == 'active-low')
        return (cs == 0) if active_low else (cs == 1)

    def handle_bit(self, sio0, sio1, sio2, sio3, clk, cs):
        # If this is the first bit of a dataword, save its sample number.
        if self.bitcount == 0:
            self.ss_block = self.samplenum
            self.cs_was_deasserted = \
                not self.cs_asserted(cs) if self.have_cs else False

        ws = self.options['wordsize']
        bo = self.options['bitorder']

        if self.is_quad:
            # Quad SPI SIO0 bits 4,0
            # Quad SPI SIO1 bits 5,1
            # Quad SPI SIO2 bits 6,2
            # Quad SPI SIO3 bits 7,3
            if bo == 'msb-first':
                self.spidata |= sio3 << (ws - 1 - self.bitcount)
                self.spidata |= sio2 << (ws - 1 - self.bitcount - 1)
                self.spidata |= sio1 << (ws - 1 - self.bitcount - 2)
                self.spidata |= sio0 << (ws - 1 - self.bitcount - 3)
            else:
                self.spidata |= sio3 << self.bitcount
                self.spidata |= sio2 << (self.bitcount + 1)
                self.spidata |= sio1 << (self.bitcount + 2)
                self.spidata |= sio0 << (self.bitcount + 3)
        else:
            # Dual SPI SIO0 bits 6,4,2,0
            # Dual SPI SIO1 bits 7,5,3,1
            if bo == 'msb-first':
                self.spidata |= sio1 << (ws - 1 - self.bitcount)
                self.spidata |= sio0 << (ws - 1 - self.bitcount - 1)
            else:
                self.spidata |= sio1 << self.bitcount
                self.spidata |= sio0 << (self.bitcount + 1)

        # Guesstimate the endsample for this bit (can be overridden below).
        es = self.samplenum
        if self.bitcount > 0:
            es += self.samplenum - self.sio0bits[0][1]

        self.sio0bits.insert(0, [sio0, self.samplenum, es])
        self.sio1bits.insert(0, [sio1, self.samplenum, es])
        if self.is_quad:
            self.sio2bits.insert(0, [sio2, self.samplenum, es])
            self.sio3bits.insert(0, [sio3, self.samplenum, es])

        if self.bitcount > 0:
            self.sio0bits[1][2] = self.samplenum
            self.sio1bits[1][2] = self.samplenum
            if self.is_quad:
                self.sio2bits[1][2] = self.samplenum
                self.sio3bits[1][2] = self.samplenum

        if self.is_quad:
            self.bitcount += 4
        else:
            self.bitcount += 2

        # Continue to receive if not enough bits were received, yet.
        if self.bitcount < ws:
            return

        self.putdata()

        # Meta bitrate.
        if self.samplerate:
            elapsed = 1 / float(self.samplerate)
            elapsed *= (self.samplenum - self.ss_block + 1)
            bitrate = int(1 / elapsed * ws)
            self.put(self.ss_block, self.samplenum, self.out_bitrate, bitrate)

        if self.have_cs and self.cs_was_deasserted:
            self.putw([ann_spi_other, ['CS# was deasserted during this data word!']])

        self.reset_decoder_state()

    def find_clk_edge(self, sio0, sio1, sio2, sio3, clk, cs, first):
        if self.have_cs and (first or self.matched[self.have_cs]):
            # Send all CS# pin value changes.
            oldcs = None if first else 1 - cs
            self.put(self.samplenum, self.samplenum, self.out_python,
                     ['CS-CHANGE', oldcs, cs])

            if self.cs_asserted(cs):
                self.ss_transfer = self.samplenum
                self.spibytes = []
            elif self.ss_transfer != -1:
                self.put(self.ss_transfer, self.samplenum, self.out_ann,
                    [ann_spi_xfer, [' '.join(format(x.val, '02X') for x in self.spibytes)]])
                self.put(self.ss_transfer, self.samplenum, self.out_python,
                    ['TRANSFER', self.spibytes])

            # Reset decoder state when CS# changes (and the CS# pin is used).
            self.reset_decoder_state()

        # We only care about samples if CS# is asserted.
        if self.have_cs and not self.cs_asserted(cs):
            return

        # Ignore sample if the clock pin hasn't changed.
        if first or not self.matched[0]:
            return

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
        self.handle_bit(sio0, sio1, sio2, sio3, clk, cs)

    def decode(self):
        # The CLK input is mandatory. SIO0 and SIO1 are mandatory for Dual SPI.
        if not self.has_channel(0) and not self.has_channel(1) and not self.has_channel(2):
            raise ChannelError('For Dual SPI SIO0 and SIO1 are pins required.')
        # The CLK input is mandatory. SIO3 and SIO4 are mandatory for Quad SPI.
        if (self.has_channel(3) and not self.has_channel(4)) or (self.has_channel(4) and not self.has_channel(3)):
            raise ChannelError('For Quad SPI SIO2 and SIO3 are pins required.')

        # Mark that SPI is Quad
        self.is_quad = self.has_channel(3) and self.has_channel(4)
        self.have_cs = self.has_channel(5)
        if not self.have_cs:
            self.put(0, 0, self.out_python, ['CS-CHANGE', None, None])

        # Check if wordsize is multiple of 2 or 4
        ws = self.options['wordsize']
        ws_div = 4 if self.is_quad else 2
        if ws % ws_div != 0:
            raise ChannelError('Wordsize must be multiple of data channels number')

        # We want all CLK changes. We want all CS changes if CS is used.
        # Map 'have_cs' from boolean to an integer index. This simplifies
        # evaluation in other locations.
        wait_cond = [{0: 'e'}]
        if self.have_cs:
            self.have_cs = len(wait_cond)
            wait_cond.append({5: 'e'})

        # "Pixel compatibility" with the v2 implementation. Grab and
        # process the very first sample before checking for edges. The
        # previous implementation did this by seeding old values with
        # None, which led to an immediate "change" in comparison.
        (clk, sio0, sio1, sio2, sio3, cs) = self.wait({})
        self.find_clk_edge(sio0, sio1, sio2, sio3, clk, cs, True)

        while True:
            (clk, sio0, sio1, sio2, sio3, cs) = self.wait(wait_cond)
            self.find_clk_edge(sio0, sio1, sio2, sio3, clk, cs, False)
