##
## This file is part of the sigrok project.
##
## Copyright (C) 2011-2012 Uwe Hermann <uwe@hermann-uwe.de>
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
ANN_ASCII = 0
ANN_DEC = 1
ANN_HEX = 2
ANN_OCT = 3
ANN_BITS = 4

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire'
    name = '1-Wire'
    longname = ''
    desc = '1-Wire bus and MicroLan'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['onewire']
    probes = [
        {'id': 'owr', 'name': 'OWR', 'desc': '1-Wire bus'},
    ]
    optional_probes = [
        {'id': 'pwr', 'name': 'PWR', 'desc': '1-Wire power'},
    ]
    options = {
        'overdrive': ['Overdrive', 0],
    }
    annotations = [
        ['ASCII', 'Data bytes as ASCII characters'],
        ['Decimal', 'Databytes as decimal, integer values'],
        ['Hex', 'Data bytes in hex format'],
        ['Octal', 'Data bytes as octal numbers'],
        ['Bits', 'Data bytes in bit notation (sequence of 0/1 digits)'],
    ]

    def putx(self, data):
        self.put(self.startsample, self.samplenum - 1, self.out_ann, data)

    def __init__(self, **kwargs):
        # Common variables
        self.samplenum = 0
        # Link layer variables
        self.lnk_state = 'WAIT FOR EVENT'
        self.lnk_event = 'NONE'
        self.lnk_start = -1
        self.lnk_bit   = -1
        self.lnk_cnt   = 0
        self.lnk_byte  = -1
        # Network layer variables
        self.net_state = 'WAIT FOR EVENT'
        self.net_event = 'NONE'
        self.net_command = -1
        # Transport layer variables
        self.trn_state = 'WAIT FOR EVENT'
        self.trn_event = 'NONE'

        self.data_sample = -1
        self.cur_data_bit = 0
        self.databyte = 0
        self.startsample = -1

    def start(self, metadata):
        self.samplerate = metadata['samplerate']
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'onewire')

        # The width of the 1-Wire time base (30us) in number of samples.
        # TODO: optimize this value
        self.time_base = float(self.samplerate) / float(0.000030)

    def report(self):
        pass

    def get_data_sample(self, owr):
        # Skip samples until we're in the middle of the start bit.
        if not self.reached_data_sample():
            return

        self.data_sample = owr

        self.cur_data_bit = 0
        self.databyte = 0
        self.startsample = -1

        self.state = 'GET DATA BITS'

        self.put(self.cycle_start, self.samplenum, self.out_proto,
                 ['STARTBIT', self.startbit])
        self.put(self.cycle_start, self.samplenum, self.out_ann,
                 [ANN_ASCII, ['Start bit', 'Start', 'S']])

    def get_data_bits(self, owr):
        # Skip samples until we're in the middle of the desired data bit.
        if not self.reached_bit(self.cur_data_bit + 1):
            return

        # Save the sample number where the data byte starts.
        if self.startsample == -1:
            self.startsample = self.samplenum

        # Get the next data bit in LSB-first or MSB-first fashion.
        if self.options['bit_order'] == 'lsb-first':
            self.databyte >>= 1
            self.databyte |= \
                (owr << (self.options['num_data_bits'] - 1))
        elif self.options['bit_order'] == 'msb-first':
            self.databyte <<= 1
            self.databyte |= (owr << 0)
        else:
            raise Exception('Invalid bit order value: %s',
                            self.options['bit_order'])

        # Return here, unless we already received all data bits.
        # TODO? Off-by-one?
        if self.cur_data_bit < self.options['num_data_bits'] - 1:
            self.cur_data_bit += 1
            return

        self.state = 'GET PARITY BIT'

        self.put(self.startsample, self.samplenum - 1, self.out_proto,
                 ['DATA', self.databyte])

        self.putx([ANN_ASCII, [chr(self.databyte)]])
        self.putx([ANN_DEC,   [str(self.databyte)]])
        self.putx([ANN_HEX,   [hex(self.databyte),
                               hex(self.databyte)[2:]]])
        self.putx([ANN_OCT,   [oct(self.databyte),
                               oct(self.databyte)[2:]]])
        self.putx([ANN_BITS,  [bin(self.databyte),
                               bin(self.databyte)[2:]]])

    def decode(self, ss, es, data):
        for (self.samplenum, owr) in data:

            # First sample: Save OWR value.
            if self.oldbit == None:
                self.oldbit = owr
                continue

            # Data link layer
            if self.lnk_state == 'WAIT FOR FALLING EDGE':
                # The start of a cycle is a falling edge.
                if (old_owr == 1 and owr == 0):
                    # Save the sample number where the start bit begins.
                    self.lnk_start = self.samplenum
                    # Go to waiting for sample time
                    self.lnk_state = 'WAIT FOR SAMPLE'
            elif self.lnk_state == 'WAIT FOR SAMPLE':
                # Data should be sample one 'time unit' after a falling edge
                if (self.samplenum == self.lnk_start + self.time_base):
                    self.lnk_bit  = owr & 0x1
                    self.lnk_cnt  = self.lnk_cnt + 1
                    self.lnk_byte = (self.lnk_byte << 1) & self.lnk_bit
                    self.lnk_state = 'WAIT FOR RISING EDGE'
            elif self.lnk_state == 'WAIT FOR RISING EDGE':
                # The end of a cycle is a rising edge.
                if (old_owr == 0 and owr == 1):
                    # Data bit cycle length should be between 2*T and 
                    if (self.samplenum < self.lnk_start + 2*self.time_base):
                        if (self.lnk_cnt == 8)
                            self.put(self.startsample, self.samplenum - 1, self.out_proto, ['BYTE', self.lnk_byte])
                            self.lnk_cnt = 0
                    if (self.samplenum == self.lnk_start + 8*self.time_base):
                        self.put(self.startsample, self.samplenum - 1, self.out_proto, ['RESET'])
                    
                    # Go to waiting for sample time
                    self.lnk_state = 'WAIT FOR SAMPLE'

            elif self.state_lnk == 'GET DATA BITS'   : self.get_data_bits(owr)
            else                                     : raise Exception('Invalid state: %d' % self.state)

            # Save current RX/TX values for the next round.
            self.oldbit = owr

