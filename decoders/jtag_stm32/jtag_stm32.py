##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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

# ST STM32 JTAG protocol decoder

import sigrokdecode as srd

# JTAG debug port data registers (in IR[3:0]) and their sizes (in bits)
ir = {
    '1111': ['BYPASS', 1],  # Bypass register
    '1110': ['IDCODE', 32], # ID code register
    '1010': ['DPACC', 35],  # Debug port access register
    '1011': ['APACC', 35],  # Access port access register
    '1000': ['ABORT', 35],  # Abort register
}

# ARM Cortex-M3 r1p1-01rel0 ID code
cm3_idcode = 0x3ba00477

# JTAG ID code in the STM32F10xxx BSC (boundary scan) TAP
jtag_idcode = {
    0x06412041: 'Low-density device, rev. A',
    0x06410041: 'Medium-density device, rev. A',
    0x16410041: 'Medium-density device, rev. B/Z/Y',
    0x06414041: 'High-density device, rev. A/Z/Y',
    0x06430041: 'XL-density device, rev. A',
    0x06418041: 'Connectivity-line device, rev. A/Z',
}

# ACK[2:0] in the DPACC/APACC registers
ack_val = {
    '000': 'Reserved',
    '001': 'WAIT',
    '010': 'OK/FAULT',
    '011': 'Reserved',
    '100': 'Reserved',
    '101': 'Reserved',
    '110': 'Reserved',
    '111': 'Reserved',
}

# 32bit debug port registers (addressed via A[3:2])
reg = {
    '00': 'Reserved', # Must be kept at reset value
    '01': 'DP CTRL/STAT',
    '10': 'DP SELECT',
    '11': 'DP RDBUFF',
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'jtag_stm32'
    name = 'JTAG / STM32'
    longname = 'Joint Test Action Group / ST STM32'
    desc = 'ST STM32-specific JTAG protocol.'
    license = 'gplv2+'
    inputs = ['jtag']
    outputs = ['jtag_stm32']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['ASCII', 'TODO: description'],
    ]

    def __init__(self, **kwargs):
        self.state = 'IDLE'

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'jtag_stm32')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'jtag_stm32')

    def report(self):
        pass

    def handle_reg_bypass(self, bits):
        # TODO
        pass

    def handle_reg_idcode(self, bits):
        # TODO
        pass

    # When transferring data IN:
    #   Bits[34:3] = DATA[31:0]: 32bit data to transfer (write request)
    #   Bits[2:1] = A[3:2]: 2-bit address of a debug port register
    #   Bits[0:0] = RnW: Read request (1) or write request (0)
    # When transferring data OUT:
    #   Bits[34:3] = DATA[31:0]: 32bit data which is read (read request)
    #   Bits[2:0] = ACK[2:0]: 3-bit acknowledge
    def handle_reg_dpacc(self, bits):
        self.put(self.ss, self.es, self.out_ann, [0, ['bits: ' + bits]])

        # Data IN
        data, a, rnw = bits[:-3], bits[-4:-1], bits[-1]
        r = 'Read request' if (rnw == '1') else 'Write request'
        s = 'DATA: %s, A: %s, RnW: %s' % (data, ack_val[a], r)
        self.put(self.ss, self.es, self.out_ann, [0, [s]])

        # Data OUT
        # data, ack = bits[:-3], bits[-3:]
        # ack_meaning = ack_val[ack]
        # s = 'DATA: %s, ACK: %s' % (data, ack_meaning)
        # self.put(self.ss, self.es, self.out_ann, [0, [s]])

    def handle_reg_apacc(self, bits):
        # TODO
        pass

    def handle_reg_abort(self, bits):
        # Bits[31:1]: reserved. Bit[0]: DAPABORT.
        a = '' if (bits[0] == '1') else 'No '
        s = 'DAPABORT = %s: %sDAP abort generated' % (bits[0], a)
        self.put(self.ss, self.es, self.out_ann, [0, [s]])

        if (bits[:-1] != ('0' * 31)):
            pass # TODO: Error

    def decode(self, ss, es, data):
        # Assumption: The right-most char in the 'val' bitstring is the LSB.
        cmd, val = data

        self.ss, self.es = ss, es

        self.put(self.ss, self.es, self.out_ann, [0, [cmd + ' / ' + val]])

        # State machine
        # TODO

