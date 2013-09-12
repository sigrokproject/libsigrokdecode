##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2011-2013 Uwe Hermann <uwe@hermann-uwe.de>
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

# UART protocol decoder

import sigrokdecode as srd

'''
Protocol output format:

UART packet:
[<packet-type>, <rxtx>, <packet-data>]

This is the list of <packet-type>s and their respective <packet-data>:
 - 'STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'DATA': The data is the (integer) value of the UART data. Valid values
   range from 0 to 512 (as the data can be up to 9 bits in size).
 - 'PARITYBIT': The data is the (integer) value of the parity bit (0/1).
 - 'STOPBIT': The data is the (integer) value of the stop bit (0 or 1).
 - 'INVALID STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'INVALID STOPBIT': The data is the (integer) value of the stop bit (0/1).
 - 'PARITY ERROR': The data is a tuple with two entries. The first one is
   the expected parity value, the second is the actual parity value.
 - TODO: Frame error?

The <rxtx> field is 0 for RX packets, 1 for TX packets.
'''

# Used for differentiating between the two data directions.
RX = 0
TX = 1

# Given a parity type to check (odd, even, zero, one), the value of the
# parity bit, the value of the data, and the length of the data (5-9 bits,
# usually 8 bits) return True if the parity is correct, False otherwise.
# 'none' is _not_ allowed as value for 'parity_type'.
def parity_ok(parity_type, parity_bit, data, num_data_bits):

    # Handle easy cases first (parity bit is always 1 or 0).
    if parity_type == 'zero':
        return parity_bit == 0
    elif parity_type == 'one':
        return parity_bit == 1

    # Count number of 1 (high) bits in the data (and the parity bit itself!).
    ones = bin(data).count('1') + parity_bit

    # Check for odd/even parity.
    if parity_type == 'odd':
        return (ones % 2) == 1
    elif parity_type == 'even':
        return (ones % 2) == 0
    else:
        raise Exception('Invalid parity type: %d' % parity_type)

