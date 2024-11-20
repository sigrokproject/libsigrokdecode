##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2011-2014 Uwe Hermann <uwe@hermann-uwe.de>
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

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <rxtx>, <pdata>]

This is the list of <ptype>s and their respective <pdata> values:
 - 'STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'DATA': This is always a tuple containing two items:
   - 1st item: the (integer) value of the UART data. Valid values
     range from 0 to 511 (as the data can be up to 9 bits in size).
   - 2nd item: the list of individual data bits and their ss/es numbers.
 - 'PARITYBIT': The data is the (integer) value of the parity bit (0/1).
 - 'STOPBIT': The data is the (integer) value of the stop bit (0 or 1).
 - 'INVALID STARTBIT': The data is the (integer) value of the start bit (0/1).
 - 'INVALID STOPBIT': The data is the (integer) value of the stop bit (0/1).
 - 'PARITY ERROR': The data is a tuple with two entries. The first one is
   the expected parity value, the second is the actual parity value.
 - 'BREAK': The data is always 0.
 - 'FRAME': The data is always a tuple containing two items: The (integer)
   value of the UART data, and a boolean which reflects the validity of the
   UART frame.
 - 'PACKET': The data is always a tuple containing two items: The list of
   (integer) values of the UART data packet, and a boolean which reflects
   the validity of the UART frames in the data packet.
 - 'IDLE': The data is always 0.

