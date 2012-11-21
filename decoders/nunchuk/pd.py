##
## This file is part of the sigrok project.
##
## Copyright (C) 2010-2012 Uwe Hermann <uwe@hermann-uwe.de>
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

# Nintendo Wii Nunchuk protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'nunchuk'
    name = 'Nunchuk'
    longname = 'Nintendo Wii Nunchuk'
    desc = 'Nintendo Wii Nunchuk controller protocol.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['nunchuck']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Text (verbose)', 'Human-readable text (verbose)'],
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.sx = self.sy = self.ax = self.ay = self.az = self.bz = self.bc = -1
        self.databytecount = 0
        self.reg = 0x00
        self.init_seq = []

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'nunchuk')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'nunchuk')

    def report(self):
        pass

    def putx(self, data):
        # Helper for annotations which span exactly one I2C packet.
        self.put(self.ss, self.es, self.out_ann, data)

    def putb(self, data):
        # Helper for annotations which span a block of I2C packets.
        self.put(self.block_start_sample, self.block_end_sample,
                 self.out_ann, data)

    def handle_reg_0x00(self, databyte):
        self.sx = databyte
        self.putx([0, ['Analog stick X position: 0x%02x' % self.sx]])
        self.putx([1, ['SX: 0x%02x' % self.sx]])

    def handle_reg_0x01(self, databyte):
        self.sy = databyte
        self.putx([0, ['Analog stick Y position: 0x%02x' % self.sy]])
        self.putx([1, ['SY: 0x%02x' % self.sy]])

    def handle_reg_0x02(self, databyte):
        self.ax = databyte << 2
        self.putx([0, ['Accelerometer X value bits[9:2]: 0x%03x' % self.ax]])
        self.putx([1, ['AX[9:2]: 0x%03x' % self.ax]])

    def handle_reg_0x03(self, databyte):
        self.ay = databyte << 2
        self.putx([0, ['Accelerometer Y value bits[9:2]: 0x%03x' % self.ay]])
        self.putx([1, ['AY[9:2]: 0x%x' % self.ay]])

    def handle_reg_0x04(self, databyte):
        self.az = databyte << 2
        self.putx([0, ['Accelerometer Z value bits[9:2]: 0x%03x' % self.az]])
        self.putx([1, ['AZ[9:2]: 0x%x' % self.az]])

    # TODO: Bit-exact annotations.
    def handle_reg_0x05(self, databyte):
        self.bz = (databyte & (1 << 0)) >> 0 # Bits[0:0]
        self.bc = (databyte & (1 << 1)) >> 1 # Bits[1:1]
        ax_rest = (databyte & (3 << 2)) >> 2 # Bits[3:2]
        ay_rest = (databyte & (3 << 4)) >> 4 # Bits[5:4]
        az_rest = (databyte & (3 << 6)) >> 6 # Bits[7:6]
        self.ax |= ax_rest
        self.ay |= ay_rest
        self.az |= az_rest

        s = '' if (self.bz == 0) else 'not '
        self.putx([0, ['Z button: %spressed' % s]])
        self.putx([1, ['BZ: %d' % self.bz]])

        s = '' if (self.bc == 0) else 'not '
        self.putx([0, ['C button: %spressed' % s]])
        self.putx([1, ['BC: %d' % self.bc]])

        self.putx([0, ['Accelerometer X value bits[1:0]: 0x%x' % ax_rest]])
        self.putx([1, ['AX[1:0]: 0x%x' % ax_rest]])

        self.putx([0, ['Accelerometer Y value bits[1:0]: 0x%x' % ay_rest]])
        self.putx([1, ['AY[1:0]: 0x%x' % ay_rest]])

        self.putx([0, ['Accelerometer Z value bits[1:0]: 0x%x' % az_rest]])
        self.putx([1, ['AZ[1:0]: 0x%x' % az_rest]])

    def output_full_block_if_possible(self):
        # For now, only output summary annotation if all values are available.
        t = (self.sx, self.sy, self.ax, self.ay, self.az, self.bz, self.bc)
        if -1 in t:
            return

        s = 'Analog stick X position: 0x%02x\n' % self.sx
        s += 'Analog stick Y position: 0x%02x\n' % self.sy
        s += 'Z button: %spressed\n' % ('' if (self.bz == 0) else 'not ')
        s += 'C button: %spressed\n' % ('' if (self.bc == 0) else 'not ')
        s += 'Accelerometer X value: 0x%03x\n' % self.ax
        s += 'Accelerometer Y value: 0x%03x\n' % self.ay
        s += 'Accelerometer Z value: 0x%03x\n' % self.az
        self.put(self.block_start_sample, self.block_end_sample,
                 self.out_ann, [0, [s]])

        s = 'SX = 0x%02x, SY = 0x%02x, AX = 0x%02x, AY = 0x%02x, ' \
            'AZ = 0x%02x, BZ = 0x%02x, BC = 0x%02x' % (self.sx, \
            self.sy, self.ax, self.ay, self.az, self.bz, self.bc)
        self.put(self.block_start_sample, self.block_end_sample,
                 self.out_ann, [1, [s]])

    def handle_reg_write(self, databyte):
        self.putx([0, ['Nunchuk write: 0x%02x' % databyte]])
        if len(self.init_seq) < 2:
            self.init_seq.append(databyte)

    def output_init_seq(self):
        if len(self.init_seq) != 2:
            self.putb([2, ['Init sequence was %d bytes long (2 expected)' % \
                      len(self.init_seq)]])

        if self.init_seq != (0x40, 0x00):
            self.putb([2, ['Unknown init sequence (expected: 0x40 0x00)']])

        # TODO: Detect Nunchuk clones (they have different init sequences).
        s = 'Initialized Nintendo Wii Nunchuk'

        self.putb([0, [s]])
        self.putb([1, ['INIT']])

    def decode(self, ss, es, data):
        cmd, databyte = data

        # Store the start/end samples of this I2C packet.
        self.ss, self.es = ss, es

        # State machine.
        if self.state == 'IDLE':
            # Wait for an I2C START condition.
            if cmd != 'START':
                return
            self.state = 'GET SLAVE ADDR'
            self.block_start_sample = ss
        elif self.state == 'GET SLAVE ADDR':
            # Wait for an address read/write operation.
            if cmd == 'ADDRESS READ':
                self.state = 'READ REGS'
            elif cmd == 'ADDRESS WRITE':
                self.state = 'WRITE REGS'
        elif self.state == 'READ REGS':
            if cmd == 'DATA READ':
                handle_reg = getattr(self, 'handle_reg_0x%02x' % self.reg)
                handle_reg(databyte)
                self.reg += 1
            elif cmd == 'STOP':
                self.block_end_sample = es
                self.output_full_block_if_possible()
                self.sx = self.sy = self.ax = self.ay = self.az = -1
                self.bz = self.bc = -1
                self.state = 'IDLE'
            else:
                # self.putx([0, ['Ignoring: %s (data=%s)' % (cmd, databyte)]])
                pass
        elif self.state == 'WRITE REGS':
            if cmd == 'DATA WRITE':
                self.handle_reg_write(databyte)
            elif cmd == 'STOP':
                self.block_end_sample = es
                self.output_init_seq()
                self.init_seq = []
                self.state = 'IDLE'
            else:
                # self.putx([0, ['Ignoring: %s (data=%s)' % (cmd, databyte)]])
                pass
        else:
            raise Exception('Invalid state: %s' % self.state)

