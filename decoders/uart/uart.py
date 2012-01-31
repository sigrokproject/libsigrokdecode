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

#
# UART protocol decoder
#

#
# Universal Asynchronous Receiver Transmitter (UART) is a simple serial
# communication protocol which allows two devices to talk to each other.
#
# It uses just two data signals and a ground (GND) signal:
#  - RX/RXD: Receive signal
#  - TX/TXD: Transmit signal
#
# The protocol is asynchronous, i.e., there is no dedicated clock signal.
# Rather, both devices have to agree on a baudrate (number of bits to be
# transmitted per second) beforehand. Baudrates can be arbitrary in theory,
# but usually the choice is limited by the hardware UARTs that are used.
# Common values are 9600 or 115200.
#
# The protocol allows full-duplex transmission, i.e. both devices can send
# data at the same time. However, unlike SPI (which is always full-duplex,
# i.e., each send operation is automatically also a receive operation), UART
# allows one-way communication, too. In such a case only one signal (and GND)
# is required.
#
# The data is sent over the TX line in so-called 'frames', which consist of:
#  - Exactly one start bit (always 0/low).
#  - Between 5 and 9 data bits.
#  - An (optional) parity bit.
#  - One or more stop bit(s).
#
# The idle state of the RX/TX line is 1/high. As the start bit is 0/low, the
# receiver can continually monitor its RX line for a falling edge, in order
# to detect the start bit.
#
# Once detected, it can (due to the agreed-upon baudrate and thus the known
# width/duration of one UART bit) sample the state of the RX line "in the
# middle" of each (start/data/parity/stop) bit it wants to analyze.
#
# It is configurable whether there is a parity bit in a frame, and if yes,
# which type of parity is used:
#  - None: No parity bit is included.
#  - Odd: The number of 1 bits in the data (and parity bit itself) is odd.
#  - Even: The number of 1 bits in the data (and parity bit itself) is even.
#  - Mark/one: The parity bit is always 1/high (also called 'mark state').
#  - Space/zero: The parity bit is always 0/low (also called 'space state').
#
# It is also configurable how many stop bits are to be used:
#  - 1 stop bit (most common case)
#  - 2 stop bits
#  - 1.5 stop bits (i.e., one stop bit, but 1.5 times the UART bit width)
#  - 0.5 stop bits (i.e., one stop bit, but 0.5 times the UART bit width)
#
# The bit order of the 5-9 data bits is LSB-first.
#
# Possible special cases:
#  - One or both data lines could be inverted, which also means that the idle
#    state of the signal line(s) is low instead of high.
#  - Only the data bits on one or both data lines (and the parity bit) could
#    be inverted (but the start/stop bits remain non-inverted).
#  - The bit order could be MSB-first instead of LSB-first.
#  - The baudrate could change in the middle of the communication. This only
#    happens in very special cases, and can only work if both devices know
#    to which baudrate they are to switch, and when.
#  - Theoretically, the baudrate on RX and the one on TX could also be
#    different, but that's a very obscure case and probably doesn't happen
#    very often in practice.
#
# Error conditions:
#  - If there is a parity bit, but it doesn't match the expected parity,
#    this is called a 'parity error'.
#  - If there are no stop bit(s), that's called a 'frame error'.
#
# More information:
# TODO: URLs
#

#
# Protocol output format:
#
# UART packet:
# [<packet-type>, <rxtx>, <packet-data>]
#
# This is the list of <packet-types>s and their respective <packet-data>:
#  - T_START: The data is the (integer) value of the start bit (0 or 1).
#  - T_DATA: The data is the (integer) value of the UART data. Valid values
#    range from 0 to 512 (as the data can be up to 9 bits in size).
#  - T_PARITY: The data is the (integer) value of the parity bit (0 or 1).
#  - T_STOP: The data is the (integer) value of the stop bit (0 or 1).
#  - T_INVALID_START: The data is the (integer) value of the start bit (0 or 1).
#  - T_INVALID_STOP: The data is the (integer) value of the stop bit (0 or 1).
#  - T_PARITY_ERROR: The data is a tuple with two entries. The first one is
#    the expected parity value, the second is the actual parity value.
#
# The <rxtx> field is 0 for RX packets, 1 for TX packets.
#