The <rxtx> field is 0 for RX packets, 1 for TX packets.
'''

# Used for differentiating between the two data directions.
RX = 0
TX = 1

# Used for protocols stackable with the uart and which require
# several uniform idle periods, such as lin PD
IDLE_NUM_WITHOUT_GROWTH = 2

# Given a parity type to check (odd, even, zero, one), the value of the
# parity bit, the value of the data, and the length of the data (5-9 bits,
# usually 8 bits) return True if the parity is correct, False otherwise.
# 'none' is _not_ allowed as value for 'parity_type'.
def parity_ok(parity_type, parity_bit, data, data_bits):

    if parity_type == 'ignore':
        return True

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

class SamplerateError(Exception):
    pass

class BaudrateError(Exception):
    pass

class ChannelError(Exception):
    pass

class Ann:
    RX_DATA, TX_DATA, RX_START, TX_START, RX_PARITY_OK, TX_PARITY_OK, \
    RX_PARITY_ERR, TX_PARITY_ERR, RX_STOP, TX_STOP, RX_WARN, TX_WARN, \
    RX_DATA_BIT, TX_DATA_BIT, RX_BREAK, TX_BREAK, RX_PACKET, TX_PACKET, \
    RX_SAMPLES, TX_SAMPLES, \
        = range(20)

class Bin:
    RX, TX, RXTX = range(3)

class State:
    WAIT_FOR_START_BIT, \
    GET_START_BIT, \
    GET_DATA_BITS, \
    GET_PARITY_BIT, \
    GET_STOP_BITS, \
        = range(5)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'uart'
    name = 'UART'
    longname = 'Universal Asynchronous Receiver/Transmitter'
    desc = 'Asynchronous, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['uart']
    tags = ['Embedded/industrial']
    optional_channels = (
        # Allow specifying only one of the signals, e.g. if only one data
        # direction exists (or is relevant).
        {'id': 'rx', 'name': 'RX', 'desc': 'UART receive line'},
        {'id': 'tx', 'name': 'TX', 'desc': 'UART transmit line'},
    )
    options = (
        {'id': 'baudrate', 'desc': 'Baud rate', 'default': 115200},
        {'id': 'data_bits', 'desc': 'Data bits', 'default': 8,
            'values': (5, 6, 7, 8, 9)},
        {'id': 'parity', 'desc': 'Parity', 'default': 'none',
            'values': ('none', 'odd', 'even', 'zero', 'one', 'ignore')},
        {'id': 'stop_bits', 'desc': 'Stop bits', 'default': 1.0,
            'values': (0.0, 0.5, 1.0, 1.5, 2.0)},
        {'id': 'bit_order', 'desc': 'Bit order', 'default': 'lsb-first',
            'values': ('lsb-first', 'msb-first')},
        {'id': 'format', 'desc': 'Data format', 'default': 'hex',
            'values': ('ascii', 'dec', 'hex', 'oct', 'bin')},
        {'id': 'invert_rx', 'desc': 'Invert RX', 'default': 'no',
            'values': ('yes', 'no')},
        {'id': 'invert_tx', 'desc': 'Invert TX', 'default': 'no',
            'values': ('yes', 'no')},
        {'id': 'put_sample_points', 'desc': 'Put sample points', 'default': 'no',
            'values': ('yes', 'no')},
        {'id': 'sample_point', 'desc': 'Sample point (%)', 'default': 50},
        {'id': 'packet_idle_us', 'desc': 'Packet delimit by idle time, us', 'default': -1},
        {'id': 'rx_packet_delim', 'desc': 'RX packet delimiter (decimal)',
            'default': -1},
        {'id': 'tx_packet_delim', 'desc': 'TX packet delimiter (decimal)',
            'default': -1},
        {'id': 'rx_packet_len', 'desc': 'RX packet length', 'default': -1},
        {'id': 'tx_packet_len', 'desc': 'TX packet length', 'default': -1},
    )
    annotations = (
        ('rx-data', 'RX data'),
        ('tx-data', 'TX data'),
        ('rx-start', 'RX start bit'),
        ('tx-start', 'TX start bit'),
        ('rx-parity-ok', 'RX parity OK bit'),
        ('tx-parity-ok', 'TX parity OK bit'),
        ('rx-parity-err', 'RX parity error bit'),
        ('tx-parity-err', 'TX parity error bit'),
        ('rx-stop', 'RX stop bit'),
        ('tx-stop', 'TX stop bit'),
        ('rx-warning', 'RX warning'),
        ('tx-warning', 'TX warning'),
        ('rx-data-bit', 'RX data bit'),
        ('tx-data-bit', 'TX data bit'),
        ('rx-break', 'RX break'),
        ('tx-break', 'TX break'),
        ('rx-packet', 'RX packet'),
        ('tx-packet', 'TX packet'),
        ('rx-samples', 'RX samples'),
        ('tx-samples', 'TX samples'),
    )
    annotation_rows = (
        ('rx-data-bits', 'RX bits', (Ann.RX_DATA_BIT,)),
        ('rx-samples', 'RX samples', (Ann.RX_SAMPLES,)),
        ('rx-data-vals', 'RX data', (Ann.RX_DATA, Ann.RX_START, Ann.RX_PARITY_OK, Ann.RX_PARITY_ERR, Ann.RX_STOP)),
        ('rx-warnings', 'RX warnings', (Ann.RX_WARN,)),
        ('rx-breaks', 'RX breaks', (Ann.RX_BREAK,)),
        ('rx-packets', 'RX packets', (Ann.RX_PACKET,)),
        ('tx-data-bits', 'TX bits', (Ann.TX_DATA_BIT,)),
        ('tx-samples', 'TX samples', (Ann.TX_SAMPLES,)),
        ('tx-data-vals', 'TX data', (Ann.TX_DATA, Ann.TX_START, Ann.TX_PARITY_OK, Ann.TX_PARITY_ERR, Ann.TX_STOP)),
        ('tx-warnings', 'TX warnings', (Ann.TX_WARN,)),
        ('tx-breaks', 'TX breaks', (Ann.TX_BREAK,)),
        ('tx-packets', 'TX packets', (Ann.TX_PACKET,)),
    )
    binary = (
        ('rx', 'RX dump'),
        ('tx', 'TX dump'),
        ('rxtx', 'RX/TX dump'),
    )
    idle_state = [State.WAIT_FOR_START_BIT, State.WAIT_FOR_START_BIT]

    def putgse(self, ss, es, data):
        self.put(ss, es, self.out_ann, data)

    def putpse(self, ss, es, data):
        self.put(ss, es, self.out_python, data)

    def putbinse(self, ss, es, data):
        self.put(ss, es, self.out_binary, data)

    def __init__(self):
        self.reset()

    def reset(self):
        self.idle_num = [0, 0]
        self.state_num = [0, 0]
        self.state = [State.WAIT_FOR_START_BIT, State.WAIT_FOR_START_BIT]
        self.data_bounds = [0, 0]
        self.samplerate = None
        self.frame_start = [-1, -1]
        self.frame_valid = [True, True]
        self.packet_valid = [True, True]
        self.datavalue = [0, 0]
        self.paritybit = [-1, -1]
        self.stopbits = [[], []]
        self.databits = [[], []]
        self.break_start = [None, None]
        self.packet_data = [[], []]
        self.ss_packet, self.es_packet = [None, None], [None, None]
        self.idle_start = [None, None]

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.stop_bits = float(self.options['stop_bits'])
        self.msb_first = self.options['bit_order'] == 'msb-first'
        self.put_sample_points = self.options['put_sample_points'] == 'yes'
        self.data_bits = self.options['data_bits']
        self.parity_type = self.options['parity']
        self.bw = (self.data_bits + 7) // 8
        self.delim = self.options['rx_packet_delim'], self.options['tx_packet_delim']
        self.plen = self.options['rx_packet_len'], self.options['tx_packet_len']
        self.check_settings_required()
        self.init_format()
        self.init_packet_idle()
        self.init_state_machine()

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            # The width of one UART bit in number of samples.
            self.baudrate = float(self.options['baudrate'])
            self.bit_width = float(self.samplerate) / self.baudrate
            self.half_bit_width = self.bit_width * 0.5

            # Accept a position in the range of 1-99% of the full bit width.
            # Assume 50% for invalid input specs for backwards compatibility.
            perc = self.options['sample_point'] or 50
            if not perc or not 1 <= perc <= 99:
                perc = 50
            self.bit_samplenum = self.bit_width * perc * 0.01

    def get_sample_point(self, rxtx):
        # Determine absolute sample number of a bit slot's sample point.
        # Counts for UART bits start from 0 (0 = start bit, 1..x = data,
        # x+1 = parity bit (if used) or the first stop bit, and so on).
        state_num = self.state_num[rxtx]
        _, samplenum, _ = self.state_machine[state_num][1]
        return self.frame_start[rxtx] + samplenum

    def wait_for_start_bit(self, rxtx, signal):
        # Save the sample number where the start bit begins.
        self.frame_start[rxtx] = self.samplenum
        self.frame_valid[rxtx] = True

        self.advance_state_machine(rxtx, signal)

    def frame_bit_bounds(self, rxtx):
        start = self.frame_start[rxtx]
        state_num = self.state_num[rxtx]
        # Relative start and end samples of the current bit
        rel_ss, _, rel_es = self.state_machine[state_num][1]
        return start + rel_ss, start + rel_es

    def reset_data_receive(self, rxtx):
        # Reset internal state for the pending UART frame.
        self.databits[rxtx].clear()
        self.datavalue[rxtx] = 0
        self.paritybit[rxtx] = -1
        self.stopbits[rxtx].clear()

    def get_start_bit(self, rxtx, signal):
        startbit = signal
        frame_ss, frame_es = self.frame_bit_bounds(rxtx)

        # The startbit must be 0. If not, we report an error and wait
        # for the next start bit (assuming this one was spurious).
        if startbit != 0:
            frame_es = self.samplenum
            self.putpse(frame_ss, frame_es, ['INVALID STARTBIT', rxtx, startbit])
            self.putgse(frame_ss, frame_es, [Ann.RX_WARN + rxtx, ['Frame error', 'Frame err', 'FE']])
            self.frame_valid[rxtx] = False
            self.handle_frame(rxtx, frame_ss, frame_es)
            self.advance_state_machine(rxtx, signal, startbit_error=True)
            return

        self.putpse(frame_ss, frame_es, ['STARTBIT', rxtx, startbit])
        self.putgse(frame_ss, frame_es, [Ann.RX_START + rxtx, ['Start bit', 'Start', 'S']])

        self.advance_state_machine(rxtx, signal)
        self.reset_data_receive(rxtx)

    def handle_packet_idle(self, rxtx, idle_end_sample):
        if not self.packet_data[rxtx] or self.packet_idle_samples is None:
            return
        if idle_end_sample >= self.es_packet[rxtx] + self.packet_idle_samples:
            self.handle_packet(rxtx)

    def handle_packet(self, rxtx):
        str_list = [self.format_value(b) for b in self.packet_data[rxtx]]
        if self.fmt is None:
            s = ''.join(str_list)
        else:
            s = ' '.join(str_list)
        ss, es = self.ss_packet[rxtx], self.es_packet[rxtx]
        self.putgse(ss, es, [Ann.RX_PACKET + rxtx, [s]])
        self.putpse(ss, es, ['PACKET', rxtx, (self.packet_data[rxtx], self.packet_valid[rxtx])])
        self.packet_data[rxtx].clear()

    def get_packet_data(self, rxtx, frame_end_sample):
        if self.delim[rxtx] < 0 and self.plen[rxtx] < 0 and self.packet_idle_samples is None:
            return
        # Cache data values until we see the delimiter and/or the specified
        # packet length has been reached (whichever happens first).
        if len(self.packet_data[rxtx]) == 0:
            self.ss_packet[rxtx] = self.frame_start[rxtx]
            self.packet_valid[rxtx] = self.frame_valid[rxtx]
        else:
            if not self.frame_valid[rxtx]:
                self.packet_valid[rxtx] = False
        self.packet_data[rxtx].append(self.datavalue[rxtx])
        self.es_packet[rxtx] = frame_end_sample
        if self.datavalue[rxtx] == self.delim[rxtx] or len(self.packet_data[rxtx]) == self.plen[rxtx]:
            self.handle_packet(rxtx)

    def frame_data_bounds(self, rxtx):
        start = self.frame_start[rxtx]
        # Relative start and end samples of the data bits
        rel_ss, rel_es = self.data_bounds
        return start + rel_ss, start + rel_es

    def get_data_bits(self, rxtx, signal):
        # Store individual data bits and their start/end samplenumbers.
        ss, es = self.frame_bit_bounds(rxtx)
        self.putgse(ss, es, [Ann.RX_DATA_BIT + rxtx, ['%d' % signal]])

        self.databits[rxtx].append([signal, ss, es])
        if len(self.databits[rxtx]) == self.data_bits:
            self.handle_data(rxtx)

        self.advance_state_machine(rxtx, signal)

    def handle_data(self, rxtx):
        # Convert accumulated data bits to a data value.
        bits = [b[0] for b in self.databits[rxtx]]
        if self.msb_first:
            bits.reverse()
        b = bitpack(bits)
        self.datavalue[rxtx] = b

        ss_data, es_data = self.frame_data_bounds(rxtx)
        self.putpse(ss_data, es_data, ['DATA', rxtx, (self.datavalue[rxtx], self.databits[rxtx])])
        self.putgse(ss_data, es_data, [rxtx, [self.format_value(b)]])

        bdata = b.to_bytes(self.bw, byteorder='big')
        self.putbinse(ss_data, es_data, [Bin.RX + rxtx, bdata])
        self.putbinse(ss_data, es_data, [Bin.RXTX, bdata])
        self.databits[rxtx].clear()

    def get_bit_bounds(self, bit_num, half_bit=False):
        ss = bit_num * self.bit_width
        if not half_bit:
            return (
                round(ss),
                round(ss + self.bit_samplenum),
                round(ss + self.bit_width),
            )
        else:
            return (
                round(ss),
                round(ss + self.bit_samplenum * 0.5),
                round(ss + self.bit_width * 0.5),
            )

    def init_state_machine(self):
        # State machine here is a list with elements containing precomputed values for each decoder step.
        # One step of state machine is a tuple((state, tuple(ss, samplenum, es))), where:
        # - state equals one of values of the class State (GET_DATA_BITS, GET_PARITY_BIT, etc)
        # - ss - relative position in frame of the start of a step,
        # - samplenum - relative position in frame where signal value is read,
        # - es - relative position in frame of the end of step.
        # Frame starts when signal went LOW logical state. This position is stored in self.frame_start
        # Thus, absolute samplenum can be calculated by simple addition:
        # step_ss = self.frame_start[rxtx] + sm_step[1][0]
        # step_samplenum = self.frame_start[rxtx] + sm_step[1][1]
        # step_es = self.frame_start[rxtx] + sm_step[1][2]
        sm = list()

        # Get START bit
        sm.append((State.WAIT_FOR_START_BIT, (0, 0, 0)))
        sm.append((State.GET_START_BIT, self.get_bit_bounds(0)))

        # Get DATA bits
        self.data_bounds[0] = sm[-1][1][2]  # end of start bit and start of first data bit
        for data_bit_num in range(self.data_bits):
            sm.append((State.GET_DATA_BITS, self.get_bit_bounds(data_bit_num+1)))
        self.data_bounds[1] = sm[-1][1][2]  # end of last data bit

        # Get PARITY bit
        frame_bit_num = 1 + self.data_bits
        if self.parity_type != 'none':
            sm.append((State.GET_PARITY_BIT, self.get_bit_bounds(frame_bit_num)))
            frame_bit_num += 1

        # Get STOP bit(s)
        stop_bits = self.stop_bits
        while stop_bits > 0.4:  # we can't check float equality with exact values due to rounding
            if stop_bits > 0.9:
                sm.append((State.GET_STOP_BITS, self.get_bit_bounds(frame_bit_num)))
                stop_bits -= 1
                frame_bit_num += 1
            elif stop_bits > 0.4:
                sm.append((State.GET_STOP_BITS, self.get_bit_bounds(frame_bit_num, half_bit=True)))
                stop_bits = 0

        # Looping state machine to simplify advance_state_machine function
        sm.append(sm[0])
        self.state_machine = sm

        # Init state machine
        for rxtx in (RX, TX):
            self.state[rxtx] = State.WAIT_FOR_START_BIT
            self.state_num[rxtx] = 0

    def init_packet_idle(self):
        packet_idle_us = self.options['packet_idle_us']
        if packet_idle_us > 0:
            self.packet_idle_samples = int(round(packet_idle_us * 1e-6 * self.samplerate))
            self.packet_idle_samples = max(1, self.packet_idle_samples)
        else:
            self.packet_idle_samples = None

    def init_format(self):
        # Init format according to configured options.
        # Reflects the user selected kind of representation, as well as
        # the number of data bits in the UART frames.

        fmt = self.options['format']
        self.hexfmt = "[{:02X}]" if self.data_bits <= 8 else "[{:03X}]"
        self.fmt = None

        if fmt == 'ascii':
            return

        # Mere number to text conversion without prefix and padding
        # for the "decimal" output format.
        if fmt == 'dec':
            self.fmt = "{:d}"
        else:
            # Padding with leading zeroes for hex/oct/bin formats, but
            # without a prefix for density -- since the format is user
            # specified, there is no ambiguity.
            if fmt == 'hex':
                digits = (self.data_bits + 4 - 1) // 4
                fmtchar = "X"
            elif fmt == 'oct':
                digits = (self.data_bits + 3 - 1) // 3
                fmtchar = "o"
            elif fmt == 'bin':
                digits = self.data_bits
                fmtchar = "b"
            else:
                fmtchar = None

            if fmtchar is not None:
                self.fmt = "{{:0{:d}{:s}}}".format(digits, fmtchar)

    def format_value(self, v):
        # Format value 'v' according to configured options.

        # Assume "is printable" for values from 32 to including 126,
        # below 32 is "control" and thus not printable, above 127 is
        # "not ASCII" in its strict sense, 127 (DEL) is not printable,
        # fall back to hex representation for non-printables.
        if self.fmt is None:
            if 32 <= v <= 126:
                return chr(v)
            return self.hexfmt.format(v)
        else:
            return self.fmt.format(v)

    def get_parity_bit(self, rxtx, signal):
        self.paritybit[rxtx] = signal
        ss, es = self.frame_bit_bounds(rxtx)
        if parity_ok(self.parity_type, self.paritybit[rxtx],
                     self.datavalue[rxtx], self.data_bits):
            self.putpse(ss, es, ['PARITYBIT', rxtx, self.paritybit[rxtx]])
            self.putgse(ss, es, [Ann.RX_PARITY_OK + rxtx, ['Parity bit', 'Parity', 'P']])
        else:
            # Return expected/actual parity values.
            self.putpse(ss, es, ['PARITY ERROR', rxtx, ((not signal)*1, signal*1)])
            self.putgse(ss, es, [Ann.RX_PARITY_ERR + rxtx, ['Parity error', 'Parity err', 'PE']])
            self.frame_valid[rxtx] = False
            report_error = True

        self.advance_state_machine(rxtx, signal)

    def get_stop_bits(self, rxtx, signal):
        self.stopbits[rxtx].append(signal)
        ss, es = self.frame_bit_bounds(rxtx)

        # Stop bits must be 1. If not, we report an error.
        stopbit_error = signal != 1
        if stopbit_error:
            es = self.samplenum
            self.putpse(ss, es, ['INVALID STOPBIT', rxtx, signal])
            self.putgse(ss, es, [Ann.RX_WARN + rxtx, ['Frame error', 'Frame err', 'FE']])
            self.putgse(ss, es, [Ann.RX_STOP + rxtx, ['Stop bit error', 'Stop err', 'TE']])
            self.frame_valid[rxtx] = False
        else:
            self.putpse(ss, es, ['STOPBIT', rxtx, signal])
            self.putgse(ss, es, [Ann.RX_STOP + rxtx, ['Stop bit', 'Stop', 'T']])

        self.advance_state_machine(rxtx, signal, stopbit_error=stopbit_error)

    def advance_state_machine(self, rxtx, signal, startbit_error=False, stopbit_error=False):
        # Advances the protocol decoder's internal state for all regular
        # UART frame inspection. Deals with either edges, sample points,
        # or other .wait() conditions. Also gracefully handles extreme
        # undersampling. Each turn takes one .wait() call which in turn
        # corresponds to at least one sample. That is why as many state
        # transitions are done here as required within a single call.

        if startbit_error or stopbit_error:
            # When requested by the caller, don't advance to the next
            # UART frame's field, but to the start of the next START bit
            # instead.
            self.state_num[rxtx] = 0
            self.state[rxtx] = State.WAIT_FOR_START_BIT

            if startbit_error:
                # When requested by the caller, start another (potential)
                # IDLE period after the caller specified position.
                self.idle_start[rxtx] = self.samplenum
                return

        else:
            # Advance to the next UART frame's field that we expect. Cope
            # with absence of optional fields. Force scan for next IDLE
            # after the (optional) STOP bit field, so that callers need
            # not deal with optional field presence. Also handles the cases
            # where the decoder navigates to edges which are not strictly
            # a field's sampling point.
            self.state_num[rxtx] += 1
            self.state[rxtx] = self.state_machine[self.state_num[rxtx]][0]

        if self.state[rxtx] == State.WAIT_FOR_START_BIT:
            self.state_num[rxtx] = 0
            # Postprocess the previously received UART frame. Advance
            # the read position to after the frame's last bit time. So
            # that the start of the next START bit won't fall into the
            # end of the previously received UART frame. This improves
            # robustness in the presence of glitchy input data.
            frame_ss = self.frame_start[rxtx]
            if not stopbit_error:
                frame_es = frame_ss + self.frame_len_sample_count
                self.idle_start[rxtx] = frame_es
            else:
                frame_es = self.samplenum
                self.idle_start[rxtx] = None
            self.handle_frame(rxtx, frame_ss, frame_es)
            self.get_packet_data(rxtx, frame_es)

    def handle_frame(self, rxtx, ss, es):
        # Pass the complete UART frame to upper layers.
        self.putpse(ss, es, ['FRAME', rxtx,
            (self.datavalue[rxtx], self.frame_valid[rxtx])])

    def handle_idle(self, rxtx, ss, es):
        self.putpse(ss, es, ['IDLE', rxtx, 0])
        self.idle_num[rxtx] += 1

    def handle_break(self, rxtx, ss, es):
        self.putpse(ss, es, ['BREAK', rxtx, 0])
        self.putgse(ss, es, [Ann.RX_BREAK + rxtx,
                ['Break condition', 'Break', 'Brk', 'B']])

    def get_wait_cond(self, rxtx, inv):
        # Return condititions that are suitable for Decoder.wait(). Those
        # conditions either match the falling edge of the START bit, or
        # the sample point of the next bit time.
        if self.state[rxtx] == State.WAIT_FOR_START_BIT:
            return {rxtx: 'r' if inv else 'f'}
        else:
            want_samplenum = self.get_sample_point(rxtx)
            return {'skip': want_samplenum - self.samplenum}

    def get_idle_cond(self, rxtx, inv):
        # Return a condition that corresponds to the (expected) end of
        # the next frame, assuming that it will be an "idle frame"
        # (constant high input level for the frame's length).
        if self.idle_start[rxtx] is None:
            return None
        if self.idle_num[rxtx] < IDLE_NUM_WITHOUT_GROWTH:
            idle_wait_samples = self.frame_len_sample_count
        elif self.idle_num[rxtx] >= self.idle_num_max:
            idle_wait_samples = self.samplerate
        else:
            double_num = self.idle_num[rxtx] - (IDLE_NUM_WITHOUT_GROWTH-1)
            idle_wait_samples = self.frame_len_sample_count * (1 << double_num)

        end_of_wait_sample = self.idle_start[rxtx] + idle_wait_samples
        if end_of_wait_sample <= self.samplenum:
            return None
        return {'skip': end_of_wait_sample - self.samplenum}

    def inspect_sample(self, rxtx, signal, inv):
        # Inspect a sample returned by .wait() for the specified UART line.
        if inv:
            signal = not signal
        state = self.state[rxtx]
        if state == State.WAIT_FOR_START_BIT:
            self.handle_packet_idle(rxtx, self.samplenum)
            self.wait_for_start_bit(rxtx, signal)
        else:
            if state == State.GET_START_BIT:
                self.get_start_bit(rxtx, signal)
            elif state == State.GET_DATA_BITS:
                self.get_data_bits(rxtx, signal)
            elif state == State.GET_PARITY_BIT:
                self.get_parity_bit(rxtx, signal)
            elif state == State.GET_STOP_BITS:
                self.get_stop_bits(rxtx, signal)
            if self.put_sample_points:
                self.putgse(self.samplenum, self.samplenum, [Ann.RX_SAMPLES + rxtx, [str(signal)]])

    def inspect_edge(self, rxtx, signal, inv):
        # Inspect edges, independently of traffic, to detect break conditions.
        if inv:
            signal = not signal
        if not signal:
            # Signal went low. Start another interval.
            self.break_start[rxtx] = self.samplenum
            return
        # Signal went high. Was there an extended period with low signal?
        if self.break_start[rxtx] is None:
            return
        diff = self.samplenum - self.break_start[rxtx]
        if diff >= self.break_min_sample_count:
            ss, es = self.frame_start[rxtx], self.samplenum
            self.handle_break(rxtx, ss, es)
        self.break_start[rxtx] = None

    def inspect_idle(self, rxtx, signal, inv):
        # Check each edge and each period of stable input (either level).
        # Can derive the "idle frame period has passed" condition.
        if inv:
            signal = not signal
        if not signal:
            # Low input, cease inspection.
            self.idle_start[rxtx] = None
            self.idle_num[rxtx] = 0
            return
        # High input, either just reached, or still stable.
        if self.idle_start[rxtx] is None:
            self.idle_start[rxtx] = self.samplenum
        diff = self.samplenum - self.idle_start[rxtx]
        if diff < self.frame_len_sample_count:
            return
        ss, es = self.idle_start[rxtx], self.samplenum
        self.handle_idle(rxtx, ss, es)
        self.handle_packet_idle(rxtx, es)
        self.idle_start[rxtx] = es

    def check_settings_required(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        if not self.baudrate or self.baudrate < 0:
            raise BaudrateError('Cannot decode without baudrate > 0.')

    def decode(self):
        self.check_settings_required()

        has_pin = [self.has_channel(ch) for ch in (RX, TX)]
        if not True in has_pin:
            raise ChannelError('Need at least one of TX or RX pins.')

        inv = (self.options['invert_rx'] == 'yes', self.options['invert_tx'] == 'yes')
        cond_data_idx = [None] * len(has_pin)

        # Determine the number of samples for a complete frame's time span.
        # A period of low signal (at least) that long is a break condition.
        frame_samples = 1 # START
        frame_samples += self.data_bits
        frame_samples += 0 if self.parity_type == 'none' else 1
        frame_samples += self.stop_bits
        frame_samples *= self.bit_width
        self.frame_len_sample_count = round(frame_samples)
        self.idle_num_max = 0
        while self.frame_len_sample_count * (1 << self.idle_num_max) < self.samplerate:
            self.idle_num_max += 1
        self.idle_num_max += IDLE_NUM_WITHOUT_GROWTH-1
        self.break_min_sample_count = self.frame_len_sample_count + 1
        cond_edge_idx = [None] * len(has_pin)
        cond_idle_idx = [None] * len(has_pin)

        conds = list()
        while True:
            conds.clear()
            for rxtx in (RX, TX):
                if has_pin[rxtx]:
                    cond_data_idx[rxtx] = len(conds)
                    conds.append(self.get_wait_cond(rxtx, inv[rxtx]))
                    cond_edge_idx[rxtx] = len(conds)
                    conds.append({rxtx: 'e'})
                    idle_cond = self.get_idle_cond(rxtx, inv[rxtx])
                    if idle_cond:
                        cond_idle_idx[rxtx] = len(conds)
                        conds.append(idle_cond)
                    else:
                        cond_idle_idx[rxtx] = None

            signal = self.wait(conds)

            for rxtx in (RX, TX):
                if has_pin[rxtx]:
                    if cond_data_idx[rxtx] is not None and self.matched[cond_data_idx[rxtx]]:
                        self.inspect_sample(rxtx, signal[rxtx], inv[rxtx])
                    if cond_edge_idx[rxtx] is not None and self.matched[cond_edge_idx[rxtx]]:
                        self.inspect_edge(rxtx, signal[rxtx], inv[rxtx])
                        self.inspect_idle(rxtx, signal[rxtx], inv[rxtx])
                    if cond_idle_idx[rxtx] is not None and self.matched[cond_idle_idx[rxtx]]:
                        self.inspect_idle(rxtx, signal[rxtx], inv[rxtx])
