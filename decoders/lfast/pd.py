##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Soeren Apel <soeren@apelpie.net>
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
from common.srdhelper import bitpack
import decimal

'''
OUTPUT_PYTHON format:

[<data>] where <data> is the payload contained between the LFAST header and
the LFAST stop bit. It's an array of bytes. 
'''

ann_bit, ann_sync, ann_header, ann_payload, ann_stopbit, ann_warning = range(6)
state_sync, state_header, state_payload, state_stopbit = range(4)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'lfast'
    name = 'LFAST'
    longname = 'NXP LFAST interface'
    desc = 'Differential high-speed P2P interface'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['lfast']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'TXP or RXP'},
    )
    annotations = (
        ('bit', 'Bits'),
        ('sync', 'Sync Pattern'),
        ('header', 'Header'),
        ('payload', 'Payload'),
        ('stop', 'Stop Bit'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (ann_bit,)),
        ('fields', 'Fields', (ann_sync, ann_header, ann_payload, ann_stopbit,)),
        ('warnings', 'Warnings', (ann_warning,)),
    )

    def __init__(self):
        decimal.getcontext().rounding = decimal.ROUND_HALF_UP
        self.reset()

    def reset(self):
        self.ss = self.es = 0
        self.ss_payload = self.es_payload = 0
        self.bits = []
        self.payload = []
        self.bit_len = 0
        self.timeout = 0
        self.state = state_sync

    def metadata(self, key, value):
        pass

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def put_ann(self, ss, es, ann_class, value):
        self.put(ss, es, self.out_ann, [ann_class, value])

    def put_payload(self):
        self.put(self.ss_payload, self.es_payload, self.out_python, self.payload)

    def handle_sync(self):
        if len(self.bits) == 1:
            self.ss_sync = self.ss_bit

        if len(self.bits) == 16:
            value = bitpack(self.bits)
            if value == 0xA84B:
                self.put_ann(self.ss_sync, self.es_bit, ann_sync, ['Sync OK'])
            else:
                self.put_ann(self.ss_sync, self.es_bit, ann_warning, ['Wrong Sync Value: {:2X}'.format(value)])

            self.bits = []
            self.state = state_header

    def handle_header(self):
        if len(self.bits) == 1:
            self.ss_header = self.ss_bit

        if len(self.bits) == 8:
            value = bitpack(self.bits)
            self.put_ann(self.ss_header, self.es_bit, ann_header, ['{:2X}'.format(value)])
            self.bits = []
            self.state = state_payload

    def handle_payload(self):
        # 8 bit times without state change are possible (8 low bits) but when
        # there are 9 bit times without state change, we should have seen the
        # stop bit - and only the stop bit
        self.timeout = int(9 * self.bit_len)

        if len(self.bits) == 1:
            self.ss_byte = self.ss_bit
            if self.ss_payload == 0:
                self.ss_payload = self.ss_bit

        if len(self.bits) == 8:
            value = bitpack(self.bits)
            self.put_ann(self.ss_byte, self.es_bit, ann_payload, ['{:2X}'.format(value)])
            self.bits = []
            self.payload.append(value)
            self.es_payload = self.es_bit

    def handle_stopbit(self):
        if len(self.bits) > 1:
            self.put_ann(self.ss_bit, self.es_bit, ann_warning, ['Expected only the stop bit, got {} bits'.format(len(self.bits))])
        else:
            if self.bits[0] == 1: 
                self.put_ann(self.ss_bit, self.es_bit, ann_stopbit, ['Stop Bit', 'Stop', 'S'])
            else:
                self.put_ann(self.ss_bit, self.es_bit, ann_warning, ['Stop Bit must be 1', 'Stop not 1', 'S'])

        # We send the payload out regardless of the stop bit's status so that
        # any intermediate results can be decoded by a stacked decoder
        self.put_payload()
        self.payload = []
        self.ss_payload = 0
        
        self.timeout = 0
        self.bits = []
        self.state = state_sync

    def decode(self):
        while True:
            if self.timeout == 0:
                rising_edge, = self.wait({0: 'e'})
            else:
                rising_edge, = self.wait([{0: 'e'}, {'skip': self.timeout}])

            # If this is the first bit, we only update ss
            if self.ss == 0:
                self.ss = self.samplenum
                continue
        
            self.es = self.samplenum

            # Check for the stop bit if this is a timeout condition
            if (self.timeout > 0) and (self.es - self.ss >= self.timeout):
                self.handle_stopbit()
                continue

            # We use the first bit to deduce the bit length
            if self.bit_len == 0:
                self.bit_len = self.es - self.ss

            # Determine number of bits covered by this edge
            bit_count = (self.es - self.ss) / self.bit_len
            bit_count = int(decimal.Decimal(bit_count).to_integral_value())

            bit_value = '0' if rising_edge else '1'

            divided_len = (self.es - self.ss) / bit_count
            for i in range(bit_count):
                self.ss_bit = int(self.ss + i * divided_len)
                self.es_bit = int(self.ss_bit + divided_len)
                self.put_ann(self.ss_bit, self.es_bit, ann_bit, [bit_value])

                # Place the new bit at the front of the bit list
                self.bits.insert(0, (0 if rising_edge else 1))

                if self.state == state_sync:
                    self.handle_sync()
                elif self.state == state_header:
                    self.handle_header()
                elif self.state == state_payload:
                    self.handle_payload()

            self.ss = self.samplenum