class Decoder(srd.Decoder):
    api_version = 1
    id = 'uart'
    name = 'UART'
    longname = 'Universal Asynchronous Receiver/Transmitter'
    desc = 'Asynchronous, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['uart']
    probes = [
        # Allow specifying only one of the signals, e.g. if only one data
        # direction exists (or is relevant).
        {'id': 'rx', 'name': 'RX', 'desc': 'UART receive line'},
        {'id': 'tx', 'name': 'TX', 'desc': 'UART transmit line'},
    ]
    optional_probes = []
    options = {
        'baudrate': ['Baud rate', 115200],
        'num_data_bits': ['Data bits', 8], # Valid: 5-9.
        'parity_type': ['Parity type', 'none'],
        'parity_check': ['Check parity?', 'yes'], # TODO: Bool supported?
        'num_stop_bits': ['Stop bit(s)', '1'], # String! 0, 0.5, 1, 1.5.
        'bit_order': ['Bit order', 'lsb-first'],
        'format': ['Data format', 'ascii'], # ascii/dec/hex/oct/bin
        # TODO: Options to invert the signal(s).
    }
    annotations = [
        ['Data', 'UART data'],
        ['Start bits', 'UART start bits'],
        ['Parity bits', 'UART parity bits'],
        ['Stop bits', 'UART stop bits'],
        ['Warnings', 'Warnings'],
    ]

    def putx(self, rxtx, data):
        s, halfbit = self.startsample[rxtx], int(self.bit_width / 2)
        self.put(s - halfbit, self.samplenum + halfbit, self.out_ann, data)

    def putg(self, data):
        s, halfbit = self.samplenum, int(self.bit_width / 2)
        self.put(s - halfbit, s + halfbit, self.out_ann, data)

    def putp(self, data):
        s, halfbit = self.samplenum, int(self.bit_width / 2)
        self.put(s - halfbit, s + halfbit, self.out_proto, data)

    def __init__(self, **kwargs):
        self.samplenum = 0
        self.frame_start = [-1, -1]
        self.startbit = [-1, -1]
        self.cur_data_bit = [0, 0]
        self.databyte = [0, 0]
        self.paritybit = [-1, -1]
        self.stopbit1 = [-1, -1]
        self.startsample = [-1, -1]
        self.state = ['WAIT FOR START BIT', 'WAIT FOR START BIT']
        self.oldbit = [1, 1]
        self.oldpins = [1, 1]

    def start(self, metadata):
        self.samplerate = metadata['samplerate']
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'uart')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'uart')

        # The width of one UART bit in number of samples.
        self.bit_width = \
            float(self.samplerate) / float(self.options['baudrate'])

    def report(self):
        pass

    # Return true if we reached the middle of the desired bit, false otherwise.
    def reached_bit(self, rxtx, bitnum):
        # bitpos is the samplenumber which is in the middle of the
        # specified UART bit (0 = start bit, 1..x = data, x+1 = parity bit
        # (if used) or the first stop bit, and so on).
        bitpos = self.frame_start[rxtx] + (self.bit_width / 2.0)
        bitpos += bitnum * self.bit_width
        if self.samplenum >= bitpos:
            return True
        return False

    def reached_bit_last(self, rxtx, bitnum):
        bitpos = self.frame_start[rxtx] + ((bitnum + 1) * self.bit_width)
        if self.samplenum >= bitpos:
            return True
        return False

    def wait_for_start_bit(self, rxtx, old_signal, signal):
        # The start bit is always 0 (low). As the idle UART (and the stop bit)
        # level is 1 (high), the beginning of a start bit is a falling edge.
        if not (old_signal == 1 and signal == 0):
            return

        # Save the sample number where the start bit begins.
        self.frame_start[rxtx] = self.samplenum

        self.state[rxtx] = 'GET START BIT'

    def get_start_bit(self, rxtx, signal):
        # Skip samples until we're in the middle of the start bit.
        if not self.reached_bit(rxtx, 0):
            return

        self.startbit[rxtx] = signal

        # The startbit must be 0. If not, we report an error.
        if self.startbit[rxtx] != 0:
            self.putp(['INVALID STARTBIT', rxtx, self.startbit[rxtx]])
            # TODO: Abort? Ignore rest of the frame?

        self.cur_data_bit[rxtx] = 0
        self.databyte[rxtx] = 0
        self.startsample[rxtx] = -1

        self.state[rxtx] = 'GET DATA BITS'

        self.putp(['STARTBIT', rxtx, self.startbit[rxtx]])
        self.putg([1, ['Start bit', 'Start', 'S']])

    def get_data_bits(self, rxtx, signal):
        # Skip samples until we're in the middle of the desired data bit.
        if not self.reached_bit(rxtx, self.cur_data_bit[rxtx] + 1):
            return

        # Save the sample number of the middle of the first data bit.
        if self.startsample[rxtx] == -1:
            self.startsample[rxtx] = self.samplenum

        # Get the next data bit in LSB-first or MSB-first fashion.
        if self.options['bit_order'] == 'lsb-first':
            self.databyte[rxtx] >>= 1
            self.databyte[rxtx] |= \
                (signal << (self.options['num_data_bits'] - 1))
        elif self.options['bit_order'] == 'msb-first':
            self.databyte[rxtx] <<= 1
            self.databyte[rxtx] |= (signal << 0)
        else:
            raise Exception('Invalid bit order value: %s',
                            self.options['bit_order'])

        # Return here, unless we already received all data bits.
        if self.cur_data_bit[rxtx] < self.options['num_data_bits'] - 1:
            self.cur_data_bit[rxtx] += 1
            return

        self.state[rxtx] = 'GET PARITY BIT'

        self.putp(['DATA', rxtx, self.databyte[rxtx]])

        s = 'RX: ' if (rxtx == RX) else 'TX: '
        b, f = self.databyte[rxtx], self.options['format']
        if f == 'ascii':
            self.putx(rxtx, [0, [s + chr(b)]])
        elif f == 'dec':
            self.putx(rxtx, [0, [s + str(b)]])
        elif f == 'hex':
            self.putx(rxtx, [0, [s + hex(b)[2:]]])
        elif f == 'oct':
            self.putx(rxtx, [0, [s + oct(b)[2:]]])
        elif f == 'bin':
            self.putx(rxtx, [0, [s + bin(b)[2:]]])
        else:
            raise Exception('Invalid data format option: %s' % f)

    def get_parity_bit(self, rxtx, signal):
        # If no parity is used/configured, skip to the next state immediately.
        if self.options['parity_type'] == 'none':
            self.state[rxtx] = 'GET STOP BITS'
            return

        # Skip samples until we're in the middle of the parity bit.
        if not self.reached_bit(rxtx, self.options['num_data_bits'] + 1):
            return

        self.paritybit[rxtx] = signal

        self.state[rxtx] = 'GET STOP BITS'

        if parity_ok(self.options['parity_type'], self.paritybit[rxtx],
                     self.databyte[rxtx], self.options['num_data_bits']):
            self.putp(['PARITYBIT', rxtx, self.paritybit[rxtx]])
            self.putg([2, ['Parity bit', 'Parity', 'P']])
        else:
            # TODO: Return expected/actual parity values.
            self.putp(['PARITY ERROR', rxtx, (0, 1)]) # FIXME: Dummy tuple...
            self.putg([4, ['Parity error', 'Parity err', 'PE']])

    # TODO: Currently only supports 1 stop bit.
    def get_stop_bits(self, rxtx, signal):
        # Skip samples until we're in the middle of the stop bit(s).
        skip_parity = 0 if self.options['parity_type'] == 'none' else 1
        b = self.options['num_data_bits'] + 1 + skip_parity
        if not self.reached_bit(rxtx, b):
            return

        self.stopbit1[rxtx] = signal

        # Stop bits must be 1. If not, we report an error.
        if self.stopbit1[rxtx] != 1:
            self.putp(['INVALID STOPBIT', rxtx, self.stopbit1[rxtx]])
            self.putg([4, ['Frame error', 'Frame err', 'FE']])
            # TODO: Abort? Ignore the frame? Other?

        self.state[rxtx] = 'WAIT FOR START BIT'

        self.putp(['STOPBIT', rxtx, self.stopbit1[rxtx]])
        self.putg([3, ['Stop bit', 'Stop', 'T']])

    def decode(self, ss, es, data):
        # TODO: Either RX or TX could be omitted (optional probe).
        for (self.samplenum, pins) in data:

            # Note: Ignoring identical samples here for performance reasons
            # is not possible for this PD, at least not in the current state.
            # if self.oldpins == pins:
            #     continue
            self.oldpins, (rx, tx) = pins, pins

            # State machine.
            for rxtx in (RX, TX):
                signal = rx if (rxtx == RX) else tx

                if self.state[rxtx] == 'WAIT FOR START BIT':
                    self.wait_for_start_bit(rxtx, self.oldbit[rxtx], signal)
                elif self.state[rxtx] == 'GET START BIT':
                    self.get_start_bit(rxtx, signal)
                elif self.state[rxtx] == 'GET DATA BITS':
                    self.get_data_bits(rxtx, signal)
                elif self.state[rxtx] == 'GET PARITY BIT':
                    self.get_parity_bit(rxtx, signal)
                elif self.state[rxtx] == 'GET STOP BITS':
                    self.get_stop_bits(rxtx, signal)
                else:
                    raise Exception('Invalid state: %s' % self.state[rxtx])

                # Save current RX/TX values for the next round.
                self.oldbit[rxtx] = signal