import sigrokdecode as srd

# States
WAIT_FOR_START_BIT = 0
GET_START_BIT = 1
GET_DATA_BITS = 2
GET_PARITY_BIT = 3
GET_STOP_BITS = 4

# Used for differentiating between the two data directions.
RX = 0
TX = 1

# Parity options
PARITY_NONE = 0
PARITY_ODD = 1
PARITY_EVEN = 2
PARITY_ZERO = 3
PARITY_ONE = 4

# Stop bit options
STOP_BITS_0_5 = 0
STOP_BITS_1 = 1
STOP_BITS_1_5 = 2
STOP_BITS_2 = 3

# Bit order options
LSB_FIRST = 0
MSB_FIRST = 1

# Annotation feed formats
ANN_ASCII = 0
ANN_DEC = 1
ANN_HEX = 2
ANN_OCT = 3
ANN_BITS = 4

# Protocol output packet types
T_START = 0
T_DATA = 1
T_PARITY = 2
T_STOP = 3
T_INVALID_START = 4
T_INVALID_STOP = 5
T_PARITY_ERROR = 6

# Given a parity type to check (odd, even, zero, one), the value of the
# parity bit, the value of the data, and the length of the data (5-9 bits,
# usually 8 bits) return True if the parity is correct, False otherwise.
# PARITY_NONE is _not_ allowed as value for 'parity_type'.
def parity_ok(parity_type, parity_bit, data, num_data_bits):

    # Handle easy cases first (parity bit is always 1 or 0).
    if parity_type == PARITY_ZERO:
        return parity_bit == 0
    elif parity_type == PARITY_ONE:
        return parity_bit == 1

    # Count number of 1 (high) bits in the data (and the parity bit itself!).
    ones = bin(data).count('1') + parity_bit

    # Check for odd/even parity.
    if parity_type == PARITY_ODD:
        return (ones % 2) == 1
    elif parity_type == PARITY_EVEN:
        return (ones % 2) == 0
    else:
        raise Exception('Invalid parity type: %d' % parity_type)

