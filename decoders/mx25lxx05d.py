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
# Macronix MX25Lxx05D SPI (NOR) flash chip decoder.
# Works for MX25L1605D/MX25L3205D/MX25L6405D.
#

#
# TODO: Description
#
# Details:
# http://www.macronix.com/QuickPlace/hq/PageLibrary4825740B00298A3B.nsf/h_Index/3F21BAC2E121E17848257639003A3146/$File/MX25L1605D-3205D-6405D-1.5.pdf
#

import sigrokdecode as srd

# States
IDLE = -1

# Chip commands (also used as additional decoder states).
CMD_WREN      = 0x06
CMD_WRDI      = 0x04
CMD_RDID      = 0x9f
CMD_RDSR      = 0x05
CMD_WRSR      = 0x01
CMD_READ      = 0x03
CMD_FAST_READ = 0x0b
CMD_2READ     = 0xbb
CMD_SE        = 0x20
CMD_BE        = 0xd8
CMD_CE        = 0x60
CMD_CE2       = 0xc7
CMD_PP        = 0x02
CMD_CP        = 0xad
CMD_DP        = 0xb9
# CMD_RDP       = 0xab
# CMD_RES       = 0xab
CMD_RDP_RES   = 0xab # Note: RDP/RES have the same ID.
CMD_REMS      = 0x90
CMD_REMS2     = 0xef
CMD_ENSO      = 0xb1
CMD_EXSO      = 0xc1
CMD_RDSCUR    = 0x2b
CMD_WRSCUR    = 0x2f
CMD_ESRY      = 0x70
CMD_DSRY      = 0x80

# TODO: (Short) command names as strings in a dict, too?

# Dict which maps command IDs to their description.
cmds = {
    CMD_WREN: 'Write enable',
    CMD_WRDI: 'Write disable',
    CMD_RDID: 'Read identification',
    CMD_RDSR: 'Read status register',
    CMD_WRSR: 'Write status register',
    CMD_READ: 'Read data',
    CMD_FAST_READ: 'Fast read data',
    CMD_2READ: '2x I/O read',
    CMD_SE: 'Sector erase',
    CMD_BE: 'Block erase',
    CMD_CE: 'Chip erase',
    CMD_CE2: 'Chip erase', # Alternative command ID
    CMD_PP: 'Page program',
    CMD_CP: 'Continuously program mode',
    CMD_DP: 'Deep power down',
    # CMD_RDP: 'Release from deep powerdown',
    # CMD_RES: 'Read electronic ID',
    CMD_RDP_RES: 'Release from deep powerdown / Read electronic ID',
    CMD_REMS: 'Read electronic manufacturer & device ID',
    CMD_REMS2: 'Read ID for 2x I/O mode',
    CMD_ENSO: 'Enter secured OTP',
    CMD_EXSO: 'Exit secured OTP',
    CMD_RDSCUR: 'Read security register',
    CMD_WRSCUR: 'Write security register',
    CMD_ESRY: 'Enable SO to output RY/BY#',
    CMD_DSRY: 'Disable SO to output RY/BY#',
}

device_name = {
    0x14: 'MX25L1605D',
    0x15: 'MX25L3205D',
    0x16: 'MX25L6405D',
}

# FIXME: This is just some example input for testing purposes...

mosi_packets = [
    # REMS
    {'type': 'D',  'range': (100, 110), 'data': 0x90, 'ann': ''},
    {'type': 'D',  'range': (120, 130), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (170, 180), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (190, 200), 'data': 0x00, 'ann': ''},
    {'type': 'D',  'range': (400, 410), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (411, 421), 'data': 0xff, 'ann': ''},
    # RDID
    {'type': 'D',  'range': (10, 11), 'data': 0x9f, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    # SE
    {'type': 'D',  'range': (10, 11), 'data': 0x20, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x12, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x34, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x56, 'ann': ''},
    # SE
    {'type': 'D',  'range': (10, 11), 'data': 0x20, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x44, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x55, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x66, 'ann': ''},
    # WREN
    {'type': 'D',  'range': (10, 11), 'data': 0x06, 'ann': ''},
]

miso_packets = [
    # REMS
    {'type': 'D',  'range': (100, 110), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (120, 130), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (170, 180), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (190, 200), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (400, 410), 'data': 0xc2, 'ann': ''},
    {'type': 'D',  'range': (411, 421), 'data': 0x14, 'ann': ''},
    # RDID
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xc2, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x20, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0x15, 'ann': ''},
    # SE
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    # SE
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
    # WREN
    {'type': 'D',  'range': (10, 11), 'data': 0xff, 'ann': ''},
]

