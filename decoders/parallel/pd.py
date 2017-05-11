##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2013-2016 Uwe Hermann <uwe@hermann-uwe.de>
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

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>, <pdata>
 - 'ITEM', [<item>, <itembitsize>]
 - 'WORD', [<word>, <wordbitsize>, <worditemcount>]

<item>:
 - A single item (a number). It can be of arbitrary size. The max. number
   of bits in this item is specified in <itembitsize>.

<itembitsize>:
 - The size of an item (in bits). For a 4-bit parallel bus this is 4,
   for a 16-bit parallel bus this is 16, and so on.

<word>:
 - A single word (a number). It can be of arbitrary size. The max. number
   of bits in this word is specified in <wordbitsize>. The (exact) number
   of items in this word is specified in <worditemcount>.

<wordbitsize>:
 - The size of a word (in bits). For a 2-item word with 8-bit items
   <wordbitsize> is 16, for a 3-item word with 4-bit items <wordbitsize>
   is 12, and so on.

<worditemcount>:
 - The size of a word (in number of items). For a 4-item word (no matter
   how many bits each item consists of) <worditemcount> is 4, for a 7-item
   word <worditemcount> is 7, and so on.
'''

def channel_list(num_channels):
    l = [{'id': 'clk', 'name': 'CLK', 'desc': 'Clock line'}]
    for i in range(num_channels):
        d = {'id': 'd%d' % i, 'name': 'D%d' % i, 'desc': 'Data line %d' % i}
        l.append(d)
    return tuple(l)

class ChannelError(Exception):
    pass

NUM_CHANNELS = 8

class Decoder(srd.Decoder):
    api_version = 3
    id = 'parallel'
    name = 'Parallel'
    longname = 'Parallel sync bus'
    desc = 'Generic parallel synchronous bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['parallel']
    optional_channels = channel_list(NUM_CHANNELS)
    options = (
        {'id': 'clock_edge', 'desc': 'Clock edge to sample on',
            'default': 'rising', 'values': ('rising', 'falling')},
        {'id': 'wordsize', 'desc': 'Data wordsize', 'default': 1},
        {'id': 'endianness', 'desc': 'Data endianness',
            'default': 'little', 'values': ('little', 'big')},
    )
    annotations = (
        ('items', 'Items'),
        ('words', 'Words'),
    )

    def __init__(self):
        self.items = []
        self.itemcount = 0
        self.saved_item = None
        self.ss_item = self.es_item = None
        self.first = True
        self.num_channels = 0

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putpb(self, data):
        self.put(self.ss_item, self.es_item, self.out_python, data)

    def putb(self, data):
        self.put(self.ss_item, self.es_item, self.out_ann, data)

    def putpw(self, data):
        self.put(self.ss_word, self.es_word, self.out_python, data)

    def putw(self, data):
        self.put(self.ss_word, self.es_word, self.out_ann, data)

    def handle_bits(self, datapins):
        # If this is the first item in a word, save its sample number.
        if self.itemcount == 0:
            self.ss_word = self.samplenum

        # Get the bits for this item.
        item, used_pins = 0, datapins.count(1) + datapins.count(0)
        for i in range(used_pins):
            item |= datapins[i] << i

        self.items.append(item)
        self.itemcount += 1

        if self.first:
            # Save the start sample and item for later (no output yet).
            self.ss_item = self.samplenum
            self.first = False
            self.saved_item = item
        else:
            # Output the saved item (from the last CLK edge to the current).
            self.es_item = self.samplenum
            self.putpb(['ITEM', self.saved_item])
            self.putb([0, ['%X' % self.saved_item]])
            self.ss_item = self.samplenum
            self.saved_item = item

        endian, ws = self.options['endianness'], self.options['wordsize']

        # Get as many items as the configured wordsize says.
        if self.itemcount < ws:
            return

        # Output annotations/python for a word (a collection of items).
        word = 0
        for i in range(ws):
            if endian == 'little':
                word |= self.items[i] << ((ws - 1 - i) * used_pins)
            elif endian == 'big':
                word |= self.items[i] << (i * used_pins)

        self.es_word = self.samplenum
        # self.putpw(['WORD', word])
        # self.putw([1, ['%X' % word]])
        self.ss_word = self.samplenum

        self.itemcount, self.items = 0, []

    def decode(self):
        for i in range(len(self.optional_channels)):
            if self.has_channel(i):
                self.num_channels += 1

        if self.num_channels == 0:
            raise ChannelError('At least one channel has to be supplied.')

        if not self.has_channel(0):
            # CLK was not supplied, sample on ANY edge of ANY of the pins
            # (but only of those pins that were actually supplied).
            conds = []
            for i in range(1, len(self.optional_channels)):
                if self.has_channel(i):
                    conds.append({i: 'e'})
            while True:
                self.handle_bits(self.wait(conds)[1:])
        else:
            # Sample on the rising or falling CLK edge (depends on config).
            while True:
                pins = self.wait({0: self.options['clock_edge'][0]})
                self.handle_bits(pins[1:])
