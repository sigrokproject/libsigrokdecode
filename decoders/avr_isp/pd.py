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

# AVR ISP protocol decoder

import sigrokdecode as srd
from .parts import *

VENDOR_CODE_ATMEL = 0x1e

class Decoder(srd.Decoder):
    api_version = 1
    id = 'avr_isp'
    name = 'AVR ISP'
    longname = 'AVR in-system programming'
    desc = 'Protocol for in-system programming Atmel AVR MCUs.'
    license = 'gplv2+'
    inputs = ['spi', 'logic']
    outputs = ['avr_isp']
    probes = []
    optional_probes = [
        {'id': 'reset', 'name': 'RESET#', 'desc': 'Target AVR MCU reset'},
    ]
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.mosi_bytes, self.miso_bytes = [], []
        self.cmd_ss, self.cmd_es = 0, 0
        self.xx, self.yy, self.zz, self.mm = 0, 0, 0, 0

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'avr_isp')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'avr_isp')

    def report(self):
        pass

    def putx(self, data):
        self.put(self.cmd_ss, self.cmd_es, self.out_ann, data)

    def handle_cmd_programming_enable(self, cmd, ret):
        # Programming enable.
        # Note: The chip doesn't send any ACK for 'Programming enable'.
        self.putx([0, ['Programming enable']])

        # Sanity check on reply.
        if ret[1:4] != [0xac, 0x53, cmd[2]]:
            self.putx([1, ['Warning: Unexpected bytes in reply!']])

    def handle_cmd_read_signature_byte_0x00(self, cmd, ret):
        # Signature byte 0x00: vendor code.
        self.vendor_code = ret[3]
        v = vendor_code[self.vendor_code]
        self.putx([0, ['Vendor code: 0x%02x (%s)' % (ret[3], v)]])

        # Store for later.
        self.xx = cmd[1] # Same as ret[2].
        self.yy = cmd[3]
        self.zz = ret[0]

        # Sanity check on reply.
        if ret[1] != 0x30 or ret[2] != cmd[1]:
            self.putx([1, ['Warning: Unexpected bytes in reply!']])

        # Sanity check for the vendor code.
        if self.vendor_code != VENDOR_CODE_ATMEL:
            self.putx([1, ['Warning: Vendor code was not 0x1e (Atmel)!']])

    def handle_cmd_read_signature_byte_0x01(self, cmd, ret):
        # Signature byte 0x01: part family and memory size.
        self.part_fam_flash_size = ret[3]
        self.putx([0, ['Part family / memory size: 0x%02x' % ret[3]]])

        # Store for later.
        self.mm = cmd[3]

        # Sanity check on reply.
        if ret[1] != 0x30 or ret[2] != cmd[1] or ret[0] != self.yy:
            self.putx([1, ['Warning: Unexpected bytes in reply!']])

    def handle_cmd_read_signature_byte_0x02(self, cmd, ret):
        # Signature byte 0x02: part number.
        self.part_number = ret[3]
        self.putx([0, ['Part number: 0x%02x' % ret[3]]])

        # TODO: Fix range.
        p = part[(self.part_fam_flash_size, self.part_number)]
        self.putx([0, ['Device: Atmel %s' % p]])

        # Sanity check on reply.
        if ret[1] != 0x30 or ret[2] != self.xx or ret[0] != self.mm:
            self.putx([1, ['Warning: Unexpected bytes in reply!']])

        self.xx, self.yy, self.zz, self.mm = 0, 0, 0, 0

    def handle_cmd_chip_erase(self, cmd, ret):
        # Chip erase (erases both flash an EEPROM).
        # Upon successful chip erase, the lock bits will also be erased.
        # The only way to end a Chip Erase cycle is to release RESET#.
        self.putx([0, ['Chip erase']])

        # TODO: Check/handle RESET#.

        # Sanity check on reply.
        bit = (ret[2] & (1 << 7)) >> 7
        if ret[1] != 0xac or bit != 1 or ret[3] != cmd[2]:
            self.putx([1, ['Warning: Unexpected bytes in reply!']])

    def handle_cmd_read_fuse_bits(self, cmd, ret):
        # Read fuse bits.
        self.putx([0, ['Read fuse bits: 0x%02x' % ret[3]]])

        # TODO: Decode fuse bits.
        # TODO: Sanity check on reply.

    def handle_cmd_read_fuse_high_bits(self, cmd, ret):
        # Read fuse high bits.
        self.putx([0, ['Read fuse high bits: 0x%02x' % ret[3]]])

        # TODO: Decode fuse bits.
        # TODO: Sanity check on reply.

    def handle_cmd_read_extended_fuse_bits(self, cmd, ret):
        # Read extended fuse bits.
        self.putx([0, ['Read extended fuse bits: 0x%02x' % ret[3]]])

        # TODO: Decode fuse bits.
        # TODO: Sanity check on reply.

    def handle_command(self, cmd, ret):
        if cmd[:2] == [0xac, 0x53]:
            self.handle_cmd_programming_enable(cmd, ret)
        elif cmd[0] == 0xac and (cmd[1] & (1 << 7)) == (1 << 7):
            self.handle_cmd_chip_erase(cmd, ret)
        elif cmd[:3] == [0x50, 0x00, 0x00]:
            self.handle_cmd_read_fuse_bits(cmd, ret)
        elif cmd[:3] == [0x58, 0x08, 0x00]:
            self.handle_cmd_read_fuse_high_bits(cmd, ret)
        elif cmd[:3] == [0x50, 0x08, 0x00]:
            self.handle_cmd_read_extended_fuse_bits(cmd, ret)
        elif cmd[0] == 0x30 and cmd[2] == 0x00:
            self.handle_cmd_read_signature_byte_0x00(cmd, ret)
        elif cmd[0] == 0x30 and cmd[2] == 0x01:
            self.handle_cmd_read_signature_byte_0x01(cmd, ret)
        elif cmd[0] == 0x30 and cmd[2] == 0x02:
            self.handle_cmd_read_signature_byte_0x02(cmd, ret)
        else:
            c = '%02x %02x %02x %02x' % tuple(cmd)
            r = '%02x %02x %02x %02x' % tuple(ret)
            self.putx([0, ['Unknown command: %s (reply: %s)!' % (c, r)]])

    def decode(self, ss, es, data):
        ptype, mosi, miso = data

        if ptype != 'DATA':
            return

        # self.put(0, 0, self.out_ann,
        #          [0, ['MOSI: 0x%02x, MISO: 0x%02x' % (mosi, miso)]])

        self.ss, self.es = ss, es

        # Append new bytes.
        self.mosi_bytes.append(mosi)
        self.miso_bytes.append(miso)

        if len(self.mosi_bytes) == 0:
            self.cmd_ss = ss

        # All commands consist of 4 bytes.
        if len(self.mosi_bytes) < 4:
            return

        self.cmd_es = es

        self.handle_command(self.mosi_bytes, self.miso_bytes)

        self.mosi_bytes = []
        self.miso_bytes = []