class Decoder(srd.Decoder):
    id = 'mx25lxx05d'
    name = 'MX25Lxx05D'
    longname = 'Macronix MX25Lxx05D SPI flash chip decoder'
    desc = 'Macronix MX25Lxx05D SPI flash chip decoder'
    longdesc = 'TODO'
    author = 'Uwe Hermann'
    email = 'uwe@hermann-uwe.de'
    license = 'gplv2+'
    inputs = ['spi', 'spi', 'logic']
    outputs = ['mx25lxx05d']
    probes = [] # TODO: HOLD#, WP#/ACC
    options = {} # TODO
    annotations = []

    def __init__(self, **kwargs):
        self.state = IDLE
        self.cmdstate = 1 # TODO
        self.out = []

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'mx25lxx05d')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'mx25lxx05d')

    def report(self):
        pass

    def handle_wren(self, miso_packet, mosi_packet):
        self.out += [{'type': self.cmd, 'range': mosi_packet['range'],
                      'data': None, 'ann': cmds[self.state]}]
        self.state = IDLE

    # TODO: Check/display device ID / name
    def handle_rdid(self, miso_packet, mosi_packet):
        ## self.state = IDLE
        ## return # FIXME

        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.start_sample = mosi_packet['range'][0]
            o = [] # TODO
        elif self.cmdstate == 2:
            # Byte 2: Slave sends the JEDEC manufacturer ID.
            o = [{'type': self.cmd, 'range': miso_packet['range'],
                  'data': miso_packet['data'], 'ann': 'Manufacturer ID'}]
        elif self.cmdstate == 3:
            # Byte 3: Slave sends the memory type (0x20 for this chip).
            o = [{'type': self.cmd, 'range': miso_packet['range'],
                  'data': miso_packet['data'], 'ann': 'Memory type'}]
        elif self.cmdstate == 4:
            # Byte 4: Slave sends the device ID.
            self.device_id = miso_packet['data']
            o = [{'type': self.cmd, 'range': miso_packet['range'],
                  'data': miso_packet['data'], 'ann': 'Device ID'}]

        if self.cmdstate == 4:
            # TODO: Check self.device_id is valid & exists in device_names.
            # TODO: Same device ID? Check!
            dev = 'Device: Macronix %s' % device_name[self.device_id]
            o += [{'type': 'RDID', # TODO: self.cmd?
                   'range': (self.start_sample, miso_packet['range'][1]),
                   'data': None, # TODO?
                   'ann': dev}]
            self.state = IDLE
        else:
            self.cmdstate += 1

        self.out += o

    # TODO: Warn/abort if we don't see the necessary amount of bytes.
    # TODO: Warn if WREN was not seen before.
    def handle_se(self, miso_packet, mosi_packet):
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.addr = 0
            self.start_sample = mosi_packet['range'][0]
            o = [{'type': self.cmd, 'range': mosi_packet['range'],
                  'data': self.cmd, 'ann': 'Command ID'}]
        elif self.cmdstate in (2, 3, 4):
            # Bytes 2/3/4: Master sends address of the sector to erase.
            # Note: Assumes SPI data is 8 bits wide (it is for MX25Lxx05D).
            # TODO: LSB-first of MSB-first?
            self.addr <<= 8
            self.addr |= mosi_packet['data']
            o = [] # TODO: Output 'Address byte 1' and such fields?

        if self.cmdstate == 4:
            o += [{'type': self.cmd,
                   'range': (self.start_sample, mosi_packet['range'][1]),
                   'data': '0x%x' % self.addr, 'ann': cmds[self.state]}]
            # TODO: Max. size depends on chip, check that too if possible.
            if self.addr % 4096 != 0:
                # Sector addresses must be 4K-aligned (same for all 3 chips).
                o += [{'type': self.cmd, # TODO: Type == 'Warning' or such?
                       'range': (self.start_sample, mosi_packet['range'][1]),
                       'data': None, 'ann': 'Warning: Invalid sector address!'}]
            self.state = IDLE
        else:
            self.cmdstate += 1

        self.out += o

    def handle_rems(self, miso_packet, mosi_packet):
        if self.cmdstate == 1:
            # Byte 1: Master sends command ID.
            self.start_sample = mosi_packet['range'][0]
            o = [{'type': self.cmd, 'range': mosi_packet['range'],
                  'data': self.cmd, 'ann': 'Command ID'}]
        elif self.cmdstate in (2, 3):
            # Bytes 2/3: Master sends two dummy bytes.
            # TODO: Check dummy bytes? Check reply from device?
            o = [{'type': self.cmd, 'range': mosi_packet['range'],
                  'data': mosi_packet['data'], 'ann': 'Dummy byte'}]
        elif self.cmdstate == 4:
            # Byte 4: Master sends 0x00 or 0x01.
            # 0x00: Master wants manufacturer ID as first reply byte.
            # 0x01: Master wants device ID as first reply byte.
            b = mosi_packet['data']
            self.manufacturer_id_first = True if (b == 0x00) else False
            d = 'manufacturer' if (b == 0x00) else 'device'
            o = [{'type': self.cmd, 'range': mosi_packet['range'],
                  'data': b, 'ann': '%s (%s ID first)' % (cmds[self.cmd], d)}]
        elif self.cmdstate == 5:
            # Byte 5: Slave sends manufacturer ID (or device ID).
            self.ids = [miso_packet['data']]
            o = []
        elif self.cmdstate in (5, 6):
            # Byte 6: Slave sends device ID (or manufacturer ID).
            self.ids += [miso_packet['data']]
            ann = 'Manufacturer' if self.manufacturer_id_first else 'Device'
            o = [{'type': self.cmd, 'range': miso_packet['range'],
                  'data': '0x%02x' % self.ids[0], 'ann': ann}]
            ann = 'Device' if self.manufacturer_id_first else 'Manufacturer'
            o += [{'type': self.cmd, 'range': miso_packet['range'],
                   'data': '0x%02x' % self.ids[1], 'ann': '%s ID' % ann}]
        else:
            # TODO: Error?
            pass

        if self.cmdstate == 6:
            self.end_sample = miso_packet['range'][1]
            id = self.ids[1] if self.manufacturer_id_first else self.ids[0]
            dev = 'Device: Macronix %s' % device_name[id]
            o += [{'type': self.cmd,
                   'range': (self.start_sample, self.end_sample),
                   'data': None, # TODO: Both IDs? Which format?
                   'ann': dev}]
            self.state = IDLE
        else:
            self.cmdstate += 1

        self.out += o

    def decode(self, ss, es, data):
        self.out = []

        # Iterate over all SPI MISO/MOSI packets. TODO: HOLD#, WP#/ACC?
        for i in range(len(miso_packets)):

            p_miso = miso_packets[i]
            p_mosi = mosi_packets[i]

            # Assumption: Every p_miso has a p_mosi entry with same range.

            # For now, skip non-data packets.
            if p_mosi['type'] != 'D':
                continue

            cmd = p_mosi['data']

            # If we encountered a known chip command, enter the resp. state.
            if self.state == IDLE:
                if cmd in cmds:
                    self.state = cmd
                    self.cmd = cmd # TODO: Eliminate?
                    self.cmdstate = 1
                else:
                    pass # TODO

            # Handle commands.
            # TODO: Use some generic way to invoke the resp. method.
            if self.state == CMD_WREN:
                self.handle_wren(p_miso, p_mosi)
            elif self.state == CMD_SE:
                self.handle_se(p_miso, p_mosi)
            elif self.state == CMD_RDID:
                self.handle_rdid(p_miso, p_mosi)
            if self.state == CMD_REMS:
                self.handle_rems(p_miso, p_mosi)
            else:
                pass

        if self.out != []:
            # self.put(0, 0, self.out_proto, out_proto)
            self.put(0, 0, self.out_ann, self.out)

