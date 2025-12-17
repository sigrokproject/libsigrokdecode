##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2025 Jorge Marques <jorge.marques@analog.com>
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

# TODO: Implement support for 10-bit I²C address.
# TODO: Implement High Data Rate (HDR).
# TODO: Implement Command Command Code (CCC).
# TODO: Implement Dynamic address assignement (DAA).
# TODO: Implement Hot-join (HJ).
# TODO: Improve ambiguous IBI/I²C read: Combine change in data rate, DAA parsing.
# TODO: Look for bus violations (IBI issued while disabled, improper transfers)

from common.srdhelper import bitpack_msb
import sigrokdecode as srd

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>:
 - 'START' (START condition)
 - 'START REPEAT' (Repeated START condition)
 - 'ADDRESS READ' (Slave address, read)
 - 'ADDRESS WRITE' (Slave address, write)
 - 'DATA READ' (Data, read)
 - 'DATA WRITE' (Data, write)
 - 'STOP' (STOP condition)
 - 'ACK' (ACK bit)
 - 'NACK' (NACK bit)
 - 'T-BIT' (Parity or transition bit)
 - 'IBI' (In-Band Interrupt)
 - 'IBI MDB' (IBI Mandatory Data Byte)
 - 'IBI DATA' (IBI extra bytes)
 - 'BITS' (<pdata>: list of data/address bits and their ss/es numbers)

