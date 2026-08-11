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

"""
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
 - 'IDLE': The data is always 0.

The <rxtx> field is 0 for RX packets, 1 for TX packets.
"""

import sigrokdecode as srd
from math import floor, ceil

# Used for differentiating between the two data directions.
RX = 0
TX = 1

def parity_ok(parity_type, parity_bit, data, data_bits):
    """
    Brief: Checks if the received parity bit matches the expected parity condition.
    Params:
        parity_type (str): Parity type ('none', 'odd', 'even', 'zero', 'one', 'ignore').
        parity_bit (int): Value of the received parity bit (0 or 1).
        data (int): Value of the UART payload data (5-9 bits).
        data_bits (int): Number of payload bits in the UART frame.
    Invariants: 'none' must not be passed to parity_ok.
    Output:
        bool: True if parity matches criteria or is ignored, False otherwise.
    """
    if parity_type == 'ignore':
        return True

    # Handle easy cases first (parity bit is always 1 or 0).
    if parity_type == 'zero':
        return parity_bit == 0
    elif parity_type == 'one':
        return parity_bit == 1

    # Count set bits in C without Python string allocations when available
    try:
        cnt = data.bit_count()
    except AttributeError:
        cnt = bin(data).count('1')
    ones = cnt + parity_bit

    # Check for odd/even parity.
    if parity_type == 'odd':
        return (ones % 2) == 1
    elif parity_type == 'even':
        return (ones % 2) == 0

class SamplerateError(Exception):
    """Exception raised when logic capture samplerate is missing or invalid."""
    pass

class ChannelError(Exception):
    """Exception raised when neither RX nor TX logic channels are configured."""
    pass

class State:
    """Decoder state machine integer definitions for UART frame inspection."""
    WAIT_FOR_START_BIT = 0
    GET_START_BIT = 1
    GET_DATA_BITS = 2
    GET_PARITY_BIT = 3
    GET_STOP_BITS = 4

class Ann:
    """Annotation class enumerations for sigrokdecode output."""
    RX_DATA, TX_DATA, RX_START, TX_START, RX_PARITY_OK, TX_PARITY_OK, \
    RX_PARITY_ERR, TX_PARITY_ERR, RX_STOP, TX_STOP, RX_WARN, TX_WARN, \
    RX_DATA_BIT, TX_DATA_BIT, RX_BREAK, TX_BREAK, RX_PACKET, TX_PACKET = \
    range(18)

class Bin:
    """Binary dump output channel enumerations."""
    RX, TX, RXTX = range(3)

