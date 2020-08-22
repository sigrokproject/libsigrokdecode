##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2015 Uwe Hermann <uwe@hermann-uwe.de>
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
from common.emmc import (cmd_names, accepted_voltages, device_status, sd_status)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'emmc_sd'
    name = 'eMMC (SD mode)'
    longname = 'Embedded Multimedia card (SD mode)'
    desc = 'Embedded Multimedia card (SD mode) low-level protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Memory']
    channels = (
        {'id': 'cmd',  'name': 'CMD',  'desc': 'Command'},
        {'id': 'clk',  'name': 'CLK',  'desc': 'Clock'},
    )

    annotations = \
        tuple(('cmd%d' % i, 'CMD%d' % i) for i in range(64)) + ( \
        ('bits', 'Bits'),
        ('field-start', 'Start bit'),
        ('field-transmission', 'Transmission bit'),
        ('field-cmd', 'Command'),
        ('field-arg', 'Argument'),
        ('field-crc', 'CRC'),
        ('field-end', 'End bit'),
        ('decoded-bits', 'Decoded bits'),
        ('decoded-fields', 'Decoded fields'),
    )
    annotation_rows = (
        ('raw-bits', 'Raw bits', (128,)),
        ('decoded-bits', 'Decoded bits', (135,)),
        ('decoded-fields', 'Decoded fields', (136,)),
        ('fields', 'Fields', tuple(range(129, 135))),
        ('cmd', 'Commands', tuple(range(128))),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'GET COMMAND TOKEN'
        self.token = []
        self.cmd = None
        self.last_cmd = None
        self.arg = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putbit(self, b, data):
        self.put(self.token[b][0], self.token[b][1], self.out_ann, [135, data])

    def putt(self, data):
        self.put(self.token[0][0], self.token[47][1], self.out_ann, data)

    def putf(self, s, e, data):
        self.put(self.token[s][0], self.token[e][1], self.out_ann, data)

    def puta(self, s, e, data):
        self.put(self.token[47 - 8 - e][0], self.token[47 - 8 - s][1],
                 self.out_ann, data)

    def putc(self, cmd, desc):
        self.last_cmd = cmd
        self.putt([cmd, ['%s: %s' % (self.cmd_str, desc), self.cmd_str,
                         self.cmd_str.split(' ')[0]]])

    def putr(self, desc):
        self.putt([self.last_cmd, ['Reply: %s' % desc]])

    def cmd_name(self, cmd):
        c = cmd_names
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

    def handle_common_token_fields(self):
        s = self.token

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
        self.arg = int('0b' + ''.join([str(s[i][2]) for i in range(8, 40)]), 2)
        self.putf(8, 39, [132, ['Argument: 0x%08x' % self.arg, 'Arg', 'A']])

        # CMD[07:01]: CRC7
        self.crc = int('0b' + ''.join([str(s[i][2]) for i in range(40, 47)]), 2)
        self.putf(40, 46, [133, ['CRC: 0x%x' % self.crc, 'CRC', 'C']])

        # CMD[00:00]: End bit (always 1)
        self.putf(47, 47, [134, ['End bit', 'End', 'E']])

    def get_command_token(self, cmd):
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

        if not self.get_token_bits(cmd, 48):
            return

        self.handle_common_token_fields()

        # Handle command.
        s = 'CMD'
        self.cmd_str = '%s%d (%s)' % (s, self.cmd, self.cmd_name(self.cmd))
        if self.cmd in (0, 2, 3, 6, 7, 8, 9, 10, 13, 41, 51, 55):
            self.state = 'HANDLE CMD%d' % self.cmd
        else:
            self.state = 'HANDLE CMD999'
            self.putc(self.cmd, '%s%d' % (s, self.cmd))

    def handle_cmd0(self):
        # CMD0 (GO_IDLE_STATE) -> no response
        self.puta(0, 31, [136, ['IDLE_STATE', 'IDLE', 'ID', 'I']])
        self.putc(0, 'Reset Device to IDLE_STATE')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_cmd1(self):
        # CMD1 (SEND_OCR_IN_IDLE) -> R3
        self.puta(0, 31, [136, ['OCR_WO_BUSY', 'OCR']])
        self.putc(1, 'Send OCR in idle state')
        self.token, self.state = [], 'GET RESPONSE R3'

    def handle_cmd2(self):
        # CMD2 (ALL_SEND_CID) -> R2
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(2, 'Ask card for CID number')
        self.token, self.state = [], 'GET RESPONSE R2'

    def handle_cmd3(self):
        # CMD3 (SET_RELATIVE_ADDR) -> R1
        self.puta(16, 31, [136, ['Set Relative Card Addr', 'Set RCA', "SRCA", "SR"]])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(3, 'Set relative card address (RCA)')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd4(self):
        # CMD4 (SET_DSR) -> no response
        self.puta(16, 31, [136, ['Set DSR', 'SDSR']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(4, 'Programs the DSR of the Device')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_cmd5(self):
        # CMD5 (SLEEP_AWAKE) ->R1b
        self.puta(16, 31, [136, ['Set DSR', 'SDSR']])
        self.puta(15, 15, [136, ['Sleep/Awake', 'S/A']])
        self.puta(0, 14, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(5, 'Sleep/Awake')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd6(self):
        # CMD6 (SWITCH_FUNC) -> R1b
        self.puta(26, 31, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(24, 25, [136, ['Access', 'A']])
        self.puta(16, 23, [136, ['Index', 'Id']])
        self.puta(8, 15, [136, ['Value', 'Val', 'V']])
        self.puta(3, 7, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(0, 2, [136, ['CMD Set', 'CMD S']])
        self.putc(6, 'Switch card function')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd7(self):
        # CMD7 (SELECT/DESELECT_CARD) -> R1b
        self.putc(7, 'Select / deselect card')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd8(self):
        # CMD8 (SEND_EXT_CSD) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(8, 'Device sends its EXT_CSD register as a block of data')
        self.token, self.state = [], 'GET RESPONSE R1'

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
        self.putc(10, 'Send card identification data (CID)')
        self.token, self.state = [], 'GET RESPONSE R2'

    def handle_cmd12(self):
        # CMD13 (SEND_STATUS) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(1, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [136, ['HPI']])
        self.putc(12, 'Forces the Device to stop transmission')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd13(self):
        # CMD13 (SEND_STATUS) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(15, 15, [136, ['SQS']])
        self.puta(1, 14, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [136, ['HPI']])
        self.putc(13, 'Send card status register')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd14(self):
        # CMD14 (BUSTEST_R) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(14, 'Host Bus Test read from Device')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd15(self):
        # CMD15 (GO_INACTIVE_STATE) -> No response
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(15, 'Set Device at RCA to Inactive State')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_cmd16(self):
        # CMD16 (SET_BLOCKLEN) -> R1
        self.puta(0, 31, [136, ['Block length', 'Blocklen', 'BL', 'B']])
        self.putc(16, 'Read the block length to %d bytes' % self.arg)
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd17(self):
        # CMD16 (READ_SINGLE_BLOCK) -> R1
        self.puta(0, 31, [136, ['Data Address', 'Dat Addr', 'DADD', 'DA']])
        self.putc(17, 'Read a block of data set by SET_BLOCKLEN')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd18(self):
        # CMD18 (READ_MULTIPLE_BLOCK) -> R1
        self.puta(0, 31, [136, ['Data Address', 'Dat Addr', 'DADD', 'DA']])
        self.putc(18, 'Read Multiple blocks of data set by SET_BLOCKLEN')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd19(self):
        # CMD19 (BUSTEST_W) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(19, 'Host Bus Test Wrtie to Device')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd21(self):
        # CMD21 (READ_MULTIPLE_BLOCK) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(21, '128 clocks of tuning pattern for HS200')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd23(self):
        # CMD23 (SET_BLOCK_COUNT) -> R1
        self.puta(30, 30, [136, ['Packed']])
        if self.token[30] == 1:
            self.puta(31, 31, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
            self.puta(16, 29, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
        else:
            self.puta(31, 31, [136, ['Reliable Write', 'RLB W']])
            self.puta(25, 28, [136, ['Context ID', 'CntxtID']])
            self.puta(24, 24, [136, ['Forced Programming', 'Forced Prog', 'FP']])
            self.puta(16, 23, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])

        self.puta(0, 15, [136, ['Number of Blocks', 'NUM BLK', 'NoB']])
        self.putc(23, 'Defines the number of blocks')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd24(self):
        # CMD24 (WRITE_BLOCK) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(24, 'Writes a block of Data')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd25(self):
        # CMD25 (WRITE_MULTIPLE_BLOCK) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(25, 'Writes multiple blocks of Data')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd26(self):
        # CMD26 (PROGRAM_CID) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(26, 'Programming of the Device identification register')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd27(self):
        # CMD27 (PROGRAM_CSD) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(27, 'Programming of the programmable bits of the CSD')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd28(self):
        # CMD28 (SET_WRITE_PROT) -> R1b
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(28, 'Set Write Protect or Release address group')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd29(self):
        # CMD29 (CLR_WRITE_PROT) -> R1b
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(29, 'Clear Write Protect or Ignored')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd30(self):
        # CMD30 (SEND_WRITE_PROT) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(30, 'Send status of Write Protect or released group')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd31(self):
        # CMD31 (SEND_WRITE_PROT_TYPE) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(31, 'Send type of Write Protect or 64bit 0s')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd35(self):
        # CMD35 (ERASE_GROUP_START) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(35, 'Set Address of the 1st erase group')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd36(self):
        # CMD36 (ERASE_GROUP_END) -> R1
        self.puta(0, 31, [136, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc(36, 'Set Address of the last erase group')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd38(self):
        # CMD38 (ERASE_GROUP_END) -> R1
        self.puta(31, 31, [136, ['Secure Request', 'Sec Req', 'SR']])
        self.puta(16, 30, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(15, 15, [136, ['Force Garbage Collect', 'F Garb Clct', 'FGC']])
        self.puta(2, 14, [136, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(1, 1, [136, ['Discard Enable', 'DISG EN', 'DE']])
        self.puta(0, 0, [136, ['TRIM Enable', 'TRIM EN', 'TE']])
        self.putc(38, 'Erase all groups defined by CMD35/36')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd39(self):
        # CMD39 (FAST_IO) -> R4
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(15, 15, [136, ['Write Flag', 'W Flag', 'WF', 'W']])
        self.puta(8, 14, [136, ['Register Addr', 'REGADD', 'RA']])
        self.puta(0, 7, [136, ['Register Data', 'REGDAT', 'DAT', 'D']])
        self.putc(39, 'R/W 8 bit (register) data fields')
        self.token, self.state = [], 'GET RESPONSE R4'

    def handle_cmd40(self):
        # CMD40 (GO_IRQ_STATE) -> R5
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(40, 'Sets the system into interrupt mode')
        self.token, self.state = [], 'GET RESPONSE R5'

    def handle_cmd42(self):
        # CMD42 (LOCK_UNLOCK) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(42, 'set/reset the password or lock/unlock the Device')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd44(self):
        # CMD44 (QUEUED_TASK_PARAMS) -> R1
        self.puta(31, 31, [136, ['Reliable Write Request', 'RWR']])
        self.puta(30, 30, [136, ['Data Direction(1:R/0:W)', 'DD']])
        self.puta(29, 29, [136, ['Tag request', 'Tag Req', 'TR']])
        self.puta(25, 28, [136, ['Context ID', 'CntxtID']])
        self.puta(24, 24, [136, ['Forced Programming', 'F Prog', 'FP']])
        self.puta(23, 23, [136, ['Priority(0:Simple/1:High)', 'Prio']])
        self.puta(21, 22, [136, ['Reserved', 'RSVD']])
        self.puta(16, 20, [136, ['Task ID', 'TID']])
        self.puta(0, 15, [136, ['Block Numbers', 'Blk NUM']])
        self.putc(44, 'Def data dir for R/W, Priority, Task ID, blk count for qd Task')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd45(self):
        # CMD45 (QUEUED_TAKS_ADDRESS) -> R1
        self.puta(0, 31, [136, ['Start of block address', 'Start BLK ADDR', 'SBA', 'SA']])
        self.putc(45, 'Defines the block address of queued task')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd46(self):
        # CMD46 (EXECUTE_READ_TASK) -> R1
        self.puta(21, 31, [136, ['Reserved', 'RSVD']])
        self.puta(16, 20, [136, ['Task ID', 'TID']])
        self.puta(0, 15, [136, ['Reserved', 'RSVD']])
        self.putc(46, 'execute task from the queue with TID')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd47(self):
        # CMD42 (EXECUTE_WRITE_TASK) -> R1
        self.puta(21, 31, [136, ['Reserved', 'RSVD']])
        self.puta(16, 20, [136, ['Task ID', 'TID']])
        self.puta(0, 15, [136, ['Reserved', 'RSVD']])
        self.putc(47, 'execute task from the queue with TID')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd48(self):
        # CMD48 (CMDQ_TASK_MGMT) -> R1b
        self.puta(21, 31, [136, ['Reserved', 'RSVD']])
        self.puta(16, 20, [136, ['Task ID', 'TID']])
        self.puta(4, 15, [136, ['Reserved', 'RSVD']])
        self.puta(0, 3, [136, ['TM Op-code', 'TMOP']])
        self.putc(48, 'discard a specific task or entire queue')
        self.token, self.state = [], 'GET RESPONSE R1b'

    def handle_cmd49(self):
        # CMD49 (SET_TIME) -> R1
        self.puta(0, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(49, 'Sets the real time clock according to the RTC')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd53(self):
        # CMD53 (PROTOCOL_RD) -> R1
        self.puta(16, 31, [136, ['Security Protolcol Specific', 'Sec P Spec', 'SPS']])
        self.puta(8, 15, [136, ['Security Protolcol', 'Sec P', 'SP']])
        self.puta(0, 7, [136, ['Reserved', 'RSVD']])
        self.putc(53, 'Transfer 512B Blk from device to host')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd54(self):
        # CMD54 (PROTOCOL_WR) -> R1
        self.puta(16, 31, [136, ['Security Protolcol Specific', 'Sec P Spec', 'SPS']])
        self.puta(8, 15, [136, ['Security Protolcol', 'Sec P', 'SP']])
        self.puta(0, 7, [136, ['Reserved', 'RSVD']])
        self.putc(54, 'Transfer 512B Blk from host to device')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd55(self):
        # CMD55 (APP_CMD) -> R1
        self.puta(16, 31, [136, ['RCA', 'R']])
        self.puta(0, 15, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(55, 'Next command is an application-specific command')
        self.token, self.state = [], 'GET RESPONSE R1'

    def handle_cmd56(self):
        # CMD55 (GEN_CMD) -> R1
        self.puta(1, 31, [136, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [136, ['RD/WR1', 'Stuff', 'SB', 'S']])
        self.putc(56, 'R/W a data block from/to the Device')
        self.token, self.state = [], 'GET RESPONSE R1'


    def handle_cmd999(self):
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
        self.putr('R1')
        self.puta(0, 31, [136, ['Card status', 'Status', 'S']])
        for i in range(32):
            self.putbit(8 + i, [device_status[31 - i]])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r1b(self, cmd):
        # R1b: Same as R1 with an optional busy signal (on the data line)
        if not self.get_token_bits(cmd, 48):
            return
        self.handle_common_token_fields()
        self.puta(0, 31, [136, ['Card status', 'Status', 'S']])
        self.putr('R1b')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r2(self, cmd):
        # R2: CID/CSD register
        #  - Bits[135:135]: Start bit (always 0)
        #  - Bits[134:134]: Transmission bit (0 == card)
        #  - Bits[133:128]: Check bits (always 0b111111)
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
        self.putf(2, 7, [131, ['Check Bits', 'CHECK', 'C']])
        self.putf(8, 134, [132, ['Argument', 'Arg', 'A']])
        self.putf(135, 135, [134, ['End bit', 'End', 'E']])
        self.putf(8, 134, [136, ['CID/CSD register', 'CID/CSD', 'C']])
        self.putf(0, 135, [55, ['R2']])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r3(self, cmd):
        # R3: OCR register
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Check bits (always 0b111111)
        #  - Bits[39:08]: OCR register
        #  - Bits[07:01]: Check bits (always 0b111111)
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 48):
            return
        self.putr('R3')
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [128, ['%d' % self.token[bit][2]]])
        self.putf(0, 0, [129, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1][2] == 1 else 'card'
        self.putf(1, 1, [130, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [131, ['Check bits', 'CHECK', 'C']])
        self.putf(8, 39, [132, ['Argument', 'Arg', 'A']])
        self.putf(40, 46, [133, ['Check bits', 'CHECK', 'C']])
        self.putf(47, 47, [134, ['End bit', 'End', 'E']])
        self.puta(0, 31, [136, ['OCR register', 'OCR reg', 'OCR', 'O']])
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r4(self, cmd):
        # R4: Published RCA response
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (always 0b100011)
        #  - Bits[39:24]: Argument[31:16]: New published RCA of the card
        #  - Bits[23:08]: Argument[15:0]: Card status bits
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 39):
            return
        self.handle_common_token_fields()
        self.puta(0, 15, [136, ['Card status bits', 'Status', 'S']])
        self.puta(16, 31, [136, ['Relative card address', 'RCA', 'R']])
        self.putr('R4')
        self.token, self.state = [], 'GET COMMAND TOKEN'

    def handle_response_r5(self, cmd):
        # R5: Card interface condition
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == card)
        #  - Bits[45:40]: Command index (always 0b101000)
        #  - Bits[39:24]: Reserved bits (all-zero)
        #  - Bits[23:08]: Not Defined
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd, 40):
            return
        self.handle_common_token_fields()

        self.putr('R5')

        # Arg[31:16]: RCA
        self.puta(16, 31, [136, ['RCA']])

        # Arg[15:00]: Echo-back of check pattern
        self.puta(0, 15, [136, ['Not Defined/IRQ data', 'NDEF']])

        self.token, self.state = [], 'GET COMMAND TOKEN'

    def decode(self):
        while True:
            # Wait for a rising CLK edge.
            (cmd, clk) = self.wait({1: 'r'})

            # State machine.
            if self.state == 'GET COMMAND TOKEN':
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd != 0:
                        continue
                self.get_command_token(cmd)
            elif self.state.startswith('HANDLE CMD'):
                # Call the respective handler method for the command.
                cmdstr = self.state[10:].lower()
                handle_cmd = getattr(self, 'handle_cmd%s' % (cmdstr))
                handle_cmd()
            elif self.state.startswith('GET RESPONSE'):
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd != 0:
                        continue
                # Call the respective handler method for the response.
                s = 'handle_response_%s' % self.state[13:].lower()
                handle_response = getattr(self, s)
                handle_response(cmd)