<pdata> is the data or address byte associated with the 'ADDRESS*', 'DATA*',
'IBI MDB', and 'IBI DATA' commands. For 'START', 'STOP', 'ACK', 'NACK', and
'T-BIT' <pdata> is None.
'''

proto = {
    'START':         [0, 'Start', 'S'],
    'START REPEAT':  [1, 'Start repeat', 'Sr'],
    'STOP':          [2, 'Stop', 'P'],
    'ACK':           [3, 'ACK', 'A'],
    'NACK':          [4, 'NACK', 'N'],
    'BIT':           [5, '{b:1d}'],
    'ADDRESS READ':  [6, 'Address read: {b:02X}', 'AR: {b:02X}', '{b:02X}'],
    'ADDRESS WRITE': [7, 'Address write: {b:02X}', 'AW: {b:02X}', '{b:02X}'],
    'DATA READ':     [8, 'Data read: {b:02X}', 'DR: {b:02X}', '{b:02X}'],
    'DATA WRITE':    [9, 'Data write: {b:02X}', 'DW: {b:02X}', '{b:02X}'],
    'IBI':           [10, 'IBI from: {b:02X}', 'IBI: {b:02X}', 'IBI'],
    'IBI MDB':       [11, 'MDB: {b:02X}', 'MDB:{b:02X}', '{b:02X}'],
    'IBI DATA':      [12, 'IBI Data: {b:02X}', 'ID: {b:02X}', '{b:02X}'],
    'T-BIT-WRITE':   [13, 'T-bit: {b} {status}', 'T:{b}{s}', 'T'],
    'T-BIT-READ':    [14, 'T-bit: {b} {status}', 'T:{b}{s}', 'T'],
    'T-BIT-IBI':     [15, 'T-bit: {b} (IBI)', 'T:{b}', 'T'],
    'WARN':          [16, '{text}'],
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'i3c'
    name = 'I3C'
    longname = 'Improved Inter-Integrated Circuit'
    desc = 'Two-wire, multi-master, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i3c']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'scl', 'name': 'SCL', 'desc': 'Serial clock line'},
        {'id': 'sda', 'name': 'SDA', 'desc': 'Serial data line'},
    )
    options = (
        {'id': 'address_format', 'desc': 'Displayed slave address format',
            'default': 'shifted', 'values': ('shifted', 'unshifted')},
    )
    annotations = (
        ('start', 'Start condition'),
        ('repeat-start', 'Repeat start condition'),
        ('stop', 'Stop condition'),
        ('ack', 'ACK'),
        ('nack', 'NACK'),
        ('bit', 'Data/address bit'),
        ('address-read', 'Address read'),
        ('address-write', 'Address write'),
        ('data-read', 'Data read'),
        ('data-write', 'Data write'),
        ('ibi', 'In-Band Interrupt'),
        ('ibi-mdb', 'IBI Mandatory Data Byte'),
        ('ibi-data', 'IBI Additional Data'),
        ('t-bit-write', 'T-bit (parity bit)'),
        ('t-bit-read', 'T-bit (transtion bit)'),
        ('t-bit-ibi', 'T-bit (transition bit)'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (6,)),
        ('addr-data', 'Address/data', (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 16)),
        ('warnings', 'Warnings', (14,)),
    )
    binary = (
        ('address-read', 'Address read'),
        ('address-write', 'Address write'),
        ('data-read', 'Data read'),
        ('data-write', 'Data write'),
        ('ibi-mdb', 'IBI MDB'),
        ('ibi-data', 'IBI data'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.is_write = None
        self.slave_addr = None
        self.is_repeat_start = False
        self.is_ibi = False
        self.is_sdr = False
        self.ibi_has_data = False
        self.ibi_mdb_received = False
        self.current_start_is_repeat = False
        self.pdu_start = None
        self.pdu_bits = 0
        self.data_bits = []
        self.bitwidth = 0
        self.state = 'IDLE'
        self.last_data_byte = None
        self.i3c_addrs = set()

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_bitrate = self.register(srd.OUTPUT_META,
                meta=(int, 'Bitrate', 'Bitrate from Start bit to Stop bit'))

    def putg(self, ss, es, cls, text):
        self.put(ss, es, self.out_ann, [cls, text])

    def putp(self, ss, es, data):
        self.put(ss, es, self.out_python, data)

    def putb(self, ss, es, data):
        self.put(ss, es, self.out_binary, data)

    def handle_start(self, ss, es):

        if self.is_repeat_start:
            cmd = 'START REPEAT'
        else:
            cmd = 'START'
            self.pdu_start = ss
            self.pdu_bits = 0
        self.state = 'ADDRESS'
        self.putp(ss, es, [cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putg(ss, es, cls, texts)
        self.current_start_is_repeat = self.is_repeat_start
        self.is_repeat_start = True
        self.is_write = None
        self.is_ibi = False
        self.ibi_has_data = False
        self.ibi_mdb_received = False
        self.slave_addr = None
        self.data_bits.clear()
        self.bitwidth = 0

    def handle_address_or_data(self, ss, es, value):
        self.pdu_bits += 1

        # Accumulate a byte's bits, including its start position.
        if self.data_bits:
            self.data_bits[-1][2] = ss
        self.data_bits.append([value, ss, es])
        if len(self.data_bits) < 8:
            return
        self.bitwidth = self.data_bits[-2][2] - self.data_bits[-3][2]
        self.data_bits[-1][2] = self.data_bits[-1][1] + self.bitwidth

        # Get the byte value. Address and data are transmitted MSB-first.
        d = bitpack_msb(self.data_bits, 0)
        ss_byte, es_byte = self.data_bits[0][1], self.data_bits[-1][2]

        # Handle address byte.
        if self.state == 'ADDRESS':
            addr_byte = d
            read_bit = bool(addr_byte & 1) # 0 is write, 1 read or IBI
            addr_7bit = addr_byte >> 1

            if addr_7bit == 0x7e:
                self.is_sdr = True

            # Collect address after broadcast address + repeated start as known
            # i3c targets.
            if (self.is_sdr and self.current_start_is_repeat and
                addr_7bit != 0x7e):
                self.i3c_addrs.add(addr_7bit)

            # An IBI header ends with bit 0, just like an I²C read transfer, so
            # the best effort to detect an IBI as an observer:
            # * Address is not I3C Broadcast Address.
            # * Only occurs after a Start, never Repeated Start.
            # * Subsequent data after ACK:
            #   - None: assume BCR bit[2] = 0, so an IBI.
            #   - With: assume IBI if address in i3c_addrs set.
            # Limitations: If not yet in set, will be mislabeled as i2c read.
            if (addr_7bit in self.i3c_addrs and not
                self.current_start_is_repeat and read_bit):
                self.is_ibi = True
                self.slave_addr = addr_7bit

            if self.options['address_format'] == 'shifted':
                d >>= 1

            self.is_write = False if read_bit else True

            if self.is_ibi:
                cmd = 'IBI'
                bin_class = -1
                texts = proto[cmd][1:]
                texts = [t.format(b = self.slave_addr) for t in texts]
            elif self.is_write:
                cmd = 'ADDRESS WRITE'
                bin_class = 1
                texts = proto[cmd][1:]
                texts = [t.format(b = d) for t in texts]
            else:
                cmd = 'ADDRESS READ'
                bin_class = 0
                texts = proto[cmd][1:]
                texts = [t.format(b = d) for t in texts]

            self.state = 'IBI-ACK' if self.is_ibi else 'ACK'

        # Handle IBI MDB.
        elif self.state == 'IBI-MDB':
            cmd = 'IBI MDB'
            bin_class = 4
            texts = proto[cmd][1:]
            texts = [t.format(b = d) for t in texts]
            self.ibi_mdb_received = True
            self.state = 'IBI-T-BIT'

        # Handle IBI extra bytes
        elif self.state == 'IBI-DATA':
            cmd = 'IBI DATA'
            bin_class = 5
            texts = proto[cmd][1:]
            texts = [t.format(b = d) for t in texts]
            self.last_data_byte = d
            self.state = 'IBI-T-BIT'

        # Handle SDR data
        else:
            # Handle IBI MDB
            if self.is_ibi and self.state == 'DATA':
                cmd = 'IBI MDB'
                bin_class = 4
                texts = proto[cmd][1:]
                texts = [t.format(b = d) for t in texts]
                self.ibi_mdb_received = True
                self.state = 'IBI-T-BIT'

            # Handle data
            if not self.is_ibi and self.is_write:
                cmd = 'DATA WRITE'
                bin_class = 3
                self.last_data_byte = d
                # In I3C mode: T-bit after data write
                # In I²C mode: ACK/NACK
                if self.is_sdr:
                    self.state = 'T-BIT-WRITE'
                else:
                    self.state = 'ACK'
                texts = proto[cmd][1:]
                texts = [t.format(b = d) for t in texts]
            elif not self.is_ibi:
                cmd = 'DATA READ'
                bin_class = 2
                self.last_data_byte = d

                if self.is_sdr:
                    self.state = 'T-BIT-READ'
                else:
                    self.state = 'ACK'
                texts = proto[cmd][1:]
                texts = [t.format(b = d) for t in texts]

        # Emit annotations
        lsb_bits = self.data_bits[:]
        lsb_bits.reverse()
        self.putp(ss_byte, es_byte, ['BITS', lsb_bits])
        self.putp(ss_byte, es_byte, [cmd, d])

        if bin_class >= 0:
            self.putb(ss_byte, es_byte, [bin_class, bytes([d])])

        for bit_value, ss_bit, es_bit in lsb_bits:
            cls, texts_bit = proto['BIT'][0], proto['BIT'][1:]
            texts_bit = [t.format(b = bit_value) for t in texts_bit]
            self.putg(ss_bit, es_bit, cls, texts_bit)

        cls = proto[cmd][0]
        self.putg(ss_byte, es_byte, cls, texts)

    def get_ack(self, ss, es, value):
        ss_bit, es_bit = ss, es
        cmd = 'ACK' if value == 0 else 'NACK'
        self.putp(ss_bit, es_bit, [cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putg(ss_bit, es_bit, cls, texts)
        self.data_bits.clear()

        # State transitions
        if self.state == 'IBI-ACK':
            # After IBI address ACK, expect MDB
            if value == 0:
                self.state = 'IBI-MDB'
            else:
                self.state = 'STOP-PENDING'
        elif self.state == 'ACK':
            if value == 0:
                self.state = 'DATA'
            else:
                self.state = 'STOP-PENDING'

    def get_write_t_bit(self, ss, es, value):
        """Handle T-bit after data write (parity bit)

        Assert odd pariety.
        """
        ss_bit, es_bit = ss, es
        cmd = 'T-BIT-WRITE'

        if self.last_data_byte is not None:
            ones_count = bin(self.last_data_byte).count('1')
            expected_parity = (ones_count % 2) ^ 1
            parity_ok = (value == expected_parity)

            if parity_ok:
                status = f"(Parity OK, data=0x{self.last_data_byte:02X})"
                status_short = "OK"
            else:
                status = f"(Parity ERR, expected={expected_parity}, data=0x{self.last_data_byte:02X})"
                status_short = "ERR"
        else:
            status = "(Parity)"
            status_short = ""

        self.putp(ss_bit, es_bit, [cmd, value])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        texts = [t.format(b=value, status=status, s=status_short) for t in texts]
        self.putg(ss_bit, es_bit, cls, texts)
        self.data_bits.clear()

        self.state = 'DATA'

    def get_t_bit(self, ss_rise, es_rise, value_rising, ss_fall, value_falling):
        """Handle transition bit

        Transition bit is sampled on both SCL edges:
        * 1->1 : Controller and target agree to continue read
        * 0->0 : Target ended transfer, expect STOP or repeated START
        * 1->0 : Controller ended transfer, expect STOP
        """
        ss_bit, es_bit = ss_rise, es_rise
        cmd = 'T-BIT-IBI' if self.is_ibi else 'T-BIT-READ'

        # Detect transition
        if value_rising == 1 and value_falling == 1:
            # Both edges high - continue reading
            transition = "1->1"
            status = f"(Continue, {transition})"
            status_short = "C"
        elif value_rising == 0 and value_falling == 0:
            # Both edges low - target ended
            transition = "0->0"
            status = f"(Target ended, {transition})"
            status_short = "TE"
        else:
            # Transition - controller ended
            transition = f"{value_rising}->{value_falling}"
            status = f"(Controller ended, {transition})"
            status_short = "CE"

        # Include last data byte in annotation
        if not self.is_ibi and self.last_data_byte is not None:
            status = f"{status}, last=0x{self.last_data_byte:02X}"

        self.putp(ss_bit, es_bit, [cmd, (value_rising, value_falling)])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        texts = [t.format(b=f"{transition}", status=status, s=status_short) for t in texts]
        self.putg(ss_bit, es_bit, cls, texts)
        self.data_bits.clear()

        # State transitions
        if value_rising == 1 and value_falling == 1:
            if self.is_ibi:
                self.ibi_has_data = True
                self.state = 'IBI-DATA'
            else:
                self.state = 'DATA'
        else:
            if self.is_ibi:
                self.ibi_has_data = False
            self.state = 'STOP-PENDING'

    def handle_stop(self, ss, es):
        # Meta bitrate
        if self.samplerate and self.pdu_start:
            elapsed = es - self.pdu_start + 1
            elapsed /= self.samplerate
            bitrate = int(1 / elapsed * self.pdu_bits)
            ss_meta, es_meta = self.pdu_start, es
            self.put(ss_meta, es_meta, self.out_bitrate, bitrate)
            self.pdu_start = None
            self.pdu_bits = 0

        cmd = 'STOP'
        self.putp(ss, es, [cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putg(ss, es, cls, texts)
        self.is_repeat_start = False
        self.is_write = None
        self.is_ibi = False
        self.ibi_has_data = False
        self.ibi_mdb_received = False
        self.data_bits.clear()
        self.state = 'IDLE'

    def decode(self):
        while True:
            if self.state == 'IDLE':
                # Wait for a START condition (S): SCL = high, SDA = falling.
                pins = self.wait({0: 'h', 1: 'f'})
                ss, es = self.samplenum, self.samplenum
                self.handle_start(ss, es)

            elif self.state in ['ADDRESS', 'DATA', 'IBI-MDB', 'IBI-DATA']:
                if len(self.data_bits) < 8:
                    # Wait for SCL rising edge OR START/STOP conditions
                    pins = self.wait([{0: 'r'}, {0: 'h', 1: 'f'}, {0: 'h', 1: 'r'}])

                    # Check which condition matched
                    if self.matched[0]:
                        # SCL rising - sample data bit
                        _, sda = pins
                        ss, es = self.samplenum, self.samplenum + self.bitwidth
                        self.handle_address_or_data(ss, es, sda)
                    elif self.matched[1]:
                        # START condition (repeated START)
                        ss, es = self.samplenum, self.samplenum
                        self.handle_start(ss, es)
                    elif self.matched[2]:
                        # STOP condition
                        ss, es = self.samplenum, self.samplenum
                        self.handle_stop(ss, es)
                # If we have 8 bits, state has already transitioned in handle_address_or_data

            # Wait for ACK bit
            elif self.state in ['ACK', 'IBI-ACK']:
                pins = self.wait({0: 'r'})
                _, sda = pins
                ss, es = self.samplenum, self.samplenum + self.bitwidth
                self.get_ack(ss, es, sda)

            # Wait for transition bit
            elif self.state in ['IBI-T-BIT', 'T-BIT-READ']:
                # Sample on rising edge
                pins = self.wait({0: 'r'})
                _, sda_rising = pins
                ss_rise = self.samplenum

                # Sample on falling edge
                pins = self.wait({0: 'f'})
                _, sda_falling = pins
                ss_fall = self.samplenum

                es_rise = self.samplenum + self.bitwidth
                self.get_t_bit(ss_rise, es_rise, sda_rising, ss_fall, sda_falling)

            # Wait for pariety bit
            elif self.state == 'T-BIT-WRITE':
                pins = self.wait({0: 'r'})
                _, sda = pins
                ss, es = self.samplenum, self.samplenum + self.bitwidth
                self.get_write_t_bit(ss, es, sda)

            # Wait for STOP or repeated START
            elif self.state == 'STOP-PENDING':
                # Wait for STOP (SCL = high, SDA = rising) or START
                pins = self.wait([{0: 'h', 1: 'r'}, {0: 'h', 1: 'f'}])
                ss, es = self.samplenum, self.samplenum
                if self.matched[0]:
                    self.handle_stop(ss, es)
                elif self.matched[1]:
                    self.handle_start(ss, es)

            else: # Unreachable
                pins = self.wait([{0: 'e'}, {1: 'e'}])
