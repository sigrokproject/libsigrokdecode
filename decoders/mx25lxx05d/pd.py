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

# Macronix MX25Lxx05D SPI (NOR) flash chip protocol decoder

# Note: Works for MX25L1605D/MX25L3205D/MX25L6405D.

import sigrokdecode as srd

# Dict which maps command IDs to their names and descriptions.
cmds = {
    0x06: ('WREN', 'Write enable'),
    0x04: ('WRDI', 'Write disable'),
    0x9f: ('RDID', 'Read identification'),
    0x05: ('RDSR', 'Read status register'),
    0x01: ('WRSR', 'Write status register'),
    0x03: ('READ', 'Read data'),
    0x0b: ('FAST/READ', 'Fast read data'),
    0xbb: ('2READ', '2x I/O read'),
    0x20: ('SE', 'Sector erase'),
    0xd8: ('BE', 'Block erase'),
    0x60: ('CE', 'Chip erase'),
    0xc7: ('CE2', 'Chip erase'), # Alternative command ID
    0x02: ('PP', 'Page program'),
    0xad: ('CP', 'Continuously program mode'),
    0xb9: ('DP', 'Deep power down'),
    0xab: ('RDP/RES', 'Release from deep powerdown / Read electronic ID'),
    0x90: ('REMS', 'Read electronic manufacturer & device ID'),
    0xef: ('REMS2', 'Read ID for 2x I/O mode'),
    0xb1: ('ENSO', 'Enter secured OTP'),
    0xc1: ('EXSO', 'Exit secured OTP'),
    0x2b: ('RDSCUR', 'Read security register'),
    0x2f: ('WRSCUR', 'Write security register'),
    0x70: ('ESRY', 'Enable SO to output RY/BY#'),
    0x80: ('DSRY', 'Disable SO to output RY/BY#'),
}

device_name = {
    0x14: 'MX25L1605D',
    0x15: 'MX25L3205D',
    0x16: 'MX25L6405D',
}

def decode_status_reg(data):
    # TODO: Additional per-bit(s) self.put() calls with correct start/end.

    # Bits[0:0]: WIP (write in progress)
    s = 'W' if (data & (1 << 0)) else 'No w'
    ret = '%srite operation in progress.\n' % s

    # Bits[1:1]: WEL (write enable latch)
    s = '' if (data & (1 << 1)) else 'not '
    ret += 'Internal write enable latch is %sset.\n' % s

    # Bits[5:2]: Block protect bits
    # TODO: More detailed decoding (chip-dependent).
    ret += 'Block protection bits (BP3-BP0): 0x%x.\n' % ((data & 0x3c) >> 2)

    # Bits[6:6]: Continuously program mode (CP mode)
    s = '' if (data & (1 << 6)) else 'not '
    ret += 'Device is %sin continuously program mode (CP mode).\n' % s

    # Bits[7:7]: SRWD (status register write disable)
    s = 'not ' if (data & (1 << 7)) else ''
    ret += 'Status register writes are %sallowed.\n' % s

    return ret