class Decoder(srd.Decoder):
    api_version = 1
    id = 'uart'
    name = 'UART'
    longname = 'Universal Asynchronous Receiver/Transmitter'
    desc = 'Universal Asynchronous Receiver/Transmitter (UART)'
    longdesc = 'TODO.'
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
        'parity_type': ['Parity type', PARITY_NONE],
        'parity_check': ['Check parity?', True], # TODO: Bool supported?
        'num_stop_bits': ['Stop bit(s)', STOP_BITS_1],
        'bit_order': ['Bit order', LSB_FIRST],
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
        self.stopbit1 = [-1, -1]
        self.startsample = [-1, -1]

        # Initial state.
        self.state = [WAIT_FOR_START_BIT, WAIT_FOR_START_BIT]

        self.oldbit = [None, None]

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

        self.state[rxtx] = GET_START_BIT

    def get_start_bit(self, rxtx, signal):
        # Skip samples until we're in the middle of the start bit.
        if not self.reached_bit(rxtx, 0):
            return

        self.startbit[rxtx] = signal

        # The startbit must be 0. If not, we report an error.
        if self.startbit[rxtx] != 0:
            self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                     [T_INVALID_START, rxtx, self.startbit[rxtx]])
            # TODO: Abort? Ignore rest of the frame?

        self.cur_data_bit[rxtx] = 0
        self.databyte[rxtx] = 0
        self.startsample[rxtx] = -1

        self.state[rxtx] = GET_DATA_BITS

        self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                 [T_START, rxtx, self.startbit[rxtx]])
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
        if self.options['bit_order'] == LSB_FIRST:
            self.databyte[rxtx] >>= 1
            self.databyte[rxtx] |= \
                (signal << (self.options['num_data_bits'] - 1))
        elif self.options['bit_order'] == MSB_FIRST:
            self.databyte[rxtx] <<= 1
            self.databyte[rxtx] |= (signal << 0)
        else:
            raise Exception('Invalid bit order value: %d',
                            self.options['bit_order'])

        # Return here, unless we already received all data bits.
        # TODO? Off-by-one?
        if self.cur_data_bit[rxtx] < self.options['num_data_bits'] - 1:
            self.cur_data_bit[rxtx] += 1
            return

        self.state[rxtx] = GET_PARITY_BIT

        self.put(self.startsample[rxtx], self.samplenum - 1, self.out_proto,
                 [T_DATA, rxtx, self.databyte[rxtx]])

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
        if self.options['parity_type'] == PARITY_NONE:
            self.state[rxtx] = GET_STOP_BITS
            return

        # Skip samples until we're in the middle of the parity bit.
        if not self.reached_bit(rxtx, self.options['num_data_bits'] + 1):
            return

        self.paritybit[rxtx] = signal

        self.state[rxtx] = GET_STOP_BITS

        if parity_ok(self.options['parity_type'], self.paritybit[rxtx],
                     self.databyte[rxtx], self.options['num_data_bits']):
            # TODO: Fix range.
            self.put(self.samplenum, self.samplenum, self.out_proto,
                     [T_PARITY_BIT, rxtx, self.paritybit[rxtx]])
            self.put(self.samplenum, self.samplenum, self.out_ann,
                     [ANN_ASCII, ['Parity bit', 'Parity', 'P']])
        else:
            # TODO: Fix range.
            # TODO: Return expected/actual parity values.
            self.put(self.samplenum, self.samplenum, self.out_proto,
                     [T_PARITY_ERROR, rxtx, (0, 1)]) # FIXME: Dummy tuple...
            self.put(self.samplenum, self.samplenum, self.out_ann,
                     [ANN_ASCII, ['Parity error', 'Parity err', 'PE']])

    # TODO: Currently only supports 1 stop bit.
    def get_stop_bits(self, rxtx, signal):
        # Skip samples until we're in the middle of the stop bit(s).
        skip_parity = 0 if self.options['parity_type'] == PARITY_NONE else 1
        b = self.options['num_data_bits'] + 1 + skip_parity
        if not self.reached_bit(rxtx, b):
            return

        self.stopbit1[rxtx] = signal

        # Stop bits must be 1. If not, we report an error.
        if self.stopbit1[rxtx] != 1:
            self.put(self.frame_start[rxtx], self.samplenum, self.out_proto,
                     [T_INVALID_STOP, rxtx, self.stopbit1[rxtx]])
            # TODO: Abort? Ignore the frame? Other?

        self.state[rxtx] = WAIT_FOR_START_BIT

        # TODO: Fix range.
        self.put(self.samplenum, self.samplenum, self.out_proto,
                 [T_STOP, rxtx, self.stopbit1[rxtx]])
        self.put(self.samplenum, self.samplenum, self.out_ann,
                 [ANN_ASCII, ['Stop bit', 'Stop', 'P']])

    def decode(self, ss, es, data):
        # TODO: Either RX or TX could be omitted (optional probe).
        for (samplenum, (rx, tx)) in data:

            # TODO: Start counting at 0 or 1? Increase before or after?
            self.samplenum += 1

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

                if self.state[rxtx] == WAIT_FOR_START_BIT:
                    self.wait_for_start_bit(rxtx, self.oldbit[rxtx], signal)
                elif self.state[rxtx] == GET_START_BIT:
                    self.get_start_bit(rxtx, signal)
                elif self.state[rxtx] == GET_DATA_BITS:
                    self.get_data_bits(rxtx, signal)
                elif self.state[rxtx] == GET_PARITY_BIT:
                    self.get_parity_bit(rxtx, signal)
                elif self.state[rxtx] == GET_STOP_BITS:
                    self.get_stop_bits(rxtx, signal)
                else:
                    raise Exception('Invalid state: %d' % self.state[rxtx])

                # Save current RX/TX values for the next round.
                self.oldbit[rxtx] = signal

