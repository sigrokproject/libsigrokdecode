##
## This file is part of the sigrok project.
##
## Copyright (C) 2011 Uwe Hermann <uwe@hermann-uwe.de>
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

import sigrok

# States
WAIT_FOR_START_BIT = 0
GET_START_BIT = 1
GET_DATA_BITS = 2
GET_PARITY_BIT = 3
GET_STOP_BITS = 4

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

# Output data formats
DATA_FORMAT_ASCII = 0
DATA_FORMAT_HEX = 1

# TODO: Remove me later.
quick_hack = 1

class Sample():
    def __init__(self, data):
        self.data = data
    def probe(self, probe):
        s = ord(self.data[probe / 8]) & (1 << (probe % 8))
        return True if s else False

def sampleiter(data, unitsize):
    for i in range(0, len(data), unitsize):
        yield(Sample(data[i:i+unitsize]))

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
    parity = bin(data).count('1') + parity_bit

    # Check for odd/even parity.
    if parity_type == PARITY_ODD:
        return (parity % 2) == 1
    elif parity_type == PARITY_EVEN:
        return (parity % 2) == 0
    else:
        raise Exception('Invalid parity type: %d' % parity_type)

class Decoder(sigrok.Decoder):
    id = 'uart'
    name = 'UART'
    longname = 'Universal Asynchronous Receiver/Transmitter (UART)'
    desc = 'Universal Asynchronous Receiver/Transmitter (UART)'
    longdesc = 'TODO.'
    author = 'Uwe Hermann'
    email = 'uwe@hermann-uwe.de'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['uart']
    probes = {
        # Allow specifying only one of the signals, e.g. if only one data
        # direction exists (or is relevant).
        ## 'rx': {'ch': 0, 'name': 'RX', 'desc': 'UART receive line'},
        ## 'tx': {'ch': 1, 'name': 'TX', 'desc': 'UART transmit line'},
        'rx': 0,
        'tx': 1,
    }
    options = {
        'baudrate': ['UART baud rate', 115200],
        'num_data_bits': ['Data bits', 8], # Valid: 5-9.
        'parity': ['Parity', PARITY_NONE],
        'parity_check': ['Check parity', True],
        'num_stop_bits': ['Stop bit(s)', STOP_BITS_1],
        'bit_order': ['Bit order', LSB_FIRST],
        'data_format': ['Output data format', DATA_FORMAT_ASCII],
        # TODO: Options to invert the signal(s).
        # ...
    }

    def __init__(self, **kwargs):
        self.probes = Decoder.probes.copy()

        # Set defaults, can be overridden in 'start'.
        self.baudrate = 115200
        self.num_data_bits = 8
        self.parity = PARITY_NONE
        self.check_parity = True
        self.num_stop_bits = 1
        self.bit_order = LSB_FIRST
        self.data_format = DATA_FORMAT_ASCII

        self.samplenum = 0
        self.frame_start = -1
        self.startbit = -1
        self.cur_data_bit = 0
        self.databyte = 0
        self.stopbit1 = -1
        self.startsample = -1

        # Initial state.
        self.staterx = WAIT_FOR_START_BIT

        # Get the channel/probe number of the RX/TX signals.
        ## self.rx_bit = self.probes['rx']['ch']
        ## self.tx_bit = self.probes['tx']['ch']
        self.rx_bit = self.probes['rx']
        self.tx_bit = self.probes['tx']

        self.oldrx = None
        self.oldtx = None

    def start(self, metadata):
        self.unitsize = metadata['unitsize']
        self.samplerate = metadata['samplerate']

        # TODO
        ### self.baudrate = metadata['baudrate']
        ### self.num_data_bits = metadata['num_data_bits']
        ### self.parity = metadata['parity']
        ### self.parity_check = metadata['parity_check']
        ### self.num_stop_bits = metadata['num_stop_bits']
        ### self.bit_order = metadata['bit_order']
        ### self.data_format = metadata['data_format']

        # The width of one UART bit in number of samples.
        self.bit_width = float(self.samplerate) / float(self.baudrate)

    def report(self):
        pass

    # Return true if we reached the middle of the desired bit, false otherwise.
    def reached_bit(self, bitnum):
        # bitpos is the samplenumber which is in the middle of the
        # specified UART bit (0 = start bit, 1..x = data, x+1 = parity bit
        # (if used) or the first stop bit, and so on).
        bitpos = self.frame_start + (self.bit_width / 2.0)
        bitpos += bitnum * self.bit_width
        if self.samplenum >= bitpos:
            return True
        return False

    def reached_bit_last(self, bitnum):
        bitpos = self.frame_start + ((bitnum + 1) * self.bit_width)
        if self.samplenum >= bitpos:
            return True
        return False

    def wait_for_start_bit(self, old_signal, signal):
        # The start bit is always 0 (low). As the idle UART (and the stop bit)
        # level is 1 (high), the beginning of a start bit is a falling edge.
        if not (old_signal == 1 and signal == 0):
            return

        # Save the sample number where the start bit begins.
        self.frame_start = self.samplenum

        self.staterx = GET_START_BIT

    def get_start_bit(self, signal):
        # Skip samples until we're in the middle of the start bit.
        if not self.reached_bit(0):
            return []

        self.startbit = signal

        if self.startbit != 0:
            # TODO: Startbit must be 0. If not, we report an error.
            pass

        self.cur_data_bit = 0
        self.databyte = 0
        self.startsample = -1

        self.staterx = GET_DATA_BITS

        if quick_hack: # TODO
            return []

        o = [{'type': 'S', 'range': (self.frame_start, self.samplenum),
             'data': None, 'ann': 'Start bit'}]
        return o

    def get_data_bits(self, signal):
        # Skip samples until we're in the middle of the desired data bit.
        if not self.reached_bit(self.cur_data_bit + 1):
            return []

        # Save the sample number where the data byte starts.
        if self.startsample == -1:
            self.startsample = self.samplenum

        # Get the next data bit in LSB-first or MSB-first fashion.
        if self.bit_order == LSB_FIRST:
            self.databyte >>= 1
            self.databyte |= (signal << (self.num_data_bits - 1))
        elif self.bit_order == MSB_FIRST:
            self.databyte <<= 1
            self.databyte |= (signal << 0)
        else:
            raise Exception('Invalid bit order value: %d', self.bit_order)

        # Return here, unless we already received all data bits.
        if self.cur_data_bit < self.num_data_bits - 1: # TODO? Off-by-one?
            self.cur_data_bit += 1
            return []

        # Convert the data byte into the configured format.
        if self.data_format == DATA_FORMAT_ASCII:
            d = chr(self.databyte)
        elif self.data_format == DATA_FORMAT_HEX:
            d = '0x%02x' % self.databyte
        else:
            raise Exception('Invalid data format value: %d', self.data_format)

        self.staterx = GET_PARITY_BIT

        if quick_hack: # TODO
            return [d]

        o = [{'type': 'D', 'range': (self.startsample, self.samplenum - 1),
             'data': d, 'ann': None}]

        return o

    def get_parity_bit(self, signal):
        # If no parity is used/configured, skip to the next state immediately.
        if self.parity == PARITY_NONE:
            self.staterx = GET_STOP_BITS
            return []

        # Skip samples until we're in the middle of the parity bit.
        if not self.reached_bit(self.num_data_bits + 1):
            return []

        self.paritybit = signal

        self.staterx = GET_STOP_BITS

        if parity_ok(self.parity, self.paritybit, self.databyte,
                     self.num_data_bits):
            if quick_hack: # TODO
                # return ['P']
                return []
            # TODO: Fix range.
            o = [{'type': 'P', 'range': (self.samplenum, self.samplenum),
                 'data': self.paritybit, 'ann': 'Parity bit'}]
        else:
            if quick_hack: # TODO
                return ['PE']
            o = [{'type': 'PE', 'range': (self.samplenum, self.samplenum),
                 'data': self.paritybit, 'ann': 'Parity error'}]

        return o

    # TODO: Currently only supports 1 stop bit.
    def get_stop_bits(self, signal):
        # Skip samples until we're in the middle of the stop bit(s).
        skip_parity = 0
        if self.parity != PARITY_NONE:
            skip_parity = 1
        if not self.reached_bit(self.num_data_bits + 1 + skip_parity):
            return []

        self.stopbit1 = signal

        if self.stopbit1 != 1:
            # TODO: Stop bits must be 1. If not, we report an error.
            pass

        self.staterx = WAIT_FOR_START_BIT

        if quick_hack: # TODO
            return []

        # TODO: Fix range.
        o = [{'type': 'P', 'range': (self.samplenum, self.samplenum),
             'data': None, 'ann': 'Stop bit'}]
        return o

    def decode(self, data):
        """UART protocol decoder"""

        out = []

        for sample in sampleiter(data["data"], self.unitsize):

            # TODO: Eliminate the need for ord().
            s = ord(sample.data)

            # TODO: Start counting at 0 or 1? Increase before or after?
            self.samplenum += 1

            # First sample: Save RX/TX value.
            if self.oldrx == None:
                # Get RX/TX bit values (0/1 for low/high) of the first sample.
                self.oldrx = (s & (1 << self.rx_bit)) >> self.rx_bit
                # self.oldtx = (s & (1 << self.tx_bit)) >> self.tx_bit
                continue

            # Get RX/TX bit values (0/1 for low/high).
            rx = (s & (1 << self.rx_bit)) >> self.rx_bit
            # tx = (s & (1 << self.tx_bit)) >> self.tx_bit

            # State machine.
            if self.staterx == WAIT_FOR_START_BIT:
                self.wait_for_start_bit(self.oldrx, rx)
            elif self.staterx == GET_START_BIT:
                out += self.get_start_bit(rx)
            elif self.staterx == GET_DATA_BITS:
                out += self.get_data_bits(rx)
            elif self.staterx == GET_PARITY_BIT:
                out += self.get_parity_bit(rx)
            elif self.staterx == GET_STOP_BITS:
                out += self.get_stop_bits(rx)
            else:
                raise Exception('Invalid state: %s' % self.staterx)

            # Save current RX/TX values for the next round.
            self.oldrx = rx
            # self.oldtx = tx

        if out != []:
            self.put(out)