class Decoder(srd.Decoder):
    api_version = 1
    id = 'mx25lxx05d'
    name = 'MX25Lxx05D'
    longname = 'Macronix MX25Lxx05D'
    desc = 'SPI (NOR) flash chip protocol.'
    license = 'gplv2+'
    inputs = ['spi', 'logic']
    outputs = ['mx25lxx05d']
    probes = []
    optional_probes = [
        {'id': 'hold', 'name': 'HOLD#', 'desc': 'TODO.'},
        {'id': 'wp_acc', 'name': 'WP#/ACC', 'desc': 'TODO.'},
    ]
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
        ['Verbose decode', 'Decoded register bits, read/write data'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.state = None
        self.cmdstate = 1
        self.addr = 0
        self.data = []

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'mx25lxx05d')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'mx25lxx05d')

    def report(self):
        pass

    def putx(self, data):
        # Simplification, most annotations span exactly one SPI byte/packet.
        self.put(self.ss, self.es, self.out_ann, data)

    def handle_wren(self, mosi, miso):
        self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        self.state = None

    def handle_wrdi(self, mosi, miso):
        pass # TODO

    # TODO: Check/display device ID / name
    def handle_rdid(self, mosi, miso):
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.start_sample = self.ss
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate == 2:
            # Byte 2: Slave sends the JEDEC manufacturer ID.
            self.putx([0, ['Manufacturer ID: 0x%02x' % miso]])
        elif self.cmdstate == 3:
            # Byte 3: Slave sends the memory type (0x20 for this chip).
            self.putx([0, ['Memory type: 0x%02x' % miso]])
        elif self.cmdstate == 4:
            # Byte 4: Slave sends the device ID.
            self.device_id = miso
            self.putx([0, ['Device ID: 0x%02x' % miso]])

        if self.cmdstate == 4:
            # TODO: Check self.device_id is valid & exists in device_names.
            # TODO: Same device ID? Check!
            d = 'Device: Macronix %s' % device_name[self.device_id]
            self.put(self.start_sample, self.es, self.out_ann, [0, [d]])
            self.state = None
        else:
            self.cmdstate += 1

    def handle_rdsr(self, mosi, miso):
        # Read status register: Master asserts CS#, sends RDSR command,
        # reads status register byte. If CS# is kept asserted, the status
        # register can be read continuously / multiple times in a row.
        # When done, the master de-asserts CS# again.
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate >= 2:
            # Bytes 2-x: Slave sends status register as long as master clocks.
            if self.cmdstate <= 3: # TODO: While CS# asserted.
                self.putx([0, ['Status register: 0x%02x' % miso]])
                self.putx([1, [decode_status_reg(miso)]])

            if self.cmdstate == 3: # TODO: If CS# got de-asserted.
                self.state = None
                return

        self.cmdstate += 1

    def handle_wrsr(self, mosi, miso):
        pass # TODO

    def handle_read(self, mosi, miso):
        # Read data bytes: Master asserts CS#, sends READ command, sends
        # 3-byte address, reads >= 1 data bytes, de-asserts CS#.
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate in (2, 3, 4):
            # Bytes 2/3/4: Master sends read address (24bits, MSB-first).
            self.addr |= (mosi << ((4 - self.cmdstate) * 8))
            # self.putx([0, ['Read address, byte %d: 0x%02x' % \
            #                (4 - self.cmdstate, mosi)]])
            if self.cmdstate == 4:
                self.putx([0, ['Read address: 0x%06x' % self.addr]])
                self.addr = 0
        elif self.cmdstate >= 5:
            # Bytes 5-x: Master reads data bytes (until CS# de-asserted).
            # TODO: For now we hardcode 256 bytes per READ command.
            if self.cmdstate <= 256 + 4: # TODO: While CS# asserted.
                self.data.append(miso)
                # self.putx([0, ['New read byte: 0x%02x' % miso]])

            if self.cmdstate == 256 + 4: # TODO: If CS# got de-asserted.
                # s = ', '.join(map(hex, self.data))
                s = ''.join(map(chr, self.data))
                self.putx([0, ['Read data']])
                self.putx([1, ['Read data: %s' % s]])
                self.data = []
                self.state = None
                return

        self.cmdstate += 1

    def handle_fast_read(self, mosi, miso):
        pass # TODO

    def handle_2read(self, mosi, miso):
        pass # TODO

    # TODO: Warn/abort if we don't see the necessary amount of bytes.
    # TODO: Warn if WREN was not seen before.
    def handle_se(self, mosi, miso):
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.addr = 0
            self.start_sample = self.ss
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate in (2, 3, 4):
            # Bytes 2/3/4: Master sends sectror address (24bits, MSB-first).
            self.addr |= (mosi << ((4 - self.cmdstate) * 8))
            # self.putx([0, ['Sector address, byte %d: 0x%02x' % \
            #                (4 - self.cmdstate, mosi)]])

        if self.cmdstate == 4:
            d = 'Erase sector %d (0x%06x)' % (self.addr, self.addr)
            self.put(self.start_sample, self.es, self.out_ann, [0, [d]])
            # TODO: Max. size depends on chip, check that too if possible.
            if self.addr % 4096 != 0:
                # Sector addresses must be 4K-aligned (same for all 3 chips).
                d = 'Warning: Invalid sector address!'
                self.put(self.start_sample, self.es, self.out_ann, [2, [d]])
            self.state = None
        else:
            self.cmdstate += 1

    def handle_be(self, mosi, miso):
        pass # TODO

    def handle_ce(self, mosi, miso):
        pass # TODO

    def handle_ce2(self, mosi, miso):
        pass # TODO

    def handle_pp(self, mosi, miso):
        # Page program: Master asserts CS#, sends PP command, sends 3-byte
        # page address, sends >= 1 data bytes, de-asserts CS#.
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate in (2, 3, 4):
            # Bytes 2/3/4: Master sends page address (24bits, MSB-first).
            self.addr |= (mosi << ((4 - self.cmdstate) * 8))
            # self.putx([0, ['Page address, byte %d: 0x%02x' % \
            #                (4 - self.cmdstate, mosi)]])
            if self.cmdstate == 4:
                self.putx([0, ['Page address: 0x%06x' % self.addr]])
                self.addr = 0
        elif self.cmdstate >= 5:
            # Bytes 5-x: Master sends data bytes (until CS# de-asserted).
            # TODO: For now we hardcode 256 bytes per page / PP command.
            if self.cmdstate <= 256 + 4: # TODO: While CS# asserted.
                self.data.append(mosi)
                # self.putx([0, ['New data byte: 0x%02x' % mosi]])

            if self.cmdstate == 256 + 4: # TODO: If CS# got de-asserted.
                # s = ', '.join(map(hex, self.data))
                s = ''.join(map(chr, self.data))
                self.putx([0, ['Page data']])
                self.putx([1, ['Page data: %s' % s]])
                self.data = []
                self.state = None
                return

        self.cmdstate += 1

    def handle_cp(self, mosi, miso):
        pass # TODO

    def handle_dp(self, mosi, miso):
        pass # TODO

    def handle_rdp_res(self, mosi, miso):
        pass # TODO

    def handle_rems(self, mosi, miso):
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.start_sample = self.ss
            self.putx([0, ['Command: %s' % cmds[self.state][1]]])
        elif self.cmdstate in (2, 3):
            # Bytes 2/3: Master sends two dummy bytes.
            # TODO: Check dummy bytes? Check reply from device?
            self.putx([0, ['Dummy byte: %s' % mosi]])
        elif self.cmdstate == 4:
            # Byte 4: Master sends 0x00 or 0x01.
            # 0x00: Master wants manufacturer ID as first reply byte.
            # 0x01: Master wants device ID as first reply byte.
            self.manufacturer_id_first = True if (mosi == 0x00) else False
            d = 'manufacturer' if (mosi == 0x00) else 'device'
            self.putx([0, ['Master wants %s ID first' % d]])
        elif self.cmdstate == 5:
            # Byte 5: Slave sends manufacturer ID (or device ID).
            self.ids = [miso]
            d = 'Manufacturer' if self.manufacturer_id_first else 'Device'
            self.putx([0, ['%s ID' % d]])
        elif self.cmdstate == 6:
            # Byte 6: Slave sends device ID (or manufacturer ID).
            self.ids.append(miso)
            d = 'Manufacturer' if self.manufacturer_id_first else 'Device'
            self.putx([0, ['%s ID' % d]])

        if self.cmdstate == 6:
            self.end_sample = self.es
            id = self.ids[1] if self.manufacturer_id_first else self.ids[0]
            self.putx([0, ['Device: Macronix %s' % device_name[id]]])
            self.state = None
        else:
            self.cmdstate += 1

    def handle_rems2(self, mosi, miso):
        pass # TODO

    def handle_enso(self, mosi, miso):
        pass # TODO

    def handle_exso(self, mosi, miso):
        pass # TODO

    def handle_rdscur(self, mosi, miso):
        pass # TODO

    def handle_wrscur(self, mosi, miso):
        pass # TODO

    def handle_esry(self, mosi, miso):
        pass # TODO

    def handle_dsry(self, mosi, miso):
        pass # TODO

    def decode(self, ss, es, data):

        ptype, mosi, miso = data

        # if ptype == 'DATA':
        #     self.putx([0, ['MOSI: 0x%02x, MISO: 0x%02x' % (mosi, miso)]])

        # if ptype == 'CS-CHANGE':
        #     if mosi == 1 and miso == 0:
        #         self.putx([0, ['Asserting CS#']])
        #     elif mosi == 0 and miso == 1:
        #         self.putx([0, ['De-asserting CS#']])

        if ptype != 'DATA':
            return

        self.ss, self.es = ss, es

        # If we encountered a known chip command, enter the resp. state.
        if self.state == None:
            self.state = mosi
            self.cmdstate = 1

        # Handle commands.
        if self.state in cmds:
            s = 'handle_%s' % cmds[self.state][0].lower().replace('/', '_')
            handle_reg = getattr(self, s)
            handle_reg(mosi, miso)
        else:
            self.putx([0, ['Unknown command: 0x%02x' % mosi]])
            self.state = None

