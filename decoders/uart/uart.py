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

# UART protocol decoder

import sigrokdecode as srd

# Used for differentiating between the two data directions.
RX = 0
TX = 1

# Annotation feed formats
ANN_ASCII = 0
ANN_DEC = 1
ANN_HEX = 2
ANN_OCT = 3
ANN_BITS = 4

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
        # TODO: Options to invert the signal(s).
    }
    annotations = [
        ['ASCII', 'Data bytes as ASCII characters'],
        ['Decimal', 'Databytes as decimal, integer values'],
        ['Hex', 'Data bytes in hex format'],
        ['Octal', 'Data bytes as octal numbers'],
        ['Bits', 'Data bytes in bit notation (sequence of 0/1 digits)'],
    ]

    def putx(self, rxtx, data):
        self.put(self.startsample[rxtx], self.samplenum - 1, self.out_ann, data)

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
        self.oldbit = [None, None]
        self.oldpins = None

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
            self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                     ['INVALID STARTBIT', rxtx, self.startbit[rxtx]])
            # TODO: Abort? Ignore rest of the frame?

        self.cur_data_bit[rxtx] = 0
        self.databyte[rxtx] = 0
        self.startsample[rxtx] = -1

        self.state[rxtx] = 'GET DATA BITS'

        self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                 ['STARTBIT', rxtx, self.startbit[rxtx]])
        self.put(self.frame_start[rxtx], self.samplenum, self.out_ann,
                 [ANN_ASCII, ['Start bit', 'Start', 'S']])

    def get_data_bits(self, rxtx, signal):
        # Skip samples until we're in the middle of the desired data bit.
        if not self.reached_bit(rxtx, self.cur_data_bit[rxtx] + 1):
            return

        # Save the sample number where the data byte starts.
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
        # TODO? Off-by-one?
        if self.cur_data_bit[rxtx] < self.options['num_data_bits'] - 1:
            self.cur_data_bit[rxtx] += 1
            return

        self.state[rxtx] = 'GET PARITY BIT'

        self.put(self.startsample[rxtx], self.samplenum - 1, self.out_proto,
                 ['DATA', rxtx, self.databyte[rxtx]])

        s = 'RX: ' if (rxtx == RX) else 'TX: '
        self.putx(rxtx, [ANN_ASCII, [s + chr(self.databyte[rxtx])]])
        self.putx(rxtx, [ANN_DEC,   [s + str(self.databyte[rxtx])]])
        self.putx(rxtx, [ANN_HEX,   [s + hex(self.databyte[rxtx]),
                                     s + hex(self.databyte[rxtx])[2:]]])
        self.putx(rxtx, [ANN_OCT,   [s + oct(self.databyte[rxtx]),
                                     s + oct(self.databyte[rxtx])[2:]]])
        self.putx(rxtx, [ANN_BITS,  [s + bin(self.databyte[rxtx]),
                                     s + bin(self.databyte[rxtx])[2:]]])

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
            # TODO: Fix range.
            self.put(self.samplenum, self.samplenum, self.out_proto,
                     ['PARITYBIT', rxtx, self.paritybit[rxtx]])
            self.put(self.samplenum, self.samplenum, self.out_ann,
                     [ANN_ASCII, ['Parity bit', 'Parity', 'P']])
        else:
            # TODO: Fix range.
            # TODO: Return expected/actual parity values.
            self.put(self.samplenum, self.samplenum, self.out_proto,
                     ['PARITY ERROR', rxtx, (0, 1)]) # FIXME: Dummy tuple...
            self.put(self.samplenum, self.samplenum, self.out_ann,
                     [ANN_ASCII, ['Parity error', 'Parity err', 'PE']])

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
            self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                     ['INVALID STOPBIT', rxtx, self.stopbit1[rxtx]])
            # TODO: Abort? Ignore the frame? Other?

        self.state[rxtx] = 'WAIT FOR START BIT'

        # TODO: Fix range.
        self.put(self.samplenum, self.samplenum, self.out_proto,
                 ['STOPBIT', rxtx, self.stopbit1[rxtx]])
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [ANN_ASCII, ['Stop bit', 'Stop', 'P']])

    def decode(self, ss, es, data):
        # TODO: Either RX or TX could be omitted (optional probe).
        for (self.samplenum, pins) in data:

            # Note: Ignoring identical samples here for performance reasons
            # is not possible for this PD, at least not in the current state.
            # if self.oldpins == pins:
            #     continue
            self.oldpins, (rx, tx) = pins, pins

            # First sample: Save RX/TX value.
            if self.oldbit[RX] == None:
                self.oldbit[RX] = rx
                continue
            if self.oldbit[TX] == None:
                self.oldbit[TX] = tx
                continue

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
                    raise Exception('Invalid state: %d' % self.state[rxtx])

                # Save current RX/TX values for the next round.
                self.oldbit[rxtx] = signal