class Decoder(srd.Decoder):
    """
    Universal Asynchronous Receiver/Transmitter (UART) Protocol Decoder.

    Decodes full duplex or half duplex UART channels (RX, TX) supporting 5-9 data bits,
    various parity modes (none, odd, even, zero, one, ignore), fractional stop bits,
    bit inversion, custom sample points, and packet delineation.
    """
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
        {'id': 'sample_point', 'desc': 'Sample point (%)', 'default': 50},
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
    )
    annotation_rows = (
        ('rx-data-bits', 'RX bits', (Ann.RX_DATA_BIT,)),
        ('rx-data-vals', 'RX data', (Ann.RX_DATA, Ann.RX_START, Ann.RX_PARITY_OK, Ann.RX_PARITY_ERR, Ann.RX_STOP)),
        ('rx-warnings', 'RX warnings', (Ann.RX_WARN,)),
        ('rx-breaks', 'RX breaks', (Ann.RX_BREAK,)),
        ('rx-packets', 'RX packets', (Ann.RX_PACKET,)),
        ('tx-data-bits', 'TX bits', (Ann.TX_DATA_BIT,)),
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

    def putx(self, rxtx, data):
        """
        Brief: Emits graphical annotations centered on the current bit sample window.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            data (list): [annotation_class, text_list].
        Invariants: Emits to self.out_ann stream.
        Output: None
        """
        s, halfbit = self.startsample[rxtx], self.bit_width / 2.0
        self.put(s - floor(halfbit), self.samplenum + ceil(halfbit), self.out_ann, data)

    def putx_packet(self, rxtx, data):
        """
        Brief: Emits graphical packet annotations spanning from packet start to current sample.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            data (list): [annotation_class, text_list].
        Invariants: Emits to self.out_ann stream using self.ss_packet[rxtx].
        Output: None
        """
        s, halfbit = self.ss_packet[rxtx], self.bit_width / 2.0
        self.put(s - floor(halfbit), self.samplenum + ceil(halfbit), self.out_ann, data)

    def putpx(self, rxtx, data):
        """
        Brief: Emits Python output data structures spanning start sample to current sample.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            data (list): [packet_type, rxtx, payload].
        Invariants: Emits to self.out_python stream.
        Output: None
        """
        s, halfbit = self.startsample[rxtx], self.bit_width / 2.0
        self.put(s - floor(halfbit), self.samplenum + ceil(halfbit), self.out_python, data)

    def putg(self, data):
        """
        Brief: Emits graphical annotations for a single bit duration centered at current sample.
        Params:
            data (list): [annotation_class, text_list].
        Invariants: Emits to self.out_ann stream.
        Output: None
        """
        s, halfbit = self.samplenum, self.bit_width / 2.0
        self.put(s - floor(halfbit), s + ceil(halfbit), self.out_ann, data)

    def putp(self, data):
        """
        Brief: Emits Python output data for a single bit duration centered at current sample.
        Params:
            data (list): [packet_type, rxtx, payload].
        Invariants: Emits to self.out_python stream.
        Output: None
        """
        s, halfbit = self.samplenum, self.bit_width / 2.0
        self.put(s - floor(halfbit), s + ceil(halfbit), self.out_python, data)

    def putgse(self, ss, es, data):
        """
        Brief: Emits graphical annotations for an explicit sample range [ss, es].
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            data (list): [annotation_class, text_list].
        Invariants: ss <= es.
        Output: None
        """
        self.put(ss, es, self.out_ann, data)

    def putpse(self, ss, es, data):
        """
        Brief: Emits Python output data structures for an explicit sample range [ss, es].
        Params:
            ss (int): Start sample index.
            es (int): End sample index.
            data (list): [packet_type, rxtx, payload].
        Invariants: ss <= es.
        Output: None
        """
        self.put(ss, es, self.out_python, data)

    def putbin(self, rxtx, data):
        """
        Brief: Emits binary payload byte dump to binary output stream.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            data (list): [bin_channel, bytes_data].
        Invariants: Emits to self.out_binary stream.
        Output: None
        """
        s, halfbit = self.startsample[rxtx], self.bit_width / 2.0
        self.put(s - floor(halfbit), self.samplenum + ceil(halfbit), self.out_binary, data)

    def __init__(self):
        """
        Brief: Initializes the UART decoder instance and state variables.
        Params: None
        Invariants: Resets internal state buffers for RX and TX.
        Output: None
        """
        self.reset()

    def reset(self):
        """
        Brief: Resets state machine variables for both RX and TX channels.
        Params: None
        Invariants: Initializes state arrays for dual direction handling (RX = 0, TX = 1).
        Output: None
        """
        self.samplerate = None
        self.frame_start = [-1, -1]
        self.frame_valid = [None, None]
        self.cur_frame_bit = [None, None]
        self.startbit = [-1, -1]
        self.cur_data_bit = [0, 0]
        self.datavalue = [0, 0]
        self.paritybit = [-1, -1]
        self.stopbits = [[], []]
        self.startsample = [-1, -1]
        self.state = [State.WAIT_FOR_START_BIT, State.WAIT_FOR_START_BIT]
        self.databits = [[], []]
        self.break_start = [None, None]
        self.packet_cache = [[], []]
        self.ss_packet, self.es_packet = [None, None], [None, None]
        self.idle_start = [None, None]

    def start(self):
        """
        Brief: Registers output streams (Python, Binary, Annotations) with sigrokdecode.
        Params: None
        Invariants: Pre-calculates byte width bw from options['data_bits'].
        Output: None
        """
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.bw = (self.options['data_bits'] + 7) // 8

    def metadata(self, key, value):
        """
        Brief: Receives capture metadata updates such as logic samplerate.
        Params:
            key (int): Metadata configuration key (e.g. SRD_CONF_SAMPLERATE).
            value (int/float): Configured value.
        Invariants: Calculates bit_width in samples based on samplerate and baudrate.
        Output: None
        """
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            self.bit_width = float(self.samplerate) / float(self.options['baudrate'])

    def get_sample_point(self, rxtx, bitnum):
        """
        Brief: Calculates the absolute sample index for sampling a bit slot.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            bitnum (int): 0-based bit index in UART frame (0 = start, 1..x = data).
        Invariants: Uses configured sample_point percentage (default 50%).
        Output:
            float: Absolute sample index for sampling point.
        """
        perc = self.options['sample_point'] or 50
        if not perc or perc not in range(1, 100):
            perc = 50
        perc /= 100.0
        bitpos = (self.bit_width - 1) * perc
        bitpos += self.frame_start[rxtx]
        bitpos += bitnum * self.bit_width
        return bitpos

    def wait_for_start_bit(self, rxtx, signal):
        """
        Brief: Records start sample of falling edge for a candidate UART start bit.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Level of logic channel (0 or 1).
        Invariants: Sets frame_valid = True; advances state.
        Output: None
        """
        self.frame_start[rxtx] = self.samplenum
        self.frame_valid[rxtx] = True
        self.cur_frame_bit[rxtx] = 0
        self.advance_state(rxtx, signal)

    def get_start_bit(self, rxtx, signal):
        """
        Brief: Samples and validates the UART START bit (must be 0/LOW).
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Sampled logic signal value (0 or 1).
        Invariants: On invalid start bit (!= 0), emits error annotation and triggers fatal advance.
        Output: None
        """
        self.startbit[rxtx] = signal
        self.cur_frame_bit[rxtx] += 1

        if self.startbit[rxtx] != 0:
            self.putp(['INVALID STARTBIT', rxtx, self.startbit[rxtx]])
            self.putg([Ann.RX_WARN + rxtx, ['Frame error', 'Frame err', 'FE']])
            self.frame_valid[rxtx] = False
            es = self.samplenum + ceil(self.bit_width / 2.0)
            self.putpse(self.frame_start[rxtx], es, ['FRAME', rxtx,
                (self.datavalue[rxtx], self.frame_valid[rxtx])])
            self.advance_state(rxtx, signal, fatal = True, idle = es)
            return

        self.cur_data_bit[rxtx] = 0
        self.datavalue[rxtx] = 0
        self.paritybit[rxtx] = -1
        self.stopbits[rxtx].clear()
        self.startsample[rxtx] = -1
        self.databits[rxtx].clear()

        self.putp(['STARTBIT', rxtx, self.startbit[rxtx]])
        self.putg([Ann.RX_START + rxtx, ['Start bit', 'Start', 'S']])
        self.advance_state(rxtx, signal)

    def handle_packet(self, rxtx):
        """
        Brief: Groups UART bytes into packet annotations based on delimiter or length options.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
        Invariants: Uses packet_cache buffer; emits Ann.RX_PACKET/TX_PACKET upon delimiter or max length.
        Output: None
        """
        d = 'rx' if (rxtx == RX) else 'tx'
        delim = self.options[d + '_packet_delim']
        plen = self.options[d + '_packet_len']
        if delim == -1 and plen == -1:
            return

        if len(self.packet_cache[rxtx]) == 0:
            self.ss_packet[rxtx] = self.startsample[rxtx]
        self.packet_cache[rxtx].append(self.datavalue[rxtx])
        if self.datavalue[rxtx] == delim or len(self.packet_cache[rxtx]) == plen:
            self.es_packet[rxtx] = self.samplenum
            sep = '' if self.options['format'] == 'ascii' else ' '
            s = sep.join(self.format_value(b) for b in self.packet_cache[rxtx])
            self.putx_packet(rxtx, [Ann.RX_PACKET + rxtx, [s]])
            self.packet_cache[rxtx] = []

    def get_data_bits(self, rxtx, signal):
        """
        Brief: Samples individual UART data bits and converts accumulated bits to payload values via direct bitwise shifts.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Sampled bit value (0 or 1).
        Invariants: Shifts signal directly into datavalue; emits DATA and binary dumps on completion.
        Output: None
        """
        if self.startsample[rxtx] == -1:
            self.startsample[rxtx] = self.samplenum

        self.putg([Ann.RX_DATA_BIT + rxtx, ['%d' % signal]])

        s, halfbit = self.samplenum, self.bit_width / 2.0
        self.databits[rxtx].append([signal, s - floor(halfbit), s + ceil(halfbit)])

        if self.options['bit_order'] == 'msb-first':
            self.datavalue[rxtx] = (self.datavalue[rxtx] << 1) | signal
        else:
            self.datavalue[rxtx] |= (signal << self.cur_data_bit[rxtx])

        self.cur_frame_bit[rxtx] += 1
        self.cur_data_bit[rxtx] += 1

        if self.cur_data_bit[rxtx] < self.options['data_bits']:
            return

        b = self.datavalue[rxtx]
        self.putpx(rxtx, ['DATA', rxtx, (b, self.databits[rxtx])])

        formatted = self.format_value(b)
        if formatted is not None:
            self.putx(rxtx, [rxtx, [formatted]])

        bdata = b.to_bytes(self.bw, byteorder='big')
        self.putbin(rxtx, [Bin.RX + rxtx, bdata])
        self.putbin(rxtx, [Bin.RXTX, bdata])

        self.handle_packet(rxtx)
        self.databits[rxtx] = []
        self.advance_state(rxtx, signal)

    def format_value(self, v):
        """
        Brief: Formats a byte payload integer value into text based on user configuration.
        Params:
            v (int): Byte value to format.
        Invariants: Supports ascii, dec, hex, oct, bin formats.
        Output:
            str or None: Formatted string representation.
        """
        fmt, bits = self.options['format'], self.options['data_bits']

        if fmt == 'ascii':
            if v in range(32, 126 + 1):
                return chr(v)
            hexfmt = "[{:02X}]" if bits <= 8 else "[{:03X}]"
            return hexfmt.format(v)

        if fmt == 'dec':
            return "{:d}".format(v)

        if fmt == 'hex':
            digits = (bits + 4 - 1) // 4
            fmtchar = "X"
        elif fmt == 'oct':
            digits = (bits + 3 - 1) // 3
            fmtchar = "o"
        elif fmt == 'bin':
            digits = bits
            fmtchar = "b"
        else:
            fmtchar = None
        if fmtchar is not None:
            fmt = "{{:0{:d}{:s}}}".format(digits, fmtchar)
            return fmt.format(v)

        return None

    def get_parity_bit(self, rxtx, signal):
        """
        Brief: Samples and validates the UART parity bit.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Sampled parity bit value (0 or 1).
        Invariants: Marks frame_valid = False on parity error and emits PARITY ERROR annotation.
        Output: None
        """
        self.paritybit[rxtx] = signal
        self.cur_frame_bit[rxtx] += 1

        if parity_ok(self.options['parity'], self.paritybit[rxtx],
                     self.datavalue[rxtx], self.options['data_bits']):
            self.putp(['PARITYBIT', rxtx, self.paritybit[rxtx]])
            self.putg([Ann.RX_PARITY_OK + rxtx, ['Parity bit', 'Parity', 'P']])
        else:
            self.putp(['PARITY ERROR', rxtx, (0, 1)])
            self.putg([Ann.RX_PARITY_ERR + rxtx, ['Parity error', 'Parity err', 'PE']])
            self.frame_valid[rxtx] = False

        self.advance_state(rxtx, signal)

    def get_stop_bits(self, rxtx, signal):
        """
        Brief: Samples and validates UART STOP bits (must be 1/HIGH).
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Sampled stop bit value (0 or 1).
        Invariants: Marks frame_valid = False on invalid stop bit (!= 1).
        Output: None
        """
        self.stopbits[rxtx].append(signal)
        self.cur_frame_bit[rxtx] += 1

        if signal != 1:
            self.putp(['INVALID STOPBIT', rxtx, signal])
            self.putg([Ann.RX_WARN + rxtx, ['Frame error', 'Frame err', 'FE']])
            self.frame_valid[rxtx] = False

        self.putp(['STOPBIT', rxtx, signal])
        self.putg([Ann.RX_STOP + rxtx, ['Stop bit', 'Stop', 'T']])

        if len(self.stopbits[rxtx]) < self.options['stop_bits']:
            return
        self.advance_state(rxtx, signal)

    def advance_state(self, rxtx, signal = None, fatal = False, idle = None):
        """
        Brief: Advances internal state machine for UART frame field transitions.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int, optional): Logic signal value.
            fatal (bool): If True, forces immediate reset to WAIT_FOR_START_BIT.
            idle (int, optional): Sample index to mark start of IDLE period.
        Invariants: Emits FRAME python packet when advancing from GET_STOP_BITS.
        Output: None
        """
        frame_end = self.frame_start[rxtx] + self.frame_len_sample_count
        if idle is not None:
            self.idle_start[rxtx] = idle
        if fatal:
            self.state[rxtx] = State.WAIT_FOR_START_BIT
            return

        st = self.state[rxtx]
        if st == State.WAIT_FOR_START_BIT:
            self.state[rxtx] = State.GET_START_BIT
        elif st == State.GET_START_BIT:
            self.state[rxtx] = State.GET_DATA_BITS
        elif st == State.GET_DATA_BITS:
            self.state[rxtx] = State.GET_PARITY_BIT
            if self.options['parity'] != 'none':
                return
            self.state[rxtx] = State.GET_STOP_BITS
            if self.options['stop_bits']:
                return
            ss = self.frame_start[rxtx]
            es = self.samplenum + ceil(self.bit_width / 2.0)
            self.handle_frame(rxtx, ss, es)
            self.state[rxtx] = State.WAIT_FOR_START_BIT
            self.idle_start[rxtx] = frame_end
        elif st == State.GET_PARITY_BIT:
            self.state[rxtx] = State.GET_STOP_BITS
            if self.options['stop_bits']:
                return
            ss = self.frame_start[rxtx]
            es = self.samplenum + ceil(self.bit_width / 2.0)
            self.handle_frame(rxtx, ss, es)
            self.state[rxtx] = State.WAIT_FOR_START_BIT
            self.idle_start[rxtx] = frame_end
        elif st == State.GET_STOP_BITS:
            ss = self.frame_start[rxtx]
            es = self.samplenum + ceil(self.bit_width / 2.0)
            self.handle_frame(rxtx, ss, es)
            self.state[rxtx] = State.WAIT_FOR_START_BIT
            self.idle_start[rxtx] = frame_end
        else:
            self.state[rxtx] = State.WAIT_FOR_START_BIT

    def handle_frame(self, rxtx, ss, es):
        """
        Brief: Emits complete FRAME python output packet for upper layer decoders.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            ss (int): Frame start sample index.
            es (int): Frame end sample index.
        Invariants: Emits tuple (datavalue, frame_valid).
        Output: None
        """
        self.putpse(ss, es, ['FRAME', rxtx,
            (self.datavalue[rxtx], self.frame_valid[rxtx])])

    def handle_idle(self, rxtx, ss, es):
        """
        Brief: Emits IDLE python output packet when UART line remains high.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            ss (int): Idle start sample index.
            es (int): Idle end sample index.
        Invariants: Emits ['IDLE', rxtx, 0].
        Output: None
        """
        self.putpse(ss, es, ['IDLE', rxtx, 0])

    def handle_break(self, rxtx, ss, es):
        """
        Brief: Emits BREAK python packet and graphical annotation on line break condition.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            ss (int): Break start sample index.
            es (int): Break end sample index.
        Invariants: Resets state[rxtx] = State.WAIT_FOR_START_BIT.
        Output: None
        """
        self.putpse(ss, es, ['BREAK', rxtx, 0])
        self.putgse(ss, es, [Ann.RX_BREAK + rxtx,
                ['Break condition', 'Break', 'Brk', 'B']])
        self.state[rxtx] = State.WAIT_FOR_START_BIT

    def get_wait_cond(self, rxtx, inv):
        """
        Brief: Generates wait conditions (edge or sample skip) for sigrokdecode engine.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            inv (bool): True if logic line is inverted.
        Invariants: Returns falling/rising edge condition for START bit or skip count for bit sampling.
        Output:
            dict: Wait condition dictionary for Decoder.wait().
        """
        st = self.state[rxtx]
        if st == State.WAIT_FOR_START_BIT:
            return {rxtx: 'r' if inv else 'f'}
        if st in (State.GET_START_BIT, State.GET_DATA_BITS,
                 State.GET_PARITY_BIT, State.GET_STOP_BITS):
            bitnum = self.cur_frame_bit[rxtx]
            want_num = ceil(self.get_sample_point(rxtx, bitnum))
            return {'skip': want_num - self.samplenum}

    def get_idle_cond(self, rxtx, inv):
        """
        Brief: Calculates sample skip condition to check for an idle frame period.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            inv (bool): True if logic line is inverted.
        Invariants: Returns skip count dictionary or None.
        Output:
            dict or None: Idle skip condition dictionary.
        """
        if self.idle_start[rxtx] is None:
            return None
        end_of_frame = self.idle_start[rxtx] + self.frame_len_sample_count
        if end_of_frame < self.samplenum:
            return None
        return {'skip': end_of_frame - self.samplenum}

    def inspect_sample(self, rxtx, signal, inv):
        """
        Brief: Dispatches a sampled logic signal to the appropriate state handler method.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Raw signal level.
            inv (bool): True if logic line is inverted.
        Invariants: Inverts signal if inv is True.
        Output: None
        """
        if inv:
            signal = not signal

        st = self.state[rxtx]
        if st == State.WAIT_FOR_START_BIT:
            self.wait_for_start_bit(rxtx, signal)
        elif st == State.GET_START_BIT:
            self.get_start_bit(rxtx, signal)
        elif st == State.GET_DATA_BITS:
            self.get_data_bits(rxtx, signal)
        elif st == State.GET_PARITY_BIT:
            self.get_parity_bit(rxtx, signal)
        elif st == State.GET_STOP_BITS:
            self.get_stop_bits(rxtx, signal)

    def inspect_edge(self, rxtx, signal, inv):
        """
        Brief: Inspects signal edges on line to detect line BREAK conditions.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Raw signal level.
            inv (bool): True if logic line is inverted.
        Invariants: Tracks low signal duration against break_min_sample_count.
        Output: None
        """
        if inv:
            signal = not signal
        if not signal:
            self.break_start[rxtx] = self.samplenum
            return
        if self.break_start[rxtx] is None:
            return
        diff = self.samplenum - self.break_start[rxtx]
        if diff >= self.break_min_sample_count:
            ss, es = self.frame_start[rxtx], self.samplenum
            self.handle_break(rxtx, ss, es)
        self.break_start[rxtx] = None

    def inspect_idle(self, rxtx, signal, inv):
        """
        Brief: Inspects high signal periods to detect bus IDLE events.
        Params:
            rxtx (int): Direction (RX = 0, TX = 1).
            signal (int): Raw signal level.
            inv (bool): True if logic line is inverted.
        Invariants: Emits handle_idle when high signal duration exceeds frame_len_sample_count.
        Output: None
        """
        if inv:
            signal = not signal
        if not signal:
            self.idle_start[rxtx] = None
            return
        if self.idle_start[rxtx] is None:
            self.idle_start[rxtx] = self.samplenum
        diff = self.samplenum - self.idle_start[rxtx]
        if diff < self.frame_len_sample_count:
            return
        ss, es = self.idle_start[rxtx], self.samplenum
        self.handle_idle(rxtx, ss, es)
        self.idle_start[rxtx] = es

    def decode(self):
        """
        Brief: Main processing loop called by sigrokdecode engine for logic sample stream.
        Params: None
        Invariants: Must have valid samplerate and at least one configured logic channel (RX or TX).
        Output: None
        """
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        # Recompute bit_width dynamically to ensure GUI baudrate changes take immediate effect
        self.bit_width = float(self.samplerate) / float(self.options['baudrate'])

        active_channels = [ch for ch in (RX, TX) if self.has_channel(ch)]
        if not active_channels:
            raise ChannelError('Need at least one of TX or RX pins.')

        opt = self.options
        inv = [opt['invert_rx'] == 'yes', opt['invert_tx'] == 'yes']

        frame_samples = 1
        frame_samples += self.options['data_bits']
        frame_samples += 0 if self.options['parity'] == 'none' else 1
        frame_samples += self.options['stop_bits']
        frame_samples *= self.bit_width
        self.frame_len_sample_count = ceil(frame_samples)
        self.break_min_sample_count = self.frame_len_sample_count

        while True:
            conds = []
            channel_cond_map = {}

            for ch in active_channels:
                d_idx = len(conds)
                conds.append(self.get_wait_cond(ch, inv[ch]))

                e_idx = len(conds)
                conds.append({ch: 'e'})

                i_idx = None
                idle_cond = self.get_idle_cond(ch, inv[ch])
                if idle_cond:
                    i_idx = len(conds)
                    conds.append(idle_cond)

                channel_cond_map[ch] = (d_idx, e_idx, i_idx)

            pins = self.wait(conds)

            for ch in active_channels:
                signal = pins[ch]
                d_idx, e_idx, i_idx = channel_cond_map[ch]

                if self.matched[d_idx]:
                    self.inspect_sample(ch, signal, inv[ch])
                if self.matched[e_idx]:
                    self.inspect_edge(ch, signal, inv[ch])
                    self.inspect_idle(ch, signal, inv[ch])
                elif i_idx is not None and self.matched[i_idx]:
                    self.inspect_idle(ch, signal, inv[ch])
