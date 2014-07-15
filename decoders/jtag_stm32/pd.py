##
## This file is part of the libsigrokdecode project.
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

import sigrokdecode as srd

# JTAG debug port data registers (in IR[3:0]) and their sizes (in bits)
# Note: The ARM DAP-DP is not IEEE 1149.1 (JTAG) compliant (as per ARM docs),
#       as it does not implement the EXTEST, SAMPLE, and PRELOAD instructions.
#       Instead, BYPASS is decoded for any of these instructions.
ir = {
    '1111': ['BYPASS', 1],  # Bypass register
    '1110': ['IDCODE', 32], # ID code register
    '1010': ['DPACC', 35],  # Debug port access register
    '1011': ['APACC', 35],  # Access port access register
    '1000': ['ABORT', 35],  # Abort register # TODO: 32 bits? Datasheet typo?
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

# ACK[2:0] in the DPACC/APACC registers (unlisted values are reserved)
ack_val = {
    '001': 'WAIT',
    '010': 'OK/FAULT',
}

# 32bit debug port registers (addressed via A[3:2])
dp_reg = {
    '00': 'Reserved', # Must be kept at reset value
    '01': 'DP CTRL/STAT',
    '10': 'DP SELECT',
    '11': 'DP RDBUFF',
}

# APB-AP registers (each of them 32 bits wide)
apb_ap_reg = {
    0x00: ['CSW', 'Control/status word'],
    0x04: ['TAR', 'Transfer address'],
    # 0x08: Reserved SBZ
    0x0c: ['DRW', 'Data read/write'],
    0x10: ['BD0', 'Banked data 0'],
    0x14: ['BD1', 'Banked data 1'],
    0x18: ['BD2', 'Banked data 2'],
    0x1c: ['BD3', 'Banked data 3'],
    # 0x20-0xf4: Reserved SBZ
    0x800000000: ['ROM', 'Debug ROM address'],
    0xfc: ['IDR', 'Identification register'],
}

# TODO: All start/end sample values in self.put() calls are bogus.
# TODO: Split off generic ARM/Cortex-M3 parts into another protocol decoder?

# Bits[31:28]: Version (here: 0x3)
#              JTAG-DP: 0x3, SW-DP: 0x2
# Bits[27:12]: Part number (here: 0xba00)
#              JTAG-DP: 0xba00, SW-DP: 0xba10
# Bits[11:1]:  JEDEC (JEP-106) manufacturer ID (here: 0x23b)
#              Bits[11:8]: Continuation code ('ARM Limited': 0x04)
#              Bits[7:1]: Identity code ('ARM Limited': 0x3b)
# Bits[0:0]:   Reserved (here: 0x1)
def decode_device_id_code(bits):
    id_hex = '0x%x' % int('0b' + bits, 2)
    ver =    '0x%x' % int('0b' + bits[-32:-28], 2)
    part =   '0x%x' % int('0b' + bits[-28:-12], 2)
    manuf =  '0x%x' % int('0b' + bits[-12:-1], 2)
    res =    '0x%x' % int('0b' + bits[-1], 2)
    return (id_hex, ver, part, manuf, res)

# DPACC is used to access debug port registers (CTRL/STAT, SELECT, RDBUFF).
# APACC is used to access all Access Port (AHB-AP) registers.

# APACC/DPACC, when transferring data IN:
# Bits[34:3] = DATA[31:0]: 32bit data to transfer (write request)
# Bits[2:1] = A[3:2]: 2-bit address (debug/access port register)
# Bits[0:0] = RnW: Read request (1) or write request (0)
def data_in(instruction, bits):
    data, a, rnw = bits[:-3], bits[-3:-1], bits[-1]
    data_hex = '0x%x' % int('0b' + data, 2)
    r = 'Read request' if (rnw == '1') else 'Write request'
    # reg = dp_reg[a] if (instruction == 'DPACC') else apb_ap_reg[a]
    reg = dp_reg[a] if (instruction == 'DPACC') else a # TODO
    return 'New transaction: DATA: %s, A: %s, RnW: %s' % (data_hex, reg, r)

# APACC/DPACC, when transferring data OUT:
# Bits[34:3] = DATA[31:0]: 32bit data which is read (read request)
# Bits[2:0] = ACK[2:0]: 3-bit acknowledge
def data_out(bits):
    data, ack = bits[:-3], bits[-3:]
    data_hex = '0x%x' % int('0b' + data, 2)
    ack_meaning = ack_val.get(ack, 'Reserved')
    return 'Previous transaction result: DATA: %s, ACK: %s' \
           % (data_hex, ack_meaning)

class Decoder(srd.Decoder):
    api_version = 2
    id = 'jtag_stm32'
    name = 'JTAG / STM32'
    longname = 'Joint Test Action Group / ST STM32'
    desc = 'ST STM32-specific JTAG protocol.'
    license = 'gplv2+'
    inputs = ['jtag']
    outputs = ['jtag_stm32']
    annotations = (
        ('text', 'Human-readable text'),
    )

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        # self.state = 'BYPASS'

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def handle_reg_bypass(self, cmd, bits):
        # TODO
        self.put(self.ss, self.es, self.out_ann, [0, ['BYPASS: ' + bits]])

    def handle_reg_idcode(self, cmd, bits):
        # TODO
        # IDCODE is a read-only register which is always accessible.
        # IR == IDCODE: The device ID code is shifted out via DR next.
        self.put(self.ss, self.es, self.out_ann,
                 [0, ['IDCODE: %s (ver=%s, part=%s, manuf=%s, res=%s)' % \
                 decode_device_id_code(bits)]])

    def handle_reg_dpacc(self, cmd, bits):
        # self.put(self.ss, self.es, self.out_ann,
        #          [0, ['DPACC/%s: %s' % (cmd, bits)]])
        s = data_in('DPACC', bits) if (cmd == 'DR TDI') else data_out(bits)
        self.put(self.ss, self.es, self.out_ann, [0, [s]])

    def handle_reg_apacc(self, cmd, bits):
        # self.put(self.ss, self.es, self.out_ann,
        #          [0, ['APACC/%s: %s' % (cmd, bits)]])
        s = data_in('APACC', bits) if (cmd == 'DR TDI') else data_out(bits)
        self.put(self.ss, self.es, self.out_ann, [0, [s]])

    def handle_reg_abort(self, cmd, bits):
        # Bits[31:1]: reserved. Bit[0]: DAPABORT.
        a = '' if (bits[0] == '1') else 'No '
        s = 'DAPABORT = %s: %sDAP abort generated' % (bits[0], a)
        self.put(self.ss, self.es, self.out_ann, [0, [s]])

        # Warn if DAPABORT[31:1] contains non-zero bits.
        if (bits[:-1] != ('0' * 31)):
            self.put(self.ss, self.es, self.out_ann,
                     [0, ['WARNING: DAPABORT[31:1] reserved!']])

    def handle_reg_unknown(self, cmd, bits):
        self.put(self.ss, self.es, self.out_ann,
                 [0, ['Unknown instruction: ' % bits]]) # TODO

    def decode(self, ss, es, data):
        # Assumption: The right-most char in the 'val' bitstring is the LSB.
        cmd, val = data

        self.ss, self.es = ss, es

        # self.put(self.ss, self.es, self.out_ann, [0, [cmd + ' / ' + val]])

        # State machine
        if self.state == 'IDLE':
            # Wait until a new instruction is shifted into the IR register.
            if cmd != 'IR TDI':
                return
            # Switch to the state named after the instruction, or 'UNKNOWN'.
            # Ignore bits other than IR[3:0]. While the IR register is only
            # 4 bits in size, some programs (e.g. OpenOCD) might fill in a
            # few more (dummy) bits. OpenOCD makes IR at least 8 bits long.
            self.state = ir.get(val[-4:], ['UNKNOWN', 0])[0]
            self.put(self.ss, self.es, self.out_ann, [0, ['IR: ' + self.state]])
        elif self.state == 'BYPASS':
            # Here we're interested in incoming bits (TDI).
            if cmd != 'DR TDI':
                return
            handle_reg = getattr(self, 'handle_reg_%s' % self.state.lower())
            handle_reg(cmd, val)
            self.state = 'IDLE'
        elif self.state in ('IDCODE', 'ABORT', 'UNKNOWN'):
            # Here we're interested in outgoing bits (TDO).
            if cmd != 'DR TDO':
                return
            handle_reg = getattr(self, 'handle_reg_%s' % self.state.lower())
            handle_reg(cmd, val)
            self.state = 'IDLE'
        elif self.state in ('DPACC', 'APACC'):
            # Here we're interested in incoming and outgoing bits (TDI/TDO).
            if cmd not in ('DR TDI', 'DR TDO'):
                return
            handle_reg = getattr(self, 'handle_reg_%s' % self.state.lower())
            handle_reg(cmd, val)
            if cmd == 'DR TDO': # TODO: Assumes 'DR TDI' comes before 'DR TDO'
                self.state = 'IDLE'
