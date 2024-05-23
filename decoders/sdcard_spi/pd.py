##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2020 Uwe Hermann <uwe@hermann-uwe.de>
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

import sigrokdecode as srd
from common.srdhelper import SrdIntEnum
from common.sdcard import (cmd_names, acmd_names)

responses = '1 1b 2 3 7'.split()

a = ['CMD%d' % i for i in range(64)] + ['ACMD%d' % i for i in range(64)] + \
    ['R' + r.upper() for r in responses] + ['BIT', 'BIT_WARNING']
Ann = SrdIntEnum.from_list('Ann', a)

# CRC16 (CCITT) with an initial XOR set to 0x0
def crc16(data: bytes):
    table = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
    ]
    crc = 0
    for byte in data:
        crc = ( (crc << 8) ^ table[(crc >> 8) ^ byte] ) & 0xffff
    return crc

class Decoder(srd.Decoder):
    api_version = 3
    id = 'sdcard_spi'
    name = 'SD card (SPI mode)'
    longname = 'Secure Digital card (SPI mode)'
    desc = 'Secure Digital card (SPI mode) low-level protocol.'
    license = 'gplv2+'
    inputs = ['spi']
    outputs = []
    tags = ['Memory']
    annotations = \
        tuple(('cmd%d' % i, 'CMD%d' % i) for i in range(64)) + \
        tuple(('acmd%d' % i, 'ACMD%d' % i) for i in range(64)) + \
        tuple(('r%s' % r, 'R%s response' % r) for r in responses) + ( \
        ('bit', 'Bit'),
        ('bit-warning', 'Bit warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (Ann.BIT, Ann.BIT_WARNING)),
        ('commands-replies', 'Commands/replies', Ann.prefixes('CMD ACMD R')),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'IDLE'
        self.ss, self.es = 0, 0
        self.ss_bit, self.es_bit = 0, 0
        self.ss_cmd, self.es_cmd = 0, 0
        self.ss_busy, self.es_busy = 0, 0
        self.cmd_token = []
        self.cmd_token_bits = []
        self.is_acmd = False # Indicates CMD vs. ACMD
        self.blocklen = 0
        self.read_buf = []
        self.cmd_str = ''
        self.is_cmd24 = False
        self.cmd24_start_token_found = False
        self.is_cmd17 = False
        self.cmd17_start_token_found = False
        self.is_cmd18 = False
        self.cmd18_start_token_found = False
        self.busy_first_byte = False

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, data):
        self.put(self.ss_cmd, self.es_cmd, self.out_ann, data)

    def putc(self, cmd, desc):
        self.putx([cmd, ['%s: %s' % (self.cmd_str, desc)]])

    def putb(self, data):
        self.put(self.ss_bit, self.es_bit, self.out_ann, data)

    def cmd_name(self, cmd):
        c = acmd_names if self.is_acmd else cmd_names
        s = c.get(cmd, 'Unknown')
        # SD mode names for CMD32/33: ERASE_WR_BLK_{START,END}.
        # SPI mode names for CMD32/33: ERASE_WR_BLK_{START,END}_ADDR.
        if cmd in (32, 33):
            s += '_ADDR'
        return s

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

        if len(self.cmd_token) == 0:
            self.ss_cmd = self.ss

        self.cmd_token.append(mosi)
        self.cmd_token_bits.append(self.mosi_bits)

        # All command tokens are 6 bytes long.
        if len(self.cmd_token) < 6:
            return

        self.es_cmd = self.es

        t = self.cmd_token

        # CMD or ACMD?
        s = 'ACMD' if self.is_acmd else 'CMD'

        def tb(byte, bit):
            return self.cmd_token_bits[5 - byte][bit]

        # Bits[47:47]: Start bit (always 0)
        bit, self.ss_bit, self.es_bit = tb(5, 7)[0], tb(5, 7)[1], tb(5, 7)[2]
        if bit == 0:
            self.putb([Ann.BIT, ['Start bit: %d' % bit]])
        else:
            self.putb([Ann.BIT_WARNING, ['Start bit: %s (Warning: Must be 0!)' % bit]])

        # Bits[46:46]: Transmitter bit (1 == host)
        bit, self.ss_bit, self.es_bit = tb(5, 6)[0], tb(5, 6)[1], tb(5, 6)[2]
        if bit == 1:
            self.putb([Ann.BIT, ['Transmitter bit: %d' % bit]])
        else:
            self.putb([Ann.BIT_WARNING, ['Transmitter bit: %d (Warning: Must be 1!)' % bit]])

        # Bits[45:40]: Command index (BCD; valid: 0-63)
        cmd = self.cmd_index = t[0] & 0x3f
        self.ss_bit, self.es_bit = tb(5, 5)[1], tb(5, 0)[2]
        self.putb([Ann.BIT, ['Command: %s%d (%s)' % (s, cmd, self.cmd_name(cmd))]])

        # Bits[39:8]: Argument
        self.arg = (t[1] << 24) | (t[2] << 16) | (t[3] << 8) | t[4]
        self.ss_bit, self.es_bit = tb(4, 7)[1], tb(1, 0)[2]
        self.putb([Ann.BIT, ['Argument: 0x%04x' % self.arg]])

        # Bits[7:1]: CRC7
        # TODO: Check CRC7.
        crc = t[5] >> 1
        self.ss_bit, self.es_bit = tb(0, 7)[1], tb(0, 1)[2]
        self.putb([Ann.BIT, ['CRC7: 0x%01x' % crc]])

        # Bits[0:0]: End bit (always 1)
        bit, self.ss_bit, self.es_bit = tb(0, 0)[0], tb(0, 0)[1], tb(0, 0)[2]
        if bit == 1:
            self.putb([Ann.BIT, ['End bit: %d' % bit]])
        else:
            self.putb([Ann.BIT_WARNING, ['End bit: %d (Warning: Must be 1!)' % bit]])

        # Handle command.
        if cmd in (0, 1, 9, 12, 16, 17, 18, 24, 41, 49, 55, 59):
            self.state = 'HANDLE CMD%d' % cmd
            self.cmd_str = '%s%d (%s)' % (s, cmd, self.cmd_name(cmd))
        else:
            self.state = 'HANDLE CMD999'
            a = '%s%d: %02x %02x %02x %02x %02x %02x' % ((s, cmd) + tuple(t))
            self.putx([cmd, [a]])

    def handle_cmd0(self):
        # CMD0: GO_IDLE_STATE
        self.putc(Ann.CMD0, 'Reset the SD card')
        self.state = 'GET RESPONSE R1'

    def handle_cmd1(self):
        # CMD1: SEND_OP_COND
        self.putc(Ann.CMD1, 'Send HCS info and activate the card init process')
        hcs = (self.arg & (1 << 30)) >> 30
        self.ss_bit = self.cmd_token_bits[5 - 4][6][1]
        self.es_bit = self.cmd_token_bits[5 - 4][6][2]
        self.putb([Ann.BIT, ['HCS: %d' % hcs]])
        self.state = 'GET RESPONSE R1'

    def handle_cmd9(self):
        # CMD9: SEND_CSD (128 bits / 16 bytes)
        self.putc(Ann.CMD9, 'Ask card to send its card specific data (CSD)')
        if len(self.read_buf) == 0:
            self.ss_cmd = self.ss
        self.read_buf.append(self.miso)
        # FIXME
        ### if len(self.read_buf) < 16:
        if len(self.read_buf) < 16 + 4:
            return
        self.es_cmd = self.es
        self.read_buf = self.read_buf[4:] # TODO: Document or redo.
        self.putx([Ann.CMD9, ['CSD: %s' % self.read_buf]])
        # TODO: Decode all bits.
        self.read_buf = []
        ### self.state = 'GET RESPONSE R1'
        self.state = 'IDLE'

    def handle_cmd10(self):
        # CMD10: SEND_CID (128 bits / 16 bytes)
        self.putc(Ann.CMD10, 'Ask card to send its card identification (CID)')
        self.read_buf.append(self.miso)
        if len(self.read_buf) < 16:
            return
        self.putx([Ann.CMD10, ['CID: %s' % self.read_buf]])
        # TODO: Decode all bits.
        self.read_buf = []
        self.state = 'GET RESPONSE R1'

    def handle_cmd12(self):
        # CMD12: STOP_TRANSMISSION
        self.putc(Ann.CMD12, 'End current multi block transfer')
        self.read_buf = []
        self.cmd18_start_token_found = False
        self.is_cmd18 = False
        self.state = 'GET RESPONSE R1'

    def handle_cmd16(self):
        # CMD16: SET_BLOCKLEN
        self.blocklen = self.arg
        # TODO: Sanity check on block length.
        self.putc(Ann.CMD16, 'Set the block length to %d bytes' % self.blocklen)
        self.state = 'GET RESPONSE R1'

    def handle_cmd17(self):
        # CMD17: READ_SINGLE_BLOCK
        self.putc(Ann.CMD17, 'Read a block from address 0x%04x' % self.arg)
        self.is_cmd17 = True
        self.state = 'GET RESPONSE R1'

    def handle_cmd18(self):
        # CMD18: READ_MULTIPLE_BLOCK
        self.putc(Ann.CMD18, 'Read multiple blocks from address 0x%04x' % self.arg)
        self.is_cmd18 = True
        self.state = 'GET RESPONSE R1'

    def handle_cmd24(self):
        # CMD24: WRITE_BLOCK
        self.putc(Ann.CMD24, 'Write a block to address 0x%04x' % self.arg)
        self.is_cmd24 = True
        self.state = 'GET RESPONSE R1'

    def handle_cmd49(self):
        self.state = 'GET RESPONSE R1'

    def handle_cmd55(self):
        # CMD55: APP_CMD
        self.putc(Ann.CMD55, 'Next command is an application-specific command')
        self.is_acmd = True
        self.state = 'GET RESPONSE R1'

    def handle_cmd59(self):
        # CMD59: CRC_ON_OFF
        crc_on_off = self.arg & (1 << 0)
        s = 'on' if crc_on_off == 1 else 'off'
        self.putc(Ann.CMD59, 'Turn the SD card CRC option %s' % s)
        self.state = 'GET RESPONSE R1'

    def handle_acmd41(self):
        # ACMD41: SD_SEND_OP_COND
        self.putc(Ann.ACMD41, 'Send HCS info and activate the card init process')
        self.state = 'GET RESPONSE R1'

    def handle_cmd999(self):
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

        self.ss_cmd, self.es_cmd = self.miso_bits[7][1], self.miso_bits[0][2]
        self.putx([Ann.R1, ['R1: 0x%02x' % res]])

        def putbit(bit, data):
            b = self.miso_bits[bit]
            self.ss_bit, self.es_bit = b[1], b[2]
            self.putb([Ann.BIT, data])

        # Bit 0: 'In idle state' bit
        s = '' if (res & (1 << 0)) else 'not '
        putbit(0, ['Card is %sin idle state' % s])

        # Bit 1: 'Erase reset' bit
        s = '' if (res & (1 << 1)) else 'not '
        putbit(1, ['Erase sequence %scleared' % s])

        # Bit 2: 'Illegal command' bit
        s = 'I' if (res & (1 << 2)) else 'No i'
        putbit(2, ['%sllegal command detected' % s])

        # Bit 3: 'Communication CRC error' bit
        s = 'failed' if (res & (1 << 3)) else 'was successful'
        putbit(3, ['CRC check of last command %s' % s])

        # Bit 4: 'Erase sequence error' bit
        s = 'E' if (res & (1 << 4)) else 'No e'
        putbit(4, ['%srror in the sequence of erase commands' % s])

        # Bit 5: 'Address error' bit
        s = 'M' if (res & (1 << 4)) else 'No m'
        putbit(5, ['%sisaligned address used in command' % s])

        # Bit 6: 'Parameter error' bit
        s = '' if (res & (1 << 4)) else 'not '
        putbit(6, ['Command argument %soutside allowed range' % s])

        # Bit 7: Always set to 0
        putbit(7, ['Bit 7 (always 0)'])

        if self.is_cmd17:
            self.state = 'HANDLE DATA BLOCK CMD17'
        elif self.is_cmd18:
            self.state = 'HANDLE DATA BLOCK CMD18'
        elif self.is_cmd24:
            self.state = 'HANDLE DATA BLOCK CMD24'

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

    def handle_data_cmd17(self, miso):
        # CMD17 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then self.blocklen bytes of data, then always
        # 2 bytes of CRC.
        if self.cmd17_start_token_found:
            if len(self.read_buf) == 0:
                self.ss_data = self.ss
                if not self.blocklen:
                    # Assume a fixed block size when inspection of the previous
                    # traffic did not provide the respective parameter value.
                    # TODO: Make the default block size a PD option?
                    self.blocklen = 512
            self.read_buf.append(miso)
            # Wait until block transfer completed.
            if len(self.read_buf) < self.blocklen:
                return
            if len(self.read_buf) == self.blocklen:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD17, ['Block data: %s' % self.read_buf]])
            elif len(self.read_buf) == (self.blocklen + 1):
                self.ss_crc = self.ss
            elif len(self.read_buf) == (self.blocklen + 2):
                self.es_crc = self.es
                block_crc = (self.read_buf[self.blocklen]<<8) | self.read_buf[self.blocklen+1]
                comp_crc = crc16(self.read_buf[:self.blocklen])
                if block_crc == comp_crc:
                  msg = "0x%04x (valid)" % block_crc
                else:
                  msg = "0x%04x (Warning: invalid -- expected: 0x%04x)" % (block_crc, comp_crc)
                self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD17, ['CRC16: %s' % (msg)]])
                self.state = 'IDLE'
                self.read_buf = []
                self.cmd17_start_token_found = False
                self.is_cmd17 = False
        elif miso == 0xfe:
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD17, ['Start Block']])
            self.cmd17_start_token_found = True

    def handle_data_cmd18(self, mosi, miso):
        # CMD18 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then [ self.blocklen bytes of data, then always
        # 2 bytes of CRC. ] multiple times until a CMD12 is sent by the master.
        if self.cmd18_start_token_found:
            if len(self.read_buf) == 0:
                self.ss_data = self.ss
                if not self.blocklen:
                    # Assume a fixed block size when inspection of the previous
                    # traffic did not provide the respective parameter value.
                    # TODO: Make the default block size a PD option?
                    self.blocklen = 512
            self.read_buf.append(miso)
            # Wait until block transfer completed.
            if len(self.read_buf) < self.blocklen:
                pass
            elif len(self.read_buf) == self.blocklen:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD18, ['Block data: %s' % self.read_buf]])
            elif len(self.read_buf) == (self.blocklen + 1):
                self.ss_crc = self.ss
            elif len(self.read_buf) == (self.blocklen + 2):
                self.es_crc = self.es
                block_crc = (self.read_buf[self.blocklen]<<8) | self.read_buf[self.blocklen+1]
                comp_crc = crc16(self.read_buf[:self.blocklen])
                if block_crc == comp_crc:
                  msg = "0x%04x (valid)" % block_crc
                else:
                  msg = "0x%04x (Warning: invalid -- expected: 0x%04x)" % (block_crc, comp_crc)
                self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD18, ['CRC16: %s' % (msg)]])
                self.read_buf = []
                self.cmd18_start_token_found = False
        elif miso == 0xfe:
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD18, ['Start Block']])
            self.cmd18_start_token_found = True
        elif miso != 0xff:
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD18, ['Warning: unexpected byte on MISO line: 0x%x (should be either 0xff or 0xfe).' % miso]])
            self.state = 'IDLE'
            self.read_buf = []
            self.cmd18_start_token_found = False
            self.is_cmd18 = False

        if mosi != 0xff:
          self.handle_command_token(mosi, miso)
          if self.state.startswith('HANDLE CMD'):
            # master has sent a new command
            if self.state != 'HANDLE CMD12':
              self.put(self.ss, self.es, self.out_ann, [Ann.CMD18, ['Warning: unexpected command on MISO line in the middle of a transfer (state: %s).' % self.state]])
              self.read_buf = []
              self.cmd18_start_token_found = False
              self.is_cmd18 = False

    def handle_data_cmd24(self, mosi):
        if self.cmd24_start_token_found:
            if len(self.read_buf) == 0:
                self.ss_data = self.ss
                if not self.blocklen:
                    # Assume a fixed block size when inspection of the
                    # previous traffic did not provide the respective
                    # parameter value.
                    # TODO Make the default block size a user adjustable option?
                    self.blocklen = 512
            self.read_buf.append(mosi)
            # Wait until block transfer completed.
            if len(self.read_buf) < self.blocklen:
                return
            self.es_data = self.es
            self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD24, ['Block data: %s' % self.read_buf]])
            self.read_buf = []
            self.cmd24_start_token_found = False
            self.is_cmd24 = False
            self.state = 'DATA RESPONSE'
        elif mosi == 0xfe:
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD24, ['Start Block']])
            self.cmd24_start_token_found = True

    def handle_data_response(self, miso):
        # Data Response token (1 byte).
        #
        # Format:
        #  - Bits[7:5]: Don't care.
        #  - Bits[4:4]: Always 0.
        #  - Bits[3:1]: Status.
        #    - 010: Data accepted.
        #    - 101: Data rejected due to a CRC error.
        #    - 110: Data rejected due to a write error.
        #  - Bits[0:0]: Always 1.
        miso &= 0x1f
        if miso & 0x11 != 0x01:
            # This is not the byte we are waiting for.
            # Should we return to IDLE here?
            return
        m = self.miso_bits
        self.put(m[7][1], m[5][2], self.out_ann, [Ann.BIT, ['Don\'t care']])
        self.put(m[4][1], m[4][2], self.out_ann, [Ann.BIT, ['Always 0']])
        if miso == 0x05:
            self.put(m[3][1], m[1][2], self.out_ann, [Ann.BIT, ['Data accepted']])
        elif miso == 0x0b:
            self.put(m[3][1], m[1][2], self.out_ann, [Ann.BIT, ['Data rejected (CRC error)']])
        elif miso == 0x0d:
            self.put(m[3][1], m[1][2], self.out_ann, [Ann.BIT, ['Data rejected (write error)']])
        self.put(m[0][1], m[0][2], self.out_ann, [Ann.BIT, ['Always 1']])
        cls = Ann.CMD24 if self.is_cmd24 else None
        if cls is not None:
            self.put(self.ss, self.es, self.out_ann, [cls, ['Data Response']])
        if self.is_cmd24:
            # We just send a block of data to be written to the card,
            # this takes some time.
            self.state = 'WAIT WHILE CARD BUSY'
            self.busy_first_byte = True
        else:
            self.state = 'IDLE'

    def wait_while_busy(self, miso):
        if miso != 0x00:
            cls = Ann.CMD24 if self.is_cmd24 else None
            if cls is not None:
                self.put(self.ss_busy, self.es_busy, self.out_ann, [cls, ['Card is busy']])
            self.state = 'IDLE'
            return
        else:
            if self.busy_first_byte:
                self.ss_busy = self.ss
                self.busy_first_byte = False
            else:
                self.es_busy = self.es

    def decode(self, ss, es, data):
        ptype, mosi, miso = data

        # For now, only use DATA and BITS packets.
        if ptype not in ('DATA', 'BITS'):
            return

        # Store the individual bit values and ss/es numbers. The next packet
        # is guaranteed to be a 'DATA' packet belonging to this 'BITS' one.
        if ptype == 'BITS':
            self.miso_bits, self.mosi_bits = miso, mosi
            return

        self.ss, self.es = ss, es

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
            a, cmdstr = 'a' if self.is_acmd else '', self.state[10:].lower()
            handle_cmd = getattr(self, 'handle_%scmd%s' % (a, cmdstr))
            handle_cmd()
            self.cmd_token = []
            self.cmd_token_bits = []
            # Leave ACMD mode again after the first command after CMD55.
            if self.is_acmd and cmdstr != '55':
                self.is_acmd = False
        elif self.state.startswith('GET RESPONSE'):
            # Ignore stray 0xff bytes, some devices seem to send those!?
            if miso == 0xff: # TODO?
                return
            # Call the respective handler method for the response.
            # Assume return to IDLE state, but allow response handlers
            # to advance to some other state when applicable.
            s = 'handle_response_%s' % self.state[13:].lower()
            handle_response = getattr(self, s)
            self.state = 'IDLE'
            handle_response(miso)
        elif self.state == 'HANDLE DATA BLOCK CMD17':
            self.handle_data_cmd17(miso)
        elif self.state == 'HANDLE DATA BLOCK CMD18':
            self.handle_data_cmd18(mosi, miso)
        elif self.state == 'HANDLE DATA BLOCK CMD24':
            self.handle_data_cmd24(mosi)
        elif self.state == 'DATA RESPONSE':
            self.handle_data_response(miso)
        elif self.state == 'WAIT WHILE CARD BUSY':
            self.wait_while_busy(miso)
