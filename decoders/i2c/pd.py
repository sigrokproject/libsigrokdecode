##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2010-2016 Uwe Hermann <uwe@hermann-uwe.de>
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

# TODO: Look into arbitration, collision detection, clock synchronisation, etc.
# TODO: Implement support for inverting SDA/SCL levels (0->1 and 1->0).
# TODO: Implement support for detecting various bus errors.

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
 - 'BITS' (<pdata>: list of data/address bits and their ss/es numbers)

<pdata> is the data or address byte associated with the 'ADDRESS*' and 'DATA*'
command. Slave addresses do not include bit 0 (the READ/WRITE indication bit).
For example, a slave address field could be 0x51 (instead of 0xa2).
For 'START', 'START REPEAT', 'STOP', 'ACK', and 'NACK' <pdata> is None.
'''

# Meaning of table items:
# command -> [annotation class, annotation text in order of decreasing length]
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
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'i2c'
    name = 'I²C'
    longname = 'Inter-Integrated Circuit'
    desc = 'Two-wire, multi-master, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2c']
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
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (5,)),
        ('addr-data', 'Address/data', (0, 1, 2, 3, 4, 6, 7, 8, 9)),
        ('warnings', 'Warnings', (10,)),
    )
    binary = (
        ('address-read', 'Address read'),
        ('address-write', 'Address write'),
        ('data-read', 'Data read'),
        ('data-write', 'Data write'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.ss = self.es = self.ss_byte = -1
        self.is_write = None
        self.rem_addr_bytes = None
        self.is_repeat_start = False
        self.state = 'FIND START'
        self.pdu_start = None
        self.pdu_bits = 0
        self.data_bits = []

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_bitrate = self.register(srd.OUTPUT_META,
                meta=(int, 'Bitrate', 'Bitrate from Start bit to Stop bit'))

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def putp(self, data):
        self.put(self.ss, self.es, self.out_python, data)

    def putb(self, data):
        self.put(self.ss, self.es, self.out_binary, data)

    def handle_start(self, pins):
        self.ss, self.es = self.samplenum, self.samplenum
        self.pdu_start = self.samplenum
        self.pdu_bits = 0
        cmd = 'START REPEAT' if self.is_repeat_start else 'START'
        self.putp([cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putx([cls, texts])
        self.state = 'FIND ADDRESS'
        self.is_repeat_start = True
        self.is_write = None
        self.rem_addr_bytes = None
        self.data_bits.clear()

    # Gather 8 bits of data plus the ACK/NACK bit.
    def handle_address_or_data(self, pins):
        scl, sda = pins
        self.pdu_bits += 1

        # Accumulate a byte's bits, including its start position.
        # Accumulate individual bits and their start/end sample numbers
        # as we see them. Get the start sample number at the time when
        # the bit value gets sampled. Assume the start of the next bit
        # as the end sample number of the previous bit. Guess the last
        # bit's end sample number from the second last bit's width.
        # (gsi: Shouldn't falling SCL be the end of the bit value?)
        # Keep the bits in receive order (MSB first) during accumulation.
        if not self.data_bits:
            self.ss_byte = self.samplenum
        if self.data_bits:
            self.data_bits[-1][2] = self.samplenum
        self.data_bits.append([sda, self.samplenum, self.samplenum])
        if len(self.data_bits) < 8:
            return
        self.bitwidth = self.data_bits[-2][2] - self.data_bits[-3][2]
        self.data_bits[-1][2] += self.bitwidth

        # Get the byte value. Address and data are transmitted MSB-first.
        d = bitpack_msb(self.data_bits, 0)
        if self.state == 'FIND ADDRESS':
            # The READ/WRITE bit is only in the first address byte, not
            # in data bytes. Address bit pattern 0b1111_0xxx means that
            # this is a 10bit slave address, another byte follows. Get
            # the R/W direction and the address bytes count from the
            # first byte in the I2C transfer.
            addr_byte = d
            if self.rem_addr_bytes is None:
                if (addr_byte & 0xf8) == 0xf0:
                    self.rem_addr_bytes = 2
                    self.slave_addr_7 = None
                    self.slave_addr_10 = addr_byte & 0x06
                    self.slave_addr_10 <<= 7
                else:
                    self.rem_addr_bytes = 1
                    self.slave_addr_7 = addr_byte >> 1
                    self.slave_addr_10 = None
            is_seven = self.slave_addr_7 is not None
            if self.is_write is None:
                read_bit = bool(addr_byte & 1)
                shift_seven = self.options['address_format'] == 'shifted'
                if is_seven and shift_seven:
                    d = d >> 1
                self.is_write = False if read_bit else True
            else:
                self.slave_addr_10 |= addr_byte

        bin_class = -1
        if self.state == 'FIND ADDRESS' and self.is_write:
            cmd = 'ADDRESS WRITE'
            bin_class = 1
        elif self.state == 'FIND ADDRESS' and not self.is_write:
            cmd = 'ADDRESS READ'
            bin_class = 0
        elif self.state == 'FIND DATA' and self.is_write:
            cmd = 'DATA WRITE'
            bin_class = 3
        elif self.state == 'FIND DATA' and not self.is_write:
            cmd = 'DATA READ'
            bin_class = 2

        self.ss, self.es = self.ss_byte, self.samplenum + self.bitwidth

        # Reverse the list of bits to LSB first order before emitting
        # annotations and passing bits to upper layers. This may be
        # unexpected because the protocol is MSB first, but it keeps
        # backwards compatibility.
        self.data_bits.reverse()
        self.putp(['BITS', self.data_bits])
        self.putp([cmd, d])

        self.putb([bin_class, bytes([d])])

        for b, ss, es in self.data_bits:
            cls, texts = proto['BIT'][0], proto['BIT'][1:]
            texts = [t.format(b = b) for t in texts]
            self.put(ss, es, self.out_ann, [cls, texts])

        if cmd.startswith('ADDRESS') and is_seven:
            self.ss, self.es = self.samplenum, self.samplenum + self.bitwidth
            cls = proto[cmd][0]
            w = ['Write', 'Wr', 'W'] if self.is_write else ['Read', 'Rd', 'R']
            self.putx([cls, w])
            self.ss, self.es = self.ss_byte, self.samplenum

        cls, texts = proto[cmd][0], proto[cmd][1:]
        texts = [t.format(b = d) for t in texts]
        self.putx([cls, texts])

        # Done with this packet.
        self.data_bits.clear()
        self.state = 'FIND ACK'

    def get_ack(self, pins):
        scl, sda = pins
        self.ss, self.es = self.samplenum, self.samplenum + self.bitwidth
        cmd = 'NACK' if (sda == 1) else 'ACK'
        self.putp([cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putx([cls, texts])
        # Slave addresses can span one or two bytes, before data bytes
        # follow. There can be an arbitrary number of data bytes. Stick
        # with getting more address bytes if applicable, or enter or
        # remain in the data phase of the transfer otherwise.
        if self.rem_addr_bytes:
            self.rem_addr_bytes -= 1
        if self.rem_addr_bytes:
            self.state = 'FIND ADDRESS'
        else:
            self.state = 'FIND DATA'

    def handle_stop(self, pins):
        # Meta bitrate
        if self.samplerate:
            elapsed = 1 / float(self.samplerate) * (self.samplenum - self.pdu_start + 1)
            bitrate = int(1 / elapsed * self.pdu_bits)
            self.put(self.ss_byte, self.samplenum, self.out_bitrate, bitrate)

        cmd = 'STOP'
        self.ss, self.es = self.samplenum, self.samplenum
        self.putp([cmd, None])
        cls, texts = proto[cmd][0], proto[cmd][1:]
        self.putx([cls, texts])
        self.state = 'FIND START'
        self.is_repeat_start = False
        self.is_write = None
        self.data_bits.clear()

    def decode(self):
        while True:
            # State machine.
            if self.state == 'FIND START':
                # Wait for a START condition (S): SCL = high, SDA = falling.
                self.handle_start(self.wait({0: 'h', 1: 'f'}))
            elif self.state == 'FIND ADDRESS':
                # Wait for a data bit: SCL = rising.
                self.handle_address_or_data(self.wait({0: 'r'}))
            elif self.state == 'FIND DATA':
                # Wait for any of the following conditions (or combinations):
                #  a) Data sampling of receiver: SCL = rising, and/or
                #  b) START condition (S): SCL = high, SDA = falling, and/or
                #  c) STOP condition (P): SCL = high, SDA = rising
                pins = self.wait([{0: 'r'}, {0: 'h', 1: 'f'}, {0: 'h', 1: 'r'}])

                # Check which of the condition(s) matched and handle them.
                if self.matched[0]:
                    self.handle_address_or_data(pins)
                elif self.matched[1]:
                    self.handle_start(pins)
                elif self.matched[2]:
                    self.handle_stop(pins)
            elif self.state == 'FIND ACK':
                # Wait for a data/ack bit: SCL = rising.
                self.get_ack(self.wait({0: 'r'}))
