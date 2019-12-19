##
## This file is part of the sigrok project.
##
## Copyright (C) 2015 Uwe Hermann <uwe@hermann-uwe.de>
## Copyright (C) 2019 XIAO Xufeng <xiaoxufeng@espressif.com>
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
from .lists import *
from .sd_crc import crc7, crc16

sample_ahead_str = 'Yes (to meet the timing)'

class Decoder(srd.Decoder):
    api_version = 2
    id = 'sdio'
    name = 'SDIO'
    longname = 'Secure Digital I/O'
    desc = 'Secure Digital I/O low-level protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['sdio']
    channels = (
        {'id': 'cmd',  'name': 'CMD',  'desc': 'Command'},
        {'id': 'clk',  'name': 'CLK',  'desc': 'Clock'},
    )
    optional_channels = (
        {'id': 'dat0', 'name': 'DAT0', 'desc': 'Data pin 0'},
        {'id': 'dat1', 'name': 'DAT1', 'desc': 'Data pin 1'},
        {'id': 'dat2', 'name': 'DAT2', 'desc': 'Data pin 2'},
        {'id': 'dat3', 'name': 'DAT3', 'desc': 'Data pin 3'},
    )
    options = (
        { 'id' : 'lines', 'desc' : 'Lines used', 'default' : '1-line',
            'values' : ('1-line', '4-line') },
        { 'id' : 'io_block_len', 'desc' : 'Block size of SDIO', 'default' : '512',
            'values' : ('128', '256','512','1024') },
        { 'id' : 'sample_ahead', 'desc' : 'Sample 1 clk ahead', 'default' : 'No',
            'values' : ('No', sample_ahead_str) },
        { 'id' : 'polarity', 'desc' : 'Sample edge', 'default' : 'risedge',
            'values' : ('risedge', 'falledge') },
    )

    # 00-63 CMD
    # 64-127 ACMD
    # 128 Bits
    # 129 field-start
    # 130 field-transmission
    # 131 field-cmd
    # 132 field-arg
    # 133 field-crc
    # 134 field-end
    # 135 decoded-bits
    # 136 decoded-fields
    # 137 data
    # 138 data-field
    # 139 data-busy
    # 140 data-field-error
    annotations = \
        tuple(('cmd%d' % i, 'CMD%d' % i) for i in range(64)) + \
        tuple(('acmd%d' % i, 'ACMD%d' % i) for i in range(64)) + ( \
        ('bits', 'Bits'),
        ('field-start', 'Start bit'),
        ('field-transmission', 'Transmission bit'),
        ('field-cmd', 'Command'),
        ('field-arg', 'Argument'),
        ('field-crc', 'CRC'),
        ('field-end', 'End bit'),
        ('decoded-bits', 'Decoded bits'),
        ('decoded-fields', 'Decoded fields'),
        ('data', 'Data'),
        ('data-field', 'Data fields'),
        ('data-busy', 'Data busy'),
        ('data-field-error', 'Data fields (Error)'),
    )
    annotation_rows = (
        ('data', 'Data Line', tuple(range(137,141))),
        ('raw-bits', 'Raw bits', (128,)),
        ('decoded-bits', 'Decoded bits', (135,)),
        ('decoded-fields', 'Decoded fields', (136,)),
        ('fields', 'Fields', tuple(range(129, 135))),
        ('cmd', 'Commands', tuple(range(128))),
    )
    #supported commands
    cmd_list = (0, 2, 3, 5, 6, 7, 8, 9, 10, 13, 16, 52, 53, 55)
    acmd_list = (6, 13, 41, 51)


    def __init__(self, **kwargs):
        self.state = 'GET COMMAND TOKEN'
        self.token = []
        self.oldpins = None
        self.oldclk = None
        self.is_acmd = False # Indicates CMD vs. ACMD
        self.cmd = None
        self.arg = None
        self.four_line = False
        self.data_received = []
        self.data_bytes_required = 512
        self.data_crc_resp = False
        self.data_state = 'IDLE'

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.four_line = self.options['lines']=='4-line'
        self.rise_sample = self.options['polarity']=='risedge'
        self.sample_ahead = self.options['sample_ahead']==sample_ahead_str
        self.io_block_len = int(self.options['io_block_len'])

    # draw data
    def putd(self, s, e, data):
        self.put(s, e, self.out_ann, [137, data])

    # draw normal data fields
    def putdf(self, s, e, data, normal):
        if normal:
            self.put(s, e, self.out_ann, [138, data])
        else:
            self.put(s, e, self.out_ann, [140, data])

    # draw busy
    def putdb(self, s, e, data):
        self.put(s, e, self.out_ann, [139, data])

    def putbit(self, b, data):
        self.put(self.token[b][0], self.token[b][1], self.out_ann, [135, data])

    def putt(self, data):
        self.put(self.token[0][0], self.token[47][1], self.out_ann, data)

    def putt2(self, data):
        self.put(self.token[47][0], self.token[0][1], self.out_ann, data)

    def putf(self, s, e, data):
        self.put(self.token[s][0], self.token[e][1], self.out_ann, data)

    def puta(self, s, e, data):
        self.put(self.token[47 - 8 - e][0], self.token[47 - 8 - s][1],
                 self.out_ann, data)

    def putc(self, cmd, desc):
        self.putt([cmd, ['%s: %s' % (self.cmd_str, desc), self.cmd_str,
                         self.cmd_str.split(' ')[0]]])

    def putr(self, cmd, desc):
        self.putt([cmd, ['Reply: %s' % desc]])

    def putr2(self, cmd, desc):
        self.putt2([cmd, ['Reply: %s' % desc]])

    def reset(self):
        self.cmd, self.arg = None, None
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def cmd_name(self, cmd):
        c = acmd_names if self.is_acmd else cmd_names
        return c.get(cmd, 'Unknown')

    def get_token_bits(self, cmd, n):
        # Get a bit, return True if we already got 'n' bits, False otherwise.
        self.token.append([self.samplenum, self.samplenum, cmd])
        if len(self.token) > 0:
            self.token[len(self.token) - 2][1] = self.samplenum
        if len(self.token) < n:
            return False
        self.token[n - 1][1] += self.token[n - 1][0] - self.token[n - 2][0]
        return True

    def get_token_data(self, start, end):
        return int('0b' + ''.join([str(self.token[i][2]) for i in range(start, end+1)]), 2)

    def handle_common_token_fields(self):
        s = self.token
        self.crc = self.get_token_data(40, 46)

        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [128, ['%d' % s[bit][2]]])

        # CMD[47:47]: Start bit (always 0)
        self.putf(0, 0, [129, ['Start bit', 'Start', 'S']])

        # CMD[46:46]: Transmission bit (1 == host)
        t = 'host' if s[1][2] == 1 else 'card'
        self.putf(1, 1, [130, ['Transmission: ' + t, 'T: ' + t, 'T']])

        # CMD[45:40]: Command index (BCD; valid: 0-63)
        self.cmd = int('0b' + ''.join([str(s[i][2]) for i in range(2, 8)]), 2)
        c = '%s (%d)' % (self.cmd_name(self.cmd), self.cmd)
        self.putf(2, 7, [131, ['Command: ' + c, 'Cmd: ' + c,
                               'CMD%d' % self.cmd, 'Cmd', 'C']])

        # CMD[39:08]: Argument
        self.putf(8, 39, [132, ['Argument', 'Arg', 'A']])

        # CMD[07:01]: CRC7
        bit_array = [s[i][2] for i in range(0,40)]
        crc_cal = crc7(bit_array)
        if crc_cal != self.crc:
            self.putf(40, 46, [133, ['CRC Error: 0x%x(should be 0x%x)' % (self.crc,crc_cal), 'CRC Error', 'Error', 'E']])
        else:
            self.putf(40, 46, [133, ['CRC: 0x%x' % self.crc, 'CRC', 'C']])

        # CMD[00:00]: End bit (always 1)
        self.putf(47, 47, [134, ['End bit', 'End', 'E']])




    def handle_cmd0(self):
        # CMD0 (GO_IDLE_STATE) -> no response
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(0, 'Reset all SD cards')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_cmd2(self):
        # CMD2 (ALL_SEND_CID) -> R2
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(2, 'Ask card for CID number')
        self.token, self.state = [], 'GET RESPONSE R2'

    def handle_cmd3(self):
        # CMD3 (SEND_RELATIVE_ADDR) -> R6
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(3, 'Ask card for new relative card address (RCA)')
        self.token, self.state = [], 'GET RESPONSE R6'

    def handle_cmd5(self):
        # CMD5 (IO_SEND_OP_COND) -> R4
        self.puta(25, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(24, 24, [136, ['Switching to 1.8V Request', 'Switch to 1.8V', 'S18R']])
        self.puta(0, 23, [136, ['Operation Conditions Register', 'I/O OCR', 'OCR']])
        self.putc(5, 'SDIO send operation conditions')
        self.token, self.state = [], 'GET RESPONSE R4'

    def handle_cmd6(self):
        # CMD6 (SWITCH_FUNC) -> R1
        self.putc(6, 'Switch/check card function')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd7(self):
        # CMD7 (SELECT/DESELECT_CARD) -> R1b
        self.putc(7, 'Select / deselect card')
        rca = self.get_token_data(8, 23)
        self.puta(16, 31, [136, ['Relative card address 0x%X'%rca, 'Relative card address', 'RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd8(self):
        # CMD8 (SEND_IF_COND) -> R7
        self.puta(12, 31, [136, ['Reserved', 'Res', 'R']])
        self.puta(8, 11, [136, ['Supply voltage', 'Voltage', 'VHS', 'V']])
        self.puta(0, 7, [136, ['Check pattern', 'Check pat', 'Check', 'C']])
        self.putc(0, 'Send interface condition to card')
        self.token, self.state = [], 'GET RESPONSE R7'
        # TODO: Handle case when card doesn't reply with R7 (no reply at all).

    def handle_cmd9(self):
        # CMD9 (SEND_CSD) -> R2
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(9, 'Send card-specific data (CSD)')
        self.token, self.state = [], 'GET RESPONSE R2'

    def handle_cmd10(self):
        # CMD10 (SEND_CID) -> R2
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(9, 'Send card identification data (CID)')
        self.token, self.state = [], 'GET RESPONSE R2'

    def handle_cmd13(self):
        # CMD13 (SEND_STATUS) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(13, 'Send card status register')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd16(self):
        # CMD16 (SET_BLOCKLEN) -> R1
        self.blocklen = self.arg
        self.puta(0, 31, [136, ['Block length', 'Blocklen', 'BL', 'B']])
        self.putc(16, 'Set the block length to %d bytes' % self.blocklen)
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd52(self):
        # CMD52 (IO_RW_DIRECT) -> R5
        self.puta(31, 31, [136, ['R/W flag','Write','R/W','W']])
        self.puta(28, 30, [136, ['Funtion number','Function','FN','F']])
        self.puta(27, 27, [136, ['RAW flag','RAW','R']])
        self.puta(26, 26, [136, ['Stuff bit','Stuff','SB']])
        self.puta(9, 25, [136, ['Register address','Address','Addr','A']])
        self.puta(8, 8, [136, ['Stuff bit','Stuff','SB']])
        self.puta(0, 7, [136, ['Write data or stuff bits','Write data','Data','D']])
        self.putc(52, 'SDIO Read/Write Direct')
        self.puta(31, 31, [135, ['W' if self.arg&0x80000000 else 'R']])
        self.puta(28, 30, [135, [str((self.arg>>28)&7)]])
        self.puta(9, 25, [135, [hex((self.arg>>9)&0x1ffff)]])
        self.puta(0, 7, [135, [hex(self.arg&0xff)]])
        self.token, self.state = [], 'GET RESPONSE R5'

    def handle_cmd53(self):
        # CMD53 (IO_RW_EXTENDED) -> R5
        self.puta(31, 31, [136, ['R/W flag','Write','R/W','W']])
        self.puta(28, 30, [136, ['Funtion number','Function','FN','F']])
        self.puta(27, 27, [136, ['Block mode','Block','BM']])
        self.puta(26, 26, [136, ['OP code (increasing addr)','OP code','OP']])
        self.puta(9, 25, [136, ['Register address','Address','Addr','A']])
        self.puta(0, 8, [136, ['Byte/Block count','Count','C']])
        self.putc(52, 'SDIO Read/Write Extended')
        self.puta(31, 31, [135, ['W' if self.arg&0x80000000 else 'R']])
        self.puta(28, 30, [135, [str((self.arg>>28)&7)]])
        self.puta(9, 25, [135, [hex((self.arg>>9)&0x1ffff)]])
        self.puta(0, 8, [135, [hex(self.arg&0x1ff)]])
        self.token, self.state = [], 'GET RESPONSE R5'
        if not (self.arg & 0x08000000):
            #block mode
            self.data_bytes_required = self.arg&0x1ff
            self.data_crc_resp = (self.arg&0x80000000 !=0)
        else:
            #byte mode
            self.data_bytes_required = self.io_block_len
            self.data_crc_resp = (self.arg&0x80000000 !=0)

    def handle_cmd55(self):
        # CMD55 (APP_CMD) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(55, 'Next command is an application-specific command')
        self.is_acmd = True
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_acmd6(self):
        # ACMD6 (SET_BUS_WIDTH) -> R1
        self.putc(64 + 6, 'Read SD config register (SCR)')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_acmd13(self):
        # ACMD13 (SD_STATUS) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(64 + 13, 'Set SD status')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_acmd41(self):
        # ACMD41 (SD_SEND_OP_COND) -> R3
        self.puta(0, 23, [136, ['VDD voltage window', 'VDD volt', 'VDD', 'V']])
        self.puta(24, 24, [136, ['S18R']])
        self.puta(25, 27, [136, ['Reserved', 'Res', 'R']])
        self.puta(28, 28, [136, ['XPC']])
        self.puta(29, 29, [136, ['Reserved for eSD', 'Reserved', 'Res', 'R']])
        self.puta(30, 30, [136, ['Host capacity support info', 'Host capacity',
                                 'HCS', 'H']])
        self.puta(31, 31, [136, ['Reserved', 'Res', 'R']])
        self.putc(64 + 41, 'Send HCS info and activate the card init process')
        self.token, self.state = [], 'GET RESPONSE R3'

    def handle_acmd51(self):
        # ACMD51 (SEND_SCR) -> R1
        self.putc(64 + 51, 'Read SD config register (SCR)')
        self.token, self.state = [], 'GET RESPONSE R1'
        self.data_bytes_required = 8
        self.data_crc_resp = False

    def handle_cmd999(self):
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_acmd999(self):
        self.token, self.state = [], 'GET RESPONSE R1'

    # Response tokens can have one of four formats (depends on content).
    # They can have a total length of 48 or 136 bits.
    # They're sent serially (MSB-first) by the card that the host
    # addressed previously, or (synchronously) by all connected cards.

    def handle_response_r1(self, cmd):
        # R1: Normal response command
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (BCD; valid: 0-63)
        #  - Bits[39:08]: Card status
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.handle_common_token_fields()
        self.putr(55, 'R1')
        self.puta(0, 31, [136, ['Card status', 'Status', 'S']])
        for i in range(32):
            self.putbit(8 + i, [card_status[31 - i]])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r1b(self, cmd):
        # R1b: Same as R1 with an optional busy signal (on the data line)
        if not self.get_token_bits(cmd, 48):
            return
        self.handle_common_token_fields()
        self.puta(0, 31, [136, ['Card status', 'Status', 'S']])
        self.putr(55, 'R1b')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r2(self, cmd):
        # R2: CID/CSD register
        #  - Bits[135:135]: Start bit (always 0)
        #  - Bits[134:134]: Transmission bit (0 == card)
        #  - Bits[133:128]: Reserved (always 0b111111)
        #  - Bits[127:001]: CID or CSD register including internal CRC7
        #  - Bits[000:000]: End bit (always 1)
        if not self.get_token_bits(cmd, 136):
            return
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [128, ['%d' % self.token[bit][2]]])
        self.putf(0, 0, [129, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1][2] == 1 else 'card'
        self.putf(1, 1, [130, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [131, ['Reserved', 'Res', 'R']])
        self.putf(8, 134, [132, ['Argument', 'Arg', 'A']])
        self.putf(135, 135, [134, ['End bit', 'End', 'E']])
        self.putf(8, 134, [136, ['CID/CSD register', 'CID/CSD', 'C']])
        self.putf(0, 135, [55, ['R2']])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r3(self, cmd):
        # R3: OCR register
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Reserved (always 0b111111)
        #  - Bits[39:08]: OCR register
        #  - Bits[07:01]: Reserved (always 0b111111)
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.putr(55, 'R3')
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [128, ['%d' % self.token[bit][2]]])
        self.putf(0, 0, [129, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1][2] == 1 else 'card'
        self.putf(1, 1, [130, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [131, ['Reserved', 'Res', 'R']])
        self.putf(8, 39, [132, ['Argument', 'Arg', 'A']])
        self.putf(40, 46, [133, ['Reserved', 'Res', 'R']])
        self.putf(47, 47, [134, ['End bit', 'End', 'E']])
        self.puta(0, 31, [136, ['OCR register', 'OCR reg', 'OCR', 'O']])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r4(self, cmd):
        # R4: I/O OCR
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Reserved (always 0b111111)
        #  - Bits[39:39]: Card ready
        #  - Bits[38:36]: Number of I/O functions
        #  - Bits[35:35]: Memory present
        #  - Bits[34:33]: Stuff bits
        #  - Bits[32:32]: Switching to 1.8V accepted
        #  - Bits[31:08]: I/O operating conditions register
        #  - Bits[07:01]: Reserved (always 0b111111)
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.putr(55, 'R4')
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [128, ['%d' % self.token[bit][2]]])
        self.putf(0, 0, [129, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1][2] == 1 else 'card'
        self.putf(1, 1, [130, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [131, ['Reserved', 'Res', 'R']])
        self.putf(8, 39, [132, ['Argument', 'Arg', 'A']])
        self.putf(40, 46, [133, ['Reserved', 'Res', 'R']])
        self.putf(47, 47, [134, ['End bit', 'End', 'E']])
        self.puta(31, 31, [136, ['Card ready', 'ready', 'C']])
        self.puta(28, 30, [136, ['Number of I/O functions','n.o. I/O functions','NIF']])
        self.puta(27, 27, [136, ['Memory present','MP','M']])
        self.puta(25, 26, [136, ['Stuff bits','SB','S']])
        self.puta(24, 24, [136, ['Switching to 1.8V accepted','Switch to 1.8V','S18A']])
        self.puta(0, 23, [136, ['I/O operating conditions register','I/O OCR','OCR']])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r5(self, cmd):
        # R5:
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (always 0b000011)
        #  - Bits[39:24]: Stuff bits
        #  - Bits[23:16]: Response flags
        #  - Bits[15:08]: Read or write data
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.cal_arg()
        self.handle_common_token_fields()
        self.puta(0, 7, [136, ['Read or write data','Data','D']])
        self.puta(8, 15, [136, ['Response flags','Response','R']])
        self.puta(16,31, [136, ['Stuff bits','SB','S']])
        self.putr(55, 'R5')
        self.puta(0, 7, [135, [hex(self.arg&0xff)]])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r6(self, cmd):
        # R6: Published RCA response
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (always 0b000011)
        #  - Bits[39:24]: Argument[31:16]: New published RCA of the card
        #  - Bits[23:08]: Argument[15:0]: Card status bits
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.handle_common_token_fields()
        rca = self.get_token_data(8,23);
        self.puta(0, 15, [136, ['Card status bits', 'Status', 'S']])
        self.puta(16, 31, [136, ['Relative card address 0x%X' %rca, 'Relative card address', 'RCA', 'R']])
        self.putr(55, 'R6')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r7(self, cmd):
        # R7: Card interface condition
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (always 0b001000)
        #  - Bits[39:20]: Reserved bits (all-zero)
        #  - Bits[19:16]: Voltage accepted
        #  - Bits[15:08]: Echo-back of check pattern
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.handle_common_token_fields()

        self.putr(55, 'R7')

        # Arg[31:12]: Reserved bits (all-zero)
        self.puta(12, 31, [136, ['Reserved', 'Res', 'R']])

        # Arg[11:08]: Voltage accepted
        v = ''.join(str(i[2]) for i in self.token[28:32])
        av = accepted_voltages.get(int('0b' + v, 2), 'Unknown')
        self.puta(8, 11, [136, ['Voltage accepted: ' + av, 'Voltage', 'Volt', 'V']])

        # Arg[07:00]: Echo-back of check pattern
        self.puta(0, 7, [136, ['Echo-back of check pattern', 'Echo', 'E']])

        self.token, self.state = [], 'GET COMMAND TOKEN'

    def cal_arg(self):
        self.arg = 0
        for i in range(32):
            self.arg = (self.arg<<1)+self.token[i+8][2]

    def is_pending(self, pins):
        if self.four_line:
            return sum(pins[2:6])>=4
        else :
            return (pins[2] == 1)

    def get_data_start(self,pins):
        if self.data_received == [] :
            if not self.is_pending(pins):
                #still return false but store time data
                self.data_received = [[self.samplenum,1]]
            return False
        else :
            self.putdf( self.data_received[0][0], self.samplenum, ['Start of Data', 'Start', 'S'], True )
            self.data_received = [[self.samplenum,pins[2:6]]]
            self.data_state = 'DATA'
            return True

    def data_value_4bit(self, data_pins):
        return data_pins[3]*8+data_pins[2]*4+data_pins[1]*2+data_pins[0]*1

    def get_data_bytes(self, pins, bytes_required):
        self.data_received.append([self.samplenum, pins[2:6]])
        samples_required = bytes_required * 2 if self.four_line else bytes_required * 8
        if len(self.data_received) > samples_required:
            for i in range(bytes_required):
                if self.four_line:
                    value = (self.data_value_4bit(self.data_received[i*2][1])<<4) | self.data_value_4bit(self.data_received[i*2+1][1])
                    self.putd( self.data_received[i*2][0], self.data_received[(i+1)*2][0], [hex(value)] )
                else:
                    value = sum([self.data_received[i*8+j][1][0]<<(7-j) for j in range(8)])
                    self.putd( self.data_received[i*8][0], self.data_received[(i+1)*8][0], [hex(value)] )

            self.crc_value = []
            for i in (range(4) if self.four_line else (0,)):
                data = [self.data_received[j][1][i] for j in range(samples_required)]
                self.crc_value.append(crc16(data))
                #self.crc_value.append(data)
            self.data_received = [self.data_received[-1]]
            self.data_state = 'CRC'
            return True
        return False

    def get_crc_bytes(self, pins):
        self.data_received.append([self.samplenum, pins[2:6]])
        if len(self.data_received) > 17:
            crc_str = []
            crc_error = False
            for (i, crc_data) in enumerate(self.crc_value):
                value = sum([self.data_received[j][1][i]<<(15-j) for j in range(16)])
                if value == self.crc_value[i]:
                    crc_str.append(hex(crc_data))
                else:
                    crc_str.append(hex(value)+"("+hex(crc_data)+")")
                    crc_error = True
                #crc_str.append(str(crc_data))
            if crc_error:
                crc_str.insert(0, 'CRC Error:')
                self.putdf( self.data_received[0][0], self.data_received[-2][0], [' '.join(crc_str),'C Err'], False )
            else:
                crc_str.insert(0, 'CRC:')
                self.putdf( self.data_received[0][0], self.data_received[-2][0], [' '.join(crc_str),'C'], True )
            self.putdf( self.data_received[-2][0], self.data_received[-1][0], ['End','E'], True )

            if self.data_crc_resp:
                self.data_state = 'CARD_BUSY'
                self.data_received = [self.data_received[-1]]
            else:
                self.data_state = 'IDLE'
                self.data_received = []
            return True
        return False

    def wait_card_busy(self, pins):
        #format : <H><H><S><Status 3 bits><Busy-------><E>
        if len(self.data_received) != 7 or pins[2] == 1:
            self.data_received.append([self.samplenum, pins[2]])

        if len(self.data_received) == 9:
            self.putdf( self.data_received[2][0], self.data_received[3][0], ['Start','S'], True )
            status = [ data[1] for data in self.data_received[4:7] ]
            if status == [1,0,1]:
                self.putd( self.data_received[3][0], self.data_received[6][0], ['CRC Correct', 'Correct'] )
            elif status == [0,1,0]:
                self.putdf( self.data_received[3][0], self.data_received[6][0], ['CRC Error', 'Error','E'], False )
            else:
                self.putdf( self.data_received[3][0], self.data_received[6][0], ['Unknown Status', 'Unknown','U'], False )
            self.putdb( self.data_received[6][0], self.data_received[7][0], ['Card Busy', 'Busy','B'] )
            self.putdf( self.data_received[7][0], self.data_received[8][0], ['End','E'], True )
            self.data_state = 'IDLE'
            self.data_received = []
            return True
        return False

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:
            data.itercnt += 1
            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue

            (cmd, clk, dat0, dat1, dat2, dat3) = pins

            # Wait for a rising CLK edge.
            if self.oldclk == None:
                risedge = False
                negedge = False
            else:
                risedge = (self.oldclk == 0 and clk == 1)
                negedge = (self.oldclk == 1 and clk == 0)

            if not((risedge and self.rise_sample) or (negedge and not self.rise_sample)):
                self.oldclk = clk
                self.oldpins = pins
                continue
            self.oldclk = clk

            if self.sample_ahead and self.oldpins != None:
                pins, (cmd, clk, dat0, dat1, dat2, dat3) = self.oldpins, self.oldpins

            self.oldpins = pins

            #handle data lines
            if self.data_state == 'IDLE' or self.data_state == 'WAIT_FOR_START':
                self.get_data_start(pins)
            elif self.data_state == 'DATA':
                self.get_data_bytes(pins, self.data_bytes_required)
            elif self.data_state == 'CRC':
                self.get_crc_bytes(pins)
            elif self.data_state == 'CARD_BUSY':
                self.wait_card_busy(pins)


            # State machine.
            if self.state.startswith('GET RESPONSE'):
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd != 0:
                        continue
                    if not self.get_token_bits(cmd, 2):
                        continue
                elif len(self.token) < 2:
                    if not self.get_token_bits(cmd, 2):
                        continue
                    if self.token[1][2] == 1:
                        #is a command rather than a respond, jump to cmd state
                        self.state = 'GET COMMAND TOKEN'
                        continue
                else:
                    # Call the respective handler method for the response.
                    s = 'handle_response_%s' % self.state[13:].lower()
                    handle_response = getattr(self, s)
                    handle_response(cmd)
            else : #if self.state == 'GET COMMAND TOKEN':
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd != 0:
                        continue

                if not self.get_token_bits(cmd, 48):
                    continue
                # Command tokens (48 bits) are sent serially (MSB-first) by the host
                # (over the CMD line), either to one SD card or to multiple ones.
                #
                # Format:
                #  - Bits[47:47]: Start bit (always 0)
                #  - Bits[46:46]: Transmission bit (1 == host)
                #  - Bits[45:40]: Command index (BCD; valid: 0-63)
                #  - Bits[39:08]: Argument
                #  - Bits[07:01]: CRC7
                #  - Bits[00:00]: End bit (always 1)
                self.handle_common_token_fields()

                # Handle command.
                self.cmd_str = 'CMD%d (%s)' % (self.cmd, self.cmd_name(self.cmd))

                if not self.is_acmd:
                    # normal command
                    if self.cmd in self.cmd_list:
                        self.state = 'HANDLE CMD%d' % self.cmd
                        handle_cmd = getattr(self, 'handle_cmd' + str(self.cmd))
                    else:
                        self.state = 'HANDLE CMD999'
                        self.putc(self.cmd, 'CMD%d' % self.cmd)
                        handle_cmd = getattr(self, 'handle_cmd999')
                else:
                    # ACMD
                    self.cmd_str = 'A' + self.cmd_str
                    if self.cmd in self.acmd_list:
                        self.state = 'HANDLE ACMD%d' % self.cmd
                        handle_cmd = getattr(self, 'handle_acmd' + str(self.cmd))
                    else:
                        self.state = 'HANDLE ACMD999'
                        self.putc(self.cmd, 'ACMD%d' % self.cmd )
                        handle_cmd = getattr(self, 'handle_acmd999')

                self.data_state = 'WAIT_FOR_START'
                self.data_received = []
                self.data_bytes_required = 4  #default
                self.data_crc_resp = False
                self.cal_arg()

                # Call the respective handler method for the command.
                handle_cmd()
                # Leave ACMD mode again after the first command after CMD55.
                if self.is_acmd and not self.cmd in (55, 63):
                    self.is_acmd = False

