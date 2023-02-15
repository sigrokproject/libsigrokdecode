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
        self.ss_r, self.es_r = 0, 0
        self.ss_busy, self.es_busy = 0, 0
        self.cmd_token = []
        self.cmd_token_bits = []
        self.is_acmd = 0 # Indicates CMD vs. ACMD
        self.blocklen = 0
        self.read_buf = []
        self.read_buf_bits = []
        self.cmd_str = ''
        self.cmd = 0
        self.r1 = 0
        self.start_token_found = False
        self.finish_token_found = False
        self.is_first_rx = False
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
        self.cmd = self.cmd_index = t[0] & 0x3f
        self.ss_bit, self.es_bit = tb(5, 5)[1], tb(5, 0)[2]
        self.putb([Ann.BIT, ['Command: %s%d (%s)' % (s, self.cmd, self.cmd_name(self.cmd))]])

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
        if self.cmd in (0, 1, 6, 9, 10, 13, 16, 17, 24, 41, 49, 51, 55, 58, 59):
            self.state = 'HANDLE CMD%d' % self.cmd
            self.cmd_str = '%s%d (%s)' % (s, self.cmd, self.cmd_name(self.cmd))
        else:
            self.state = 'HANDLE CMD999'
            a = '%s%d: %02x %02x %02x %02x %02x %02x' % ((s, self.cmd) + tuple(t))
            self.putx([self.cmd, [a]])

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

    def handle_cmd6(self):
        # CMD6: SWITCH_FUNC (64 bits / 8 bytes)
        self.putc(Ann.CMD6, 'Check switchable mode and check switch function')
        self.state = 'GET RESPONSE R1'
        #self.state = 'IDLE'

    def handle_cmd9(self):
        # CMD9: SEND_CSD (128 bits / 16 bytes)
        self.putc(Ann.CMD9, 'Ask card to send its card specific data (CSD)')
        self.state = 'GET RESPONSE R1'

    def handle_cmd10(self):
        # CMD10: SEND_CID (128 bits / 16 bytes)
        self.putc(Ann.CMD10, 'Ask card to send its card ID (CID)')
        self.state = 'GET RESPONSE R1'

    def handle_cmd13(self):
        # CMD13: SEND_STATUS
        self.putc(Ann.CMD13, 'Ask card to send the Status register')
        self.state = 'GET RESPONSE R2'

    def handle_cmd16(self):
        # CMD16: SET_BLOCKLEN
        self.blocklen = self.arg
        # TODO: Sanity check on block length.
        self.putc(Ann.CMD16, 'Set the block length to %d bytes' % self.blocklen)
        self.state = 'GET RESPONSE R1'

    def handle_cmd17(self):
        # CMD17: READ_SINGLE_BLOCK
        self.putc(Ann.CMD17, 'Read a block from address 0x%04x' % self.arg)
        self.state = 'GET RESPONSE R1'

    def handle_cmd24(self):
        # CMD24: WRITE_BLOCK
        self.putc(Ann.CMD24, 'Write a block to address 0x%04x' % self.arg)
        self.state = 'GET RESPONSE R1'

    def handle_cmd49(self):
        self.state = 'GET RESPONSE R1'

    def handle_cmd55(self):
        # CMD55: APP_CMD
        self.putc(Ann.CMD55, 'Next command is an application-specific command')
        self.is_acmd = 1
        self.state = 'GET RESPONSE R1'

    def handle_cmd58(self):
        # CMD58: SEND_OCR (128 bits / 16 bytes)
        self.putc(Ann.CMD58, 'Ask card to send the OCR register')
        self.state = 'GET RESPONSE R3'

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

    def handle_acmd51(self):
        # ACMD51: SEND_SCR (64 bits / 8 bytes)
        self.putc(Ann.ACMD51, 'Ask card to send its SCR register')
        self.state = 'GET RESPONSE R1'
        #self.state = 'IDLE'

    def handle_cmd999(self):
        self.state = 'GET RESPONSE R1'

    def handle_acmd999(self):
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

        # Ignore leading 0xff bytes before get R1 byte. Can get 1-8 of these.
        if res == 0xff:
            return

        self.r1 = res
        self.ss_cmd, self.es_cmd = self.miso_bits[7][1], self.miso_bits[0][2]
        self.ss_r, self.es_r = self.ss_cmd, self.es_cmd
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
        s = 'M' if (res & (1 << 5)) else 'No m'
        putbit(5, ['%sisaligned address used in command' % s])

        # Bit 6: 'Parameter error' bit
        s = '' if (res & (1 << 6)) else 'not '
        putbit(6, ['Command argument %soutside allowed range' % s])

        # Bit 7: Always set to 0
        putbit(7, ['Bit 7 (always 0)'])

        if (res & (1 << 2)) or (res & (1 << 3)) or (res & (1 << 5)) or (res & (1 << 6)):
            self.state = 'IDLE'
            return;

        if (not self.is_acmd) and (self.cmd in (6, 9, 10, 17)):
            self.state = 'WAIT DATA RESPONSE'
        elif (self.is_acmd) and (self.cmd == 51):
            self.state = 'WAIT DATA RESPONSE'
        elif (not self.is_acmd) and (self.cmd in (24, 25)):
            self.state = 'HANDLE TX BLOCK CMD%d' % self.cmd

    def handle_response_r1b(self, res):
        # TODO
        pass


    def handle_response_r2(self, res):
        # The R2 response token format (1+1 bytes).
        # Sent by the card after CMD58 SEND_STATUS

        def putbit(bit, data):
            b = self.miso_bits[bit]
            self.ss_bit, self.es_bit = b[1], b[2]
            self.putb([Ann.BIT, data])

        if len(self.read_buf) == 0:
            # Ignore leading 0xff bytes before get R1 byte. Can get 1-8 of these.
            if res == 0xff:
                return

            self.r1 = res
            self.ss_r = self.miso_bits[0][2]
            self.ss_cmd, self.es_cmd = self.miso_bits[7][1], self.miso_bits[0][2]
            self.putx([Ann.R1, ['R1: 0x%02x' % res]])

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

        self.read_buf.append(res)
        if len(self.read_buf) < 2:
            self.state = 'GET RESPONSE R2'
            return

        t = self.read_buf
        r2 = t[1]

        self.ss_cmd, self.es_cmd = self.ss_r, self.miso_bits[0][2]
        self.putx([Ann.R2, ['R2: 0x%02x' % r2]])

        # Bit 0: 'Card is locked' bit
        s = '' if (res & (1 << 0)) else 'not '
        putbit(0, ['Card is %slocked' % s])

        # Bit 1: 'Write Protect erase skip | lock/unlock command failed' bit
        s = '' if (res & (1 << 1)) else 'not '
        putbit(1, ['Write Protect Erase Skip/Lock/Unlock command %sfailed' % s])

        # Bit 2: 'Error' bit
        s = 'E' if (res & (1 << 2)) else 'No e'
        putbit(2, ['%srror' % s])

        # Bit 3: 'Card controller error' bit
        s = 'C' if (res & (1 << 3)) else 'No c'
        putbit(3, ['%sard controller error' % s])

        # Bit 4: 'ECC Failed' bit
        s = '' if (res & (1 << 4)) else 'No '
        putbit(4, ['%sECC Failed' % s])

        # Bit 5: 'Write Protect Violation' bit
        s = 'W' if (res & (1 << 5)) else 'No w'
        putbit(5, ['%srite protect violation' % s])

        # Bit 6: 'Erase param' bit
        s = 'I' if (res & (1 << 6)) else 'No i'
        putbit(6, ['%snvalid selection for erase, sectors or groups' % s])

        # Bit 7: 'Out of Range | CSD overwrite'
        s = 'O' if (res & (1 << 7)) else 'Not o'
        putbit(7, ['%sut of Range | CSD overwrite' % s])

        self.state = 'IDLE'
        self.read_buf = []


    def handle_response_r3(self, res):
        # The R3 response token format (1+4 bytes).
        # Sent by the card after CMD58 READ_OCR

        def putbit(bit, data):
            b = self.miso_bits[bit]
            self.ss_bit, self.es_bit = b[1], b[2]
            self.putb([Ann.BIT, data])

        if len(self.read_buf) == 0:
            # Ignore leading 0xff bytes before get R1 byte. Can get 1-8 of these.
            if res == 0xff:
                return

            self.r1 = res
            self.ss_r = self.miso_bits[0][2]
            self.ss_cmd, self.es_cmd = self.miso_bits[7][1], self.miso_bits[0][2]
            self.putx([Ann.R1, ['R1: 0x%02x' % res]])

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
            s = 'M' if (res & (1 << 5)) else 'No m'
            putbit(5, ['%sisaligned address used in command' % s])

            # Bit 6: 'Parameter error' bit
            s = '' if (res & (1 << 6)) else 'not '
            putbit(6, ['Command argument %soutside allowed range' % s])

            # Bit 7: Always set to 0
            putbit(7, ['Bit 7 (always 0)'])

        if len(self.read_buf) == 1:
            s = 'READY' if (res & (1 << 7)) else 'BUSY'
            putbit(7, ['Power-Up Status Bit %s' % s])

            s = 'HC/XC' if (res & (1 << 6)) else 'SC'
            putbit(6, ['Card Capacity Status %s' % s])

            self.ss_bit, self.es_bit = self.miso_bits[5][1], self.miso_bits[1][2]
            self.putb([Ann.BIT, ['Reserved']])

            s = '' if (res & (1 << 0)) else 'Not '
            putbit(0, ['%s1.8V Tolerant' % s])

        if len(self.read_buf) == 2:
            s = '' if (res & (1 << 7)) else 'not '
            putbit(7, ['3.6-3.5V %sOK' % s])

            s = '' if (res & (1 << 6)) else 'not '
            putbit(6, ['3.5-3.4V %sOK' % s])

            s = '' if (res & (1 << 5)) else 'not '
            putbit(5, ['3.4-3.3V %sOK' % s])

            s = '' if (res & (1 << 4)) else 'not '
            putbit(4, ['3.3-3.2V %sOK' % s])

            s = '' if (res & (1 << 3)) else 'not '
            putbit(3, ['3.2-3.1V %sOK' % s])

            s = '' if (res & (1 << 2)) else 'not '
            putbit(2, ['3.1-3.0V %sOK' % s])

            s = '' if (res & (1 << 1)) else 'not '
            putbit(1, ['3.0-2.9V %sOK' % s])

            s = '' if (res & (1 << 0)) else 'not '
            putbit(0, ['2.9-2.8V %sOK' % s])

        if len(self.read_buf) == 3:
            s = '' if (res & (1 << 7)) else 'not '
            putbit(7, ['2.8-2.7V %sOK' % s])

            self.ss_bit, self.es_bit = self.miso_bits[6][1], self.miso_bits[0][2]
            self.putb([Ann.BIT, ['Reserved']])

        if len(self.read_buf) == 4:
            putbit(7, ['Reserved Low Voltage'])

            self.ss_bit, self.es_bit = self.miso_bits[6][1], self.miso_bits[4][2]
            self.putb([Ann.BIT, ['Reserved']])

            self.ss_bit, self.es_bit = self.miso_bits[3][1], self.miso_bits[0][2]
            self.putb([Ann.BIT, ['Reserved']])

        self.read_buf.append(res)
        if len(self.read_buf) < 5:
            self.state = 'GET RESPONSE R3'
            return

        t = self.read_buf
        r3 = (t[3] << 24) | (t[2] << 16) | (t[1] << 8) | t[0]

        self.ss_cmd, self.es_cmd = self.ss_r, self.miso_bits[0][2]
        self.putx([Ann.R3, ['R3: 0x%08x' % r3]])
        self.state = 'IDLE'
        self.read_buf = []

    # Note: Response token formats R4 and R5 are reserved for SDIO.

    # TODO: R6?

    def handle_response_r7(self, res):
        # TODO
        pass

    def handle_data_cmd6(self, miso):
        # CMD6 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then 64 bytes of data, then always
        # 2 bytes of CRC.
        if len(self.read_buf) == 0:
            self.ss_data = self.ss
        self.read_buf.append(miso)
        # Wait until block transfer completed.
        if len(self.read_buf) < 64:
            return
        if len(self.read_buf) == 64:
            self.es_data = self.es
            self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD6, ['Block data: %s' % self.read_buf]])
        elif len(self.read_buf) == (64 + 1):
            self.ss_crc = self.ss
        elif len(self.read_buf) == (64 + 2):
            self.es_crc = self.es
            # TODO: Check CRC.
            self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD6, ['CRC - WARNING: If High Speed (HS) mode got set here the next instruction(s) may be decoded incorrectly, see description']])
            self.read_buf = []
            self.state = 'IDLE'

    def handle_data_cmd9(self, miso):
        # CMD9 CSD returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then 16 bytes of data, then always
        # 2 bytes of CRC.
        if len(self.read_buf) == 0:
            self.ss_data = self.ss
        self.read_buf.append(miso)
        self.read_buf_bits += self.miso_bits

        def putbit(bit, data):
            b = self.read_buf_bits[bit]
            self.ss_bit, self.es_bit = b[1], b[2]
            self.putb([Ann.BIT, data])

        # Wait until block transfer completed.
        if len(self.read_buf) < 16:
            return
        if len(self.read_buf) == 16:
            self.es_data = self.es
            self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD9, ['CSD: %s' % self.read_buf]])

            csd_ver = (((self.read_buf[0] & 0xC0) >> 6)+1)

            self.ss_bit, self.es_bit = self.read_buf_bits[7][1], self.read_buf_bits[6][2]
            self.putb([Ann.BIT, ['CSD V%d.0' % csd_ver]])

            self.ss_bit, self.es_bit = self.read_buf_bits[5][1], self.read_buf_bits[0][2]
            self.putb([Ann.BIT, ['Reserved']])

            self.ss_bit, self.es_bit = self.read_buf_bits[8+6][1], self.read_buf_bits[8+0][2]
            time_unit = self.read_buf[1] & 0x07
            time_value = (self.read_buf[1] & 0x78) >> 3
            taac = time_value
            if (0 == time_value):
                taac = 0.0
            elif (1 == time_value):
                taac = 1.0
            elif (2 == time_value):
                taac = 1.2
            elif (3 == time_value):
                taac = 1.3
            elif (4 == time_value):
                taac = 1.5
            elif (5 == time_value):
                taac = 2.0
            elif (6 == time_value):
                taac = 2.5
            elif (7 == time_value):
                taac = 3.0
            elif (8 == time_value):
                taac = 3.5
            elif (9 == time_value):
                taac = 4.0
            elif (10 == time_value):
                taac = 4.5
            elif (11 == time_value):
                taac = 5.0
            elif (12 == time_value):
                taac = 5.5
            elif (13 == time_value):
                taac = 6.0
            elif (14 == time_value):
                taac = 7.0
            elif (15 == time_value):
                taac = 8.0
            taac *= pow(10, time_unit)
            self.putb([Ann.BIT, ['TAAC Data read access-time-1 %dns' % taac]])

            self.ss_bit, self.es_bit = self.read_buf_bits[2*8+7][1], self.read_buf_bits[2*8+0][2]
            self.putb([Ann.BIT, ['NSAC data read access-time-2 CLK cycles %d' % (self.read_buf[2] * 100)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+6][1], self.read_buf_bits[3*8+0][2]
            tf_rate_unit = self.read_buf[3] & 0x07
            tf_rate_value = (self.read_buf[3] & 0x78) >> 3
            tran_speed = tf_rate_value
            if (0 == tf_rate_value):
                tran_speed = 0.0
            elif (1 == tf_rate_value):
                tran_speed = 1.0
            elif (2 == tf_rate_value):
                tran_speed = 1.2
            elif (3 == tf_rate_value):
                tran_speed = 1.3
            elif (4 == tf_rate_value):
                tran_speed = 1.5
            elif (5 == tf_rate_value):
                tran_speed = 2.0
            elif (6 == tf_rate_value):
                tran_speed = 2.5
            elif (7 == tf_rate_value):
                tran_speed = 3.0
            elif (8 == tf_rate_value):
                tran_speed = 3.5
            elif (9 == tf_rate_value):
                tran_speed = 4.0
            elif (10 == tf_rate_value):
                tran_speed = 4.5
            elif (11 == tf_rate_value):
                tran_speed = 5.0
            elif (12 == tf_rate_value):
                tran_speed = 5.5
            elif (13 == tf_rate_value):
                tran_speed = 6.0
            elif (14 == tf_rate_value):
                tran_speed = 7.0
            elif (15 == tf_rate_value):
                tran_speed = 8.0
            tran_speed *= pow(10, tf_rate_unit)*.1
            self.putb([Ann.BIT, ['TRAN_SPEED Max data rate %dMHz' % tran_speed]])

            s = '' if (self.read_buf[4] & (1 << 7)) else 'not '
            putbit(4*8+7, ['CCC Class 0 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 6)) else 'not '
            putbit(4*8+6, ['CCC Class 1 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 5)) else 'not '
            putbit(4*8+5, ['CCC Class 2 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 4)) else 'not '
            putbit(4*8+4, ['CCC Class 3 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 3)) else 'not '
            putbit(4*8+3, ['CCC Class 4 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 2)) else 'not '
            putbit(4*8+2, ['CCC Class 5 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 1)) else 'not '
            putbit(4*8+1, ['CCC Class 6 %ssupported' % s])

            s = '' if (self.read_buf[4] & (1 << 0)) else 'not '
            putbit(4*8+0, ['CCC Class 7 %ssupported' % s])

            s = '' if (self.read_buf[5] & (1 << 7)) else 'not '
            putbit(5*8+7, ['CCC Class 8 %ssupported' % s])

            s = '' if (self.read_buf[5] & (1 << 6)) else 'not '
            putbit(5*8+6, ['CCC Class 9 %ssupported' % s])

            s = '' if (self.read_buf[5] & (1 << 5)) else 'not '
            putbit(5*8+5, ['CCC Class 10 %ssupported' % s])

            s = '' if (self.read_buf[5] & (1 << 4)) else 'not '
            putbit(5*8+4, ['CCC Class 11 %ssupported' % s])

            self.ss_bit, self.es_bit = self.read_buf_bits[5*8+3][1], self.read_buf_bits[5*8+0][2]
            read_bl_len = (self.read_buf[5] & 0xf)
            read_bl_len = pow(2, read_bl_len)
            self.putb([Ann.BIT, ['READ_BL_LEN %d' % read_bl_len]])

            s = '' if (self.read_buf[6] & (1 << 7)) else 'not '
            putbit(6*8+7, ['READ_BL_PARTIAL %sallowed' % s])

            s = '' if (self.read_buf[6] & (1 << 6)) else 'not '
            putbit(6*8+6, ['WRITE_BLK_MISALIGN %sallowed' % s])

            s = '' if (self.read_buf[6] & (1 << 5)) else 'not '
            putbit(6*8+5, ['READ_BLK_MISALIGN %sallowed' % s])

            s = '' if (self.read_buf[6] & (1 << 4)) else 'not '
            putbit(6*8+4, ['DSR_IMP configurable driver %simplemented' % s])

            if (1 == csd_ver):
                self.ss_bit, self.es_bit = self.read_buf_bits[6*8+3][1], self.read_buf_bits[6*8+2][2]
                self.putb([Ann.BIT, ['Reserved']])

                self.ss_bit, self.es_bit = self.read_buf_bits[9*8+1][1], self.read_buf_bits[10*8+7][2]
                c_size_mult = ((self.read_buf[9] & 0x3) << 1) + ((self.read_buf[10] & 0x80) >> 7)
                c_size_mult = pow(2, c_size_mult + 2)
                self.putb([Ann.BIT, ['C_SIZE_MULT %d' % c_size_mult]])

                self.ss_bit, self.es_bit = self.read_buf_bits[6*8+1][1], self.read_buf_bits[8*8+6][2]
                c_size = ((self.read_buf[6] & 0x3) << 10) + ((self.read_buf[7] & 0xff) << 2) + ((self.read_buf[8] & 0xC0) >> 6)
                c_size *= read_bl_len * c_size_mult
                self.putb([Ann.BIT, ['C_SIZE %d+1 sectors %.2fGB' % (c_size, (c_size * read_bl_len * c_size_mult) / (1024 * 1024))]])

                self.ss_bit, self.es_bit = self.read_buf_bits[8*8+5][1], self.read_buf_bits[9*8+2][2]
                self.putb([Ann.BIT, ['Card max currents']])

            elif (2 == csd_ver):
                self.ss_bit, self.es_bit = self.read_buf_bits[6*8+3][1], self.read_buf_bits[7*8+6][2]
                self.putb([Ann.BIT, ['Reserved']])

                self.ss_bit, self.es_bit = self.read_buf_bits[7*8+5][1], self.read_buf_bits[9*8+0][2]
                c_size = ((self.read_buf[7] & 0x3f) << 16) + ((self.read_buf[8] & 0xff) << 8) + ((self.read_buf[9] & 0xff))
                self.putb([Ann.BIT, ['C_SIZE %d+1 sectors %.2fGB' % (c_size, (c_size+1) / 2048)]])

                putbit(10*8+7, ['Reserved'])

            s = '' if (self.read_buf[10] & (1 << 6)) else 'not '
            putbit(10*8+6, ['ERASE_BLK_EN Erase single block %senabled' % s])

            self.ss_bit, self.es_bit = self.read_buf_bits[10*8+5][1], self.read_buf_bits[11*8+7][2]
            wp_grp_size = ((self.read_buf[10] & 0x3f) << 1) + ((self.read_buf[11] & 0x80) >> 7)
            self.putb([Ann.BIT, ['ERASE_SECTOR_SIZE %d+1 sectors' % wp_grp_size]])

            self.ss_bit, self.es_bit = self.read_buf_bits[11*8+6][1], self.read_buf_bits[11*8+0][2]
            wp_grp_size = ((self.read_buf[11] & 0x7f))
            self.putb([Ann.BIT, ['WP_GRP_SIZE %d+1 sectors' % wp_grp_size]])

            s = '' if (self.read_buf[12] & (1 << 7)) else 'not '
            putbit(12*8+7, ['WP_GRP_ENABLE Group Write Protect %senabled' % s])

            self.ss_bit, self.es_bit = self.read_buf_bits[12*8+6][1], self.read_buf_bits[12*8+5][2]
            self.putb([Ann.BIT, ['Reserved']])

            self.ss_bit, self.es_bit = self.read_buf_bits[12*8+4][1], self.read_buf_bits[12*8+2][2]
            r2w_factor = ((self.read_buf[12] & 0x1C) >> 2)
            r2w_factor = pow(2, r2w_factor)
            self.putb([Ann.BIT, ['R2W_FACTOR %d' % r2w_factor]])

            self.ss_bit, self.es_bit = self.read_buf_bits[12*8+1][1], self.read_buf_bits[13*8+6][2]
            write_bl_len = ((self.read_buf[12] & 0x3) << 2) + ((self.read_buf[13] & 0xC0) >> 6)
            write_bl_len = pow(2, write_bl_len)
            self.putb([Ann.BIT, ['WRITE_BL_LEN %d' % write_bl_len]])

            s = '' if (self.read_buf[13] & (1 << 5)) else 'not '
            putbit(13*8+5, ['WRITE_BL_PARTIAL Partial Block write %senabled' % s])

            self.ss_bit, self.es_bit = self.read_buf_bits[13*8+4][1], self.read_buf_bits[13*8+0][2]
            self.putb([Ann.BIT, ['Reserved']])

            file_format_grp = 1 if (self.read_buf[14] & (1 << 7)) else 0
            putbit(14*8+7, ['FILE_FORMAT_GRP %d' % file_format_grp])

            s = 'copied' if (self.read_buf[14] & (1 << 6)) else 'original'
            putbit(14*8+6, ['COPY Contents are %s' % s])

            s = 'P' if (self.read_buf[14] & (1 << 5)) else 'Not p'
            putbit(14*8+5, ['PERM_WRITE_PROTECT %sermanently write protected' % s])

            s = 'W' if (self.read_buf[14] & (1 << 4)) else 'Not w'
            putbit(14*8+4, ['TMP_WRITE_PROTECT %srite protected' % s])

            self.ss_bit, self.es_bit = self.read_buf_bits[14*8+3][1], self.read_buf_bits[14*8+2][2]
            file_format = ((self.read_buf[14] & 0xC) >> 2)
            if (0 == file_format):
                s = 'Hard disk-like with partition table'
            elif (1 == file_format):
                s = 'DOS FAT floppy like with boot sector only, no partition table'
            elif (2 == file_format):
                s = 'Universal File Format'
            elif (3 == file_format):
                s = 'Others/Unknown'
            self.putb([Ann.BIT, ['FILE_FORMAT %d %s' % (file_format, s)]])

            s = 'W' if (self.read_buf[14] & (1 << 1)) else 'Not w'
            putbit(14*8+1, ['WP_UPC %srite protected until power cycle' % s])

            putbit(14*8+0, ['Reserved'])

            self.ss_bit, self.es_bit = self.read_buf_bits[15*8+7][1], self.read_buf_bits[15*8+2][2]
            self.putb([Ann.BIT, ['CRC7 0x%02x' % ((self.read_buf[15] & 0xfe) >> 1)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[15*8+1][1], self.read_buf_bits[15*8+0][2]
            self.putb([Ann.BIT, ['Always 1']])


        elif len(self.read_buf) == (16 + 1):
            self.ss_crc = self.ss
        elif len(self.read_buf) == (16 + 2):
            self.es_crc = self.es
            # TODO: Check CRC.
            self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD9, ['CRC']])
            self.read_buf = []
            self.state = 'IDLE'

    def handle_data_cmd10(self, miso):
        # CMD10 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then 16 bytes of data, then always
        # 2 bytes of CRC.
        if len(self.read_buf) == 0:
            self.ss_data = self.ss
        self.read_buf.append(miso)
        self.read_buf_bits += self.miso_bits
        # Wait until block transfer completed.
        if len(self.read_buf) < 16:
            return
        if len(self.read_buf) == 16:
            self.es_data = self.es
            self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD10, ['CID: %s' % self.read_buf]])

            self.ss_bit, self.es_bit = self.read_buf_bits[7][1], self.read_buf_bits[0][2]
            self.putb([Ann.BIT, ['Manufacturer ID 0x%02x' % self.read_buf[0]]])

            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+7][1], self.read_buf_bits[2*8+0][2]
            self.putb([Ann.BIT, ['OEM ID \'%c%c\'' % (self.read_buf[1], self.read_buf[2])]])

            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+7][1], self.read_buf_bits[7*8+0][2]
            self.putb([Ann.BIT, ['PNM Product Name \'%c%c%c%c%c\'' % (self.read_buf[3], self.read_buf[4], self.read_buf[5], self.read_buf[6], self.read_buf[7])]])

            self.ss_bit, self.es_bit = self.read_buf_bits[8*8+7][1], self.read_buf_bits[8*8+0][2]
            self.putb([Ann.BIT, ['PRV Product Revision %d.%d' % ((self.read_buf[8] & 0xf0) >> 4, self.read_buf[8] & 0xf)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[9*8+7][1], self.read_buf_bits[12*8][2]
            self.putb([Ann.BIT, ['PSN Serial No 0x%02x%02x%02x%02x' % (self.read_buf[9], self.read_buf[10], self.read_buf[11], self.read_buf[12])]])

            self.ss_bit, self.es_bit = self.read_buf_bits[13*8+7][1], self.read_buf_bits[13*8+4][2]
            self.putb([Ann.BIT, ['Reserved 0x%x' % ((self.read_buf[13] & 0xf0) >> 4)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[13*8+3][1], self.read_buf_bits[14*8+0][2]
            self.putb([Ann.BIT, ['Mfg Date %d/2%03d' % ((self.read_buf[14] & 0xf), ((self.read_buf[13] & 0xf) << 4) + ((self.read_buf[14] & 0xf0) >> 4))]])

            self.ss_bit, self.es_bit = self.read_buf_bits[15*8+7][1], self.read_buf_bits[15*8+2][2]
            self.putb([Ann.BIT, ['CRC7 0x%02x' % ((self.read_buf[15] & 0xfe) >> 1)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[15*8+1][1], self.read_buf_bits[15*8+0][2]
            self.putb([Ann.BIT, ['Always 1']])


        elif len(self.read_buf) == (16 + 1):
            self.ss_crc = self.ss
        elif len(self.read_buf) == (16 + 2):
            self.es_crc = self.es
            # TODO: Check CRC.
            self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD10, ['CRC']])
            self.read_buf = []
            self.state = 'IDLE'

    def handle_data_cmd17(self, miso):
        # CMD17 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then self.blocklen bytes of data, then always
        # 2 bytes of CRC.
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
            # TODO: Check CRC.
            self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.CMD17, ['CRC']])
            self.read_buf = []
            self.state = 'IDLE'

    def handle_data_cmd24(self, mosi):
        if self.start_token_found:
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
            if len(self.read_buf) == self.blocklen:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD24, ['Block data: %s' % self.read_buf]])
                self.ss_data = self.es
            if len(self.read_buf) == self.blocklen + 1:
                self.ss_data = self.ss
            if len(self.read_buf) == self.blocklen + 2:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD24, ['CRC']])
                self.read_buf = []
                self.state = 'DATA RESPONSE'
        elif mosi == 0xfe:
            self.put(self.ss_data, self.ss, self.out_ann, [Ann.CMD24, ['Wait for response']])
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD24, ['Start Block']])
            self.start_token_found = True
            self.is_first_rx = False
        elif False == self.is_first_rx:
            self.ss_data = self.ss
            self.is_first_rx = True

    def handle_data_cmd25(self, mosi):
        if self.start_token_found:
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
            if len(self.read_buf) == self.blocklen:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD25, ['Block data: %s' % self.read_buf]])
                self.ss_data = self.es
            if len(self.read_buf) == self.blocklen + 1:
                self.ss_data = self.ss
            if len(self.read_buf) == self.blocklen + 2:
                self.es_data = self.es
                self.put(self.ss_data, self.es_data, self.out_ann, [Ann.CMD25, ['CRC']])
                self.read_buf = []
                self.start_token_found = False
                self.is_first_rx = True
                self.state = 'DATA RESPONSE'
        elif mosi == 0xfc:
            self.put(self.ss_data, self.ss, self.out_ann, [Ann.CMD25, ['Wait for response']])
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD25, ['Start Block']])
            self.start_token_found = True
            self.is_first_rx = False
        elif self.finish_token_found:
            self.state = 'WAIT WHILE CARD BUSY'
            self.busy_first_byte = True
            self.is_first_rx = False
            self.finish_token_found = False
            self.cmd = 24
        elif mosi == 0xfd:
            self.put(self.ss_data, self.ss, self.out_ann, [Ann.CMD25, ['Wait for response']])
            self.put(self.ss, self.es, self.out_ann, [Ann.CMD25, ['Stop Tran']])
            self.finish_token_found = True
        elif False == self.is_first_rx:
            self.ss_data = self.ss
            self.is_first_rx = True

    def handle_data_acmd51(self, miso):
        # CMD51 returns one byte R1, then some bytes 0xff, then a Start Block
        # (single byte 0xfe), then 8 bytes of data, then always
        # 2 bytes of CRC.
        if len(self.read_buf) == 0:
            self.ss_data = self.ss
        self.read_buf.append(miso)
        self.read_buf_bits += self.miso_bits
        # Wait until block transfer completed.
        if len(self.read_buf) < 8:
            return
        if len(self.read_buf) == 8:
            self.es_data = self.es
            self.put(self.ss_data, self.es_data, self.out_ann, [Ann.ACMD51, ['SCR SD Card Configuration Register: %s' % self.read_buf]])

            self.ss_bit, self.es_bit = self.read_buf_bits[7][1], self.read_buf_bits[4][2]
            scr_structure = ((self.read_buf[0] & 0xf0) >> 4) + 1
            self.putb([Ann.BIT, ['SCR V%d.0' % scr_structure]])

            self.ss_bit, self.es_bit = self.read_buf_bits[3][1], self.read_buf_bits[0][2]
            sd_spec = (self.read_buf[0] & 0xf)
            self.putb([Ann.BIT, ['SD_SPEC %d' % sd_spec]])

            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+7][1], self.read_buf_bits[1*8+7][2]
            self.putb([Ann.BIT, ['DATA_STAT_AFTER_ERASE %d' % ((self.read_buf[1] & 0x80) >> 7)]])

            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+6][1], self.read_buf_bits[1*8+4][2]
            sd_security = ((self.read_buf[1] & 0x70) >> 4)
            s = 'Reserved'
            if (0 == sd_security):
                s = 'No Security'
            elif (1 == sd_security):
                s = 'Not Used'
            elif (2 == sd_security):
                s = 'SDSC Card (Security Version 1.01)'
            elif (3 == sd_security):
                s = 'SDHC Card (Security Version 2.00)'
            elif (4 == sd_security):
                s = 'SDXC Card (Security Version 3.xx)'
            self.putb([Ann.BIT, ['SD_SECURITY %d %s' % (sd_security, s)]])

            #self.ss_bit, self.es_bit = self.read_buf_bits[1*8+3][1], self.read_buf_bits[1*8+0][2]
            #self.putb([Ann.BIT, ['SD_BUS_WIDTHS']])
            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+0][1], self.read_buf_bits[1*8+0][2]
            s = '' if (self.read_buf[1] & (1 << 0)) else 'not '
            self.putb([Ann.BIT, ['SD_BUS_WIDTHS 1-bit %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+1][1], self.read_buf_bits[1*8+1][2]
            self.putb([Ann.BIT, ['SD_BUS_WIDTHS Reserved']])
            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+2][1], self.read_buf_bits[1*8+2][2]
            s = '' if (self.read_buf[1] & (1 << 2)) else 'not '
            self.putb([Ann.BIT, ['SD_BUS_WIDTHS 4-bit %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[1*8+3][1], self.read_buf_bits[1*8+3][2]
            self.putb([Ann.BIT, ['SD_BUS_WIDTHS Reserved']])

            self.ss_bit, self.es_bit = self.read_buf_bits[2*8+7][1], self.read_buf_bits[2*8+7][2]
            sd_spec3 = ((self.read_buf[2] & 0x80) >> 7)
            self.putb([Ann.BIT, ['SD_SPEC3 %d' % sd_spec3]])

            self.ss_bit, self.es_bit = self.read_buf_bits[2*8+6][1], self.read_buf_bits[2*8+3][2]
            ex_security = ((self.read_buf[2] & 0x78) >> 3)
            self.putb([Ann.BIT, ['EX_SECURITY %d' % ex_security]])

            self.ss_bit, self.es_bit = self.read_buf_bits[2*8+2][1], self.read_buf_bits[2*8+2][2]
            sd_spec4 = ((self.read_buf[2] & 0x4) >> 2)
            self.putb([Ann.BIT, ['SD_SPEC4 %d' % sd_spec4]])

            self.ss_bit, self.es_bit = self.read_buf_bits[2*8+1][1], self.read_buf_bits[3*8+6][2]
            sd_specx = ((self.read_buf[2] & 0x3) << 2) + ((self.read_buf[3] & 0xC0) >> 6)
            self.putb([Ann.BIT, ['SD_SPECX %d' % sd_specx]])

            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+5][1], self.read_buf_bits[3*8+5][2]
            self.putb([Ann.BIT, ['Reserved']])

            #self.ss_bit, self.es_bit = self.read_buf_bits[3*8+4][1], self.read_buf_bits[3*8+0][2]
            #self.putb([Ann.BIT, ['CMD_SUPPORT']])
            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+4][1], self.read_buf_bits[3*8+4][2]
            s = '' if (self.read_buf[3] & (1 << 4)) else 'not '
            self.putb([Ann.BIT, ['CMD_SUPPORT Secure Rx/Tx ACMD53/54 %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+3][1], self.read_buf_bits[3*8+3][2]
            s = '' if (self.read_buf[3] & (1 << 3)) else 'not '
            self.putb([Ann.BIT, ['CMD_SUPPORT Extension Register Multi-block CMD58/59 %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+2][1], self.read_buf_bits[3*8+2][2]
            s = '' if (self.read_buf[3] & (1 << 2)) else 'not '
            self.putb([Ann.BIT, ['CMD_SUPPORT Extension Register Single Block CMD48/49 %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+1][1], self.read_buf_bits[3*8+1][2]
            s = '' if (self.read_buf[3] & (1 << 1)) else 'not '
            self.putb([Ann.BIT, ['CMD_SUPPORT Set Block Count CMD23 %ssupported' % s]])
            self.ss_bit, self.es_bit = self.read_buf_bits[3*8+0][1], self.read_buf_bits[3*8+0][2]
            s = '' if (self.read_buf[3] & (1 << 0)) else 'not '
            self.putb([Ann.BIT, ['CMD_SUPPORT Speed Class Control CMD20 %ssupported' % s]])

            self.ss_bit, self.es_bit = self.read_buf_bits[4*8+7][1], self.read_buf_bits[7*8+0][2]
            self.putb([Ann.BIT, ['Reserved']])


        elif len(self.read_buf) == (8 + 1):
            self.ss_crc = self.ss
        elif len(self.read_buf) == (8 + 2):
            self.es_crc = self.es
            # TODO: Check CRC.
            self.put(self.ss_crc, self.es_crc, self.out_ann, [Ann.ACMD51, ['CRC']])
            self.read_buf = []
            self.state = 'IDLE'

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
        cls = None
        if 24 == self.cmd:
            cls = Ann.CMD24
        elif 25 == self.cmd:
            cls = Ann.CMD25
        if cls is not None:
            self.put(self.ss, self.es, self.out_ann, [cls, ['Data Response']])
        if self.cmd in (24, 25):
            # We just send a block of data to be written to the card,
            # this takes some time.
            self.busy_first_byte = True
            self.state = 'WAIT WHILE CARD BUSY'
        else:
            self.state = 'IDLE'

    def wait_while_busy(self, miso):
        if miso != 0x00:
            cls = None
            if 24 == self.cmd:
                cls = Ann.CMD24
            elif 25 == self.cmd:
                cls = Ann.CMD25
            if cls is not None:
                self.put(self.ss_busy, self.es_busy, self.out_ann, [cls, ['Card is busy']])
            if 25 == self.cmd:
                self.read_buf = []
                self.ss_data = self.es
                self.start_token_found = False
                self.is_first_rx = True
                self.state = 'HANDLE TX BLOCK CMD25'
            else:
                self.state = 'IDLE'
            return
        else:
            if self.busy_first_byte:
                self.ss_busy = self.ss
                self.es_busy = self.es
                self.busy_first_byte = False
            else:
                self.es_busy = self.es

    def wait_data_response(self, miso):
        if miso == 0xfe:
            self.put(self.ss_busy, self.es_busy, self.out_ann, [Ann.R1, ['Wait for response']])
            self.put(self.ss, self.es, self.out_ann, [Ann.R1, ['Start Block']])
            if (not self.is_acmd) and (self.cmd in (6, 9, 10, 17)):
                self.state = 'HANDLE RX BLOCK CMD%d' % self.cmd
            elif (self.is_acmd) and (self.cmd == 51):
                self.state = 'HANDLE RX BLOCK ACMD%d' % self.cmd
            else:
                self.state = 'IDLE'
            return
        else:
            if self.busy_first_byte:
                self.ss_busy = self.ss
                self.es_busy = self.es
                self.busy_first_byte = False
            else:
                self.es_busy = self.es

    def decode(self, ss, es, data):
        ptype, mosi, miso = data

        # For now, only use DATA and BITS packets.
        if ptype not in ('DATA', 'BITS', 'CS-CHANGE'):
            return

        if 'CS-CHANGE' == ptype:
            self.state = 'IDLE'
            return

        # Store the individual bit values and ss/es numbers. The next packet
        # is guaranteed to be a 'DATA' packet belonging to this 'BITS' one.
        if ptype == 'BITS':
            self.miso_bits, self.mosi_bits = miso, mosi
            return

        self.ss, self.es = ss, es

        # State machine.
        if self.state == 'IDLE':
            self.read_buf = []
            self.read_buf_bits = []
            # Ignore stray 0xff bytes, some devices seem to send those!?
            if mosi == 0xff: # TODO?
                return
            # Leave ACMD mode again after the first command after CMD55.
            if self.is_acmd:
                self.is_acmd += 1
            if self.is_acmd > 2:
                self.is_acmd = 0
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
            self.start_token_found = False
            self.busy_first_byte = True
        elif self.state.startswith('GET RESPONSE'):
            # Call the respective handler method for the response.
            # Assume return to IDLE state, but allow response handlers
            # to advance to some other state when applicable.
            s = 'handle_response_%s' % self.state[13:].lower()
            handle_response = getattr(self, s)
            self.state = 'IDLE'
            handle_response(miso)
        elif self.state.startswith('HANDLE RX BLOCK'):
            # Call the respective handler method for the response.
            s = 'handle_data_%s' % self.state[16:].lower()
            handle_response = getattr(self, s)
            handle_response(miso)
        elif self.state.startswith('HANDLE TX BLOCK'):
            # Call the respective handler method for the sent data.
            s = 'handle_data_%s' % self.state[16:].lower()
            handle_response = getattr(self, s)
            handle_response(mosi)
        elif self.state == 'WAIT DATA RESPONSE':
            self.wait_data_response(miso)
        elif self.state == 'DATA RESPONSE':
            self.handle_data_response(miso)
        elif self.state == 'WAIT WHILE CARD BUSY':
            self.wait_while_busy(miso)
        else:
            self.state = 'IDLE'
