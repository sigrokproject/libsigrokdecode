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

# SD card (SPI mode) low-level protocol decoder

import sigrokdecode as srd

cmd_name = {
    # Normal commands (CMD)
    0:  'GO_IDLE_STATE',
    1:  'SEND_OP_COND',
    6:  'SWITCH_FUNC',
    8:  'SEND_IF_COND',
    9:  'SEND_CSD',
    10: 'SEND_CID',
    12: 'STOP_TRANSMISSION',
    13: 'SEND_STATUS',
    16: 'SET_BLOCKLEN',
    17: 'READ_SINGLE_BLOCK',
    18: 'READ_MULTIPLE_BLOCK',
    24: 'WRITE_BLOCK',
    25: 'WRITE_MULTIPLE_BLOCK',
    27: 'PROGRAM_CSD',
    28: 'SET_WRITE_PROT',
    29: 'CLR_WRITE_PROT',
    30: 'SEND_WRITE_PROT',
    32: 'ERASE_WR_BLK_START_ADDR',
    33: 'ERASE_WR_BLK_END_ADDR',
    38: 'ERASE',
    42: 'LOCK_UNLOCK',
    55: 'APP_CMD',
    56: 'GEN_CMD',
    58: 'READ_OCR',
    59: 'CRC_ON_OFF',
    # CMD60-63: Reserved for manufacturer

    # Application-specific commands (ACMD)
    13: 'SD_STATUS',
    18: 'Reserved for SD security applications',
    22: 'SEND_NUM_WR_BLOCKS',
    23: 'SET_WR_BLK_ERASE_COUNT',
    25: 'Reserved for SD security applications',
    26: 'Reserved for SD security applications',
    38: 'Reserved for SD security applications',
    41: 'SD_SEND_OP_COND',
    42: 'SET_CLR_CARD_DETECT',
    43: 'Reserved for SD security applications',
    44: 'Reserved for SD security applications',
    45: 'Reserved for SD security applications',
    46: 'Reserved for SD security applications',
    47: 'Reserved for SD security applications',
    48: 'Reserved for SD security applications',
    49: 'Reserved for SD security applications',
    51: 'SEND_SCR',
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'sdcard_spi'
    name = 'SD card (SPI mode)'
    longname = 'Secure Digital card (SPI mode)'
    desc = 'Secure Digital card (SPI mode) low-level protocol.'
    license = 'gplv2+'
    inputs = ['spi']
    outputs = ['sdcard_spi']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.samplenum = 0
        self.cmd_ss, self.cmd_es = 0, 0
        self.cmd_token = []
        self.is_acmd = False # Indicates CMD vs. ACMD
        self.blocklen = 0
        self.read_buf = []

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'sdcard_spi')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'sdcard_spi')

    def report(self):
        pass

    def putx(self, data):
        self.put(self.cmd_ss, self.cmd_es, self.out_ann, data)

    def handle_command_token(self, mosi, miso):
        # Command tokens (6 bytes) are sent (MSB-first) by the host.
        #
        # Format:
        #  - CMD[47:47]: Start bit (always 0)
        #  - CMD[46:46]: Transmitter bit (1 == host)
        #  - CMD[45:40]: Command index (BCD; valid: 0-63)
        #  - CMD[39:08]: Argument
        #  - CMD[07:01]: CRC7
        #  - CMD[00:00]: End bit (always 1)

        self.cmd_token.append(mosi)
        # TODO: Record MISO too?

        # All command tokens are 6 bytes long.
        if len(self.cmd_token) < 6:
            return

        # Received all 6 bytes of the command token. Now decode it.

        t = self.cmd_token

        # CMD or ACMD?
        s = 'ACMD' if self.is_acmd else 'CMD'
        # TODO
        self.put(0, 0, self.out_ann,
                 [0, [s + ': %02x %02x %02x %02x %02x %02x' % tuple(t)]])

        # Start bit
        self.startbit = (t[0] & (1 << 7)) >> 7
        self.put(0, 0, self.out_ann,
                 [0, ['Start bit: %d' % self.startbit]])
        if self.startbit != 0:
            # TODO
            self.put(0, 0, self.out_ann, [1, ['Warning: Start bit != 0']])

        # Transmitter bit
        self.transmitterbit = (t[0] & (1 << 6)) >> 6
        self.put(0, 0, self.out_ann,
                 [0, ['Transmitter bit: %d' % self.transmitterbit]])
        if self.transmitterbit != 0:
            # TODO
            self.put(0, 0, self.out_ann, [1, ['Warning: Transmitter bit != 1']])

        # Command index
        cmd = self.cmd_index = t[0] & 0x3f
        # TODO
        self.put(0, 0, self.out_ann,
                 [0, ['Command: %s%d (%s)' % (s, cmd, cmd_name[cmd])]])

        # Argument
        self.arg = (t[1] << 24) | (t[2] << 16) | (t[3] << 8) | t[4]
        self.put(0, 0, self.out_ann, [0, ['Argument: 0x%04x' % self.arg]])
        # TODO: Sanity check on argument? Must be per-cmd?

        # CRC
        # TODO: Check CRC.
        self.crc = t[5] >> 1
        self.put(0, 0, self.out_ann, [0, ['CRC: 0x%01x' % self.crc]])

        # End bit
        self.endbit = t[5] & (1 << 0)
        self.put(0, 0, self.out_ann, [0, ['End bit: %d' % self.endbit]])
        if self.endbit != 1:
            # TODO
            self.put(0, 0, self.out_ann, [1, ['Warning: End bit != 1']])

        # Handle command.
        if cmd in (0, 1, 9, 16, 17, 41, 49, 55, 59):
            self.state = 'HANDLE CMD%d' % cmd

        # ...
        if self.is_acmd and cmd != 55:
            self.is_acmd = False

        self.cmd_token = []

    def handle_cmd0(self, ):
        # CMD0: GO_IDLE_STATE
        # TODO
        self.put(0, 0, self.out_ann, [0, ['CMD0: Card reset / idle state']])
        self.state = 'GET RESPONSE R1'

    def handle_cmd1(self):
        # CMD1: SEND_OP_COND
        # TODO
        hcs = (self.arg & (1 << 30)) >> 30
        self.put(0, 0, self.out_ann, [0, ['HCS bit = %d' % hcs]])
        self.state = 'GET RESPONSE R1'

    def handle_cmd9(self):
        # CMD9: SEND_CSD (128 bits / 16 bytes)
        self.read_buf.append(self.miso)
        # FIXME
        ### if len(self.read_buf) < 16:
        if len(self.read_buf) < 16 + 4:
            return
        self.read_buf = self.read_buf[4:] ### TODO: Document or redo.
        self.put(0, 0, self.out_ann, [0, ['CSD: %s' % self.read_buf]])
        # TODO: Decode all bits.
        self.read_buf = []
        ### self.state = 'GET RESPONSE R1'
        self.state = 'IDLE'

    def handle_cmd10(self):
        # CMD10: SEND_CID (128 bits / 16 bytes)
        self.read_buf.append(self.miso)
        if len(self.read_buf) < 16:
            return
        self.put(0, 0, self.out_ann, [0, ['CID: %s' % self.read_buf]])
        # TODO: Decode all bits.
        self.read_buf = []
        self.state = 'GET RESPONSE R1'

    def handle_cmd16(self):
        # CMD16: SET_BLOCKLEN
        self.blocklen = self.arg # TODO
        # TODO: Sanity check on block length.
        self.put(0, 0, self.out_ann, [0, ['Block length: %d' % self.blocklen]])
        self.state = 'GET RESPONSE R1'

    def handle_cmd17(self):
        # CMD17: READ_SINGLE_BLOCK
        self.read_buf.append(self.miso)
        if len(self.read_buf) == 1:
            self.put(0, 0, self.out_ann,
                     [0, ['Read block at address: 0x%04x' % self.arg]])
        if len(self.read_buf) < self.blocklen + 2: # FIXME
            return
        self.read_buf = self.read_buf[2:] # FIXME
        self.put(0, 0, self.out_ann, [0, ['Block data: %s' % self.read_buf]])
        self.read_buf = []
        self.state = 'GET RESPONSE R1'

    def handle_cmd41(self):
        # ACMD41: SD_SEND_OP_COND
        self.state = 'GET RESPONSE R1'

    def handle_cmd49(self):
        self.state = 'GET RESPONSE R1'

    def handle_cmd55(self):
        # CMD55: APP_CMD
        self.is_acmd = True
        self.state = 'GET RESPONSE R1'

    def handle_cmd59(self):
        # CMD59: CRC_ON_OFF
        crc_on_off = self.arg & (1 << 0)
        s = 'on' if crc_on_off == 1 else 'off'
        self.put(0, 0, self.out_ann, [0, ['SD card CRC option: %s' % s]])
        self.state = 'GET RESPONSE R1'

    def handle_cid_register(self):
        # Card Identification (CID) register, 128bits

        cid = self.cid

        # Manufacturer ID: CID[127:120] (8 bits)
        mid = cid[15]

        # OEM/Application ID: CID[119:104] (16 bits)
        oid = (cid[14] << 8) | cid[13]

        # Product name: CID[103:64] (40 bits)
        pnm = 0
        for i in range(12, 8 - 1, -1):
            pnm <<= 8
            pnm |= cid[i]

        # Product revision: CID[63:56] (8 bits)
        prv = cid[7]

        # Product serial number: CID[55:24] (32 bits)
        psn = 0
        for i in range(6, 3 - 1, -1):
            psn <<= 8
            psn |= cid[i]

        # RESERVED: CID[23:20] (4 bits)

        # Manufacturing date: CID[19:8] (12 bits)
        # TODO

        # CRC7 checksum: CID[7:1] (7 bits)
        # TODO

        # Not used, always 1: CID[0:0] (1 bit)
        # TODO

    def handle_response_r1(self, res):
        # The R1 response token format (1 byte).
        # Sent by the card after every command except for SEND_STATUS.

        self.put(0, 0, self.out_ann, [0, ['R1: 0x%02x' % res]])

        # TODO: Configurable whether all bits are decoded.

        # 'In idle state' bit
        s = '' if (res & (1 << 0)) else 'not '
        self.put(0, 0, self.out_ann, [0, ['Card is %sin idle state' % s]])

        # 'Erase reset' bit
        s = '' if (res & (1 << 1)) else 'not '
        self.put(0, 0, self.out_ann, [0, ['Erase sequence %scleared' % s]])

        # 'Illegal command' bit
        s = 'I' if (res & (1 << 2)) else 'No i'
        self.put(0, 0, self.out_ann, [0, ['%sllegal command detected' % s]])

        # 'Communication CRC error' bit
        s = 'failed' if (res & (1 << 3)) else 'was successful'
        self.put(0, 0, self.out_ann,
                 [0, ['CRC check of last command %s' % s]])

        # 'Erase sequence error' bit
        s = 'E' if (res & (1 << 4)) else 'No e'
        self.put(0, 0, self.out_ann,
                 [0, ['%srror in the sequence of erase commands' % s]])

        # 'Address error' bit
        s = 'M' if (res & (1 << 4)) else 'No m'
        self.put(0, 0, self.out_ann,
                 [0, ['%sisaligned address used in command' % s]])

        # 'Parameter error' bit
        s = '' if (res & (1 << 4)) else 'not '
        self.put(0, 0, self.out_ann,
                 [0, ['Command argument %soutside allowed range' % s]])

        self.state = 'IDLE'

    def handle_response_r1b(self, res):
        # TODO
        pass

    def handle_response_r2(self, res):
        # TODO
        pass

    def handle_response_r3(self, res):
        # TODO
        pass

    # Note: Response token formats R4 and R5 are reserved for SDIO.

    # TODO: R6?

    def handle_response_r7(self, res):
        # TODO
        pass

    def decode(self, ss, es, data):
        ptype, mosi, miso = data

        # For now, ignore non-data packets.
        if ptype != 'DATA':
            return

        self.put(0, 0, self.out_ann, [0, ['0x%02x 0x%02x' % (mosi, miso)]])

        # State machine.
        if self.state == 'IDLE':
            # Ignore stray 0xff bytes, some devices seem to send those!?
            if mosi == 0xff: # TODO?
                return
            self.state = 'GET COMMAND TOKEN'
            self.handle_command_token(mosi, miso)
        elif self.state == 'GET COMMAND TOKEN':
            self.handle_command_token(mosi, miso)
        elif self.state.startswith('HANDLE CMD'):
            self.miso, self.mosi = miso, mosi
            # Call the respective handler method for the command.
            s = 'handle_cmd%s' % self.state[10:].lower()
            handle_cmd = getattr(self, s)
            handle_cmd()
        elif self.state.startswith('GET RESPONSE'):
            # Ignore stray 0xff bytes, some devices seem to send those!?
            if miso == 0xff: # TODO?
                return

            # Call the respective handler method for the response.
            s = 'handle_response_%s' % self.state[13:].lower()
            # self.put(0, 0, self.out_ann, [0, [s]]) # TODO
            handle_response = getattr(self, s)
            handle_response(miso)

            self.state = 'IDLE'
        else:
            raise Exception('Invalid state: %s' % self.state)

