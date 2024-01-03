##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2015-2020 Uwe Hermann <uwe@hermann-uwe.de>
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
from common.srdhelper import SrdIntEnum, SrdStrEnum
from common.emmc import (cmd_names, acmd_names, accepted_voltages, device_current_state)

responses = '1 1b 2 3 4 5'.split()
token_fields = 'START TRANSMISSION CMD ARG CRC END'.split()
reg_device_status = 'OUT_OF_RANGE ADDRESS_MISALIGN BLOCK_LEN_ERROR ERASE_SEQ_ERROR \
    ERASE_PARAM WP_VIOLATION DEVICE_IS_LOCKED LOCK_UNLOCK_FAILED COM_CRC_ERROR \
    ILLEGAL_COMMAND DEVICE_ECC_FAILED CC_ERROR ERROR OBS_HOST_IGNORE_18 OBS_HOST_IGNORE_17 \
    CID_CSD_OVERWRITE WP_ERASE_SKIP RSVD_14 ERASE_RESET CURRENT_STATE \
    READY_FOR_DATA SWITCH_ERROR EXCEPTION_EVENT APP_CMD RSVD_4 RSVD_APP_CMD \
    RSVD_TESTMODE'.split()
reg_cid = 'MID RSVD CBX OID PNM PRV PSN MDT CRC ONE'.split()
reg_csd = 'CSD_STRUCTURE SPEC_VERS RSVD TAAC NSAC TRAN_SPEED CCC READ_BL_LEN \
    READ_BL_PARTIAL WRITE_BLK_MISALIGN READ_BLK_MISALIGN DSR_IMP C_SIZE \
    VDD_R_CURR_MIN VDD_R_CURR_MAX VDD_W_CURR_MIN VDD_W_CURR_MAX C_SIZE_MULT \
    ERASE_GRP_SIZE ERASE_GRP_MULT WP_GRP_SIZE WP_GRP_ENABLE DEFAULT_ECC R2W_FACTOR \
    WRITE_BL_LEN WRITE_BL_PARTIAL CONTENT_PROT_APP FILE_FORMAT_GRP COPY  \
    PERM_WRITE_PROTECT TMP_WRITE_PROTECT FILE_FORMAT ECC CRC ONE'.split()

Pin = SrdIntEnum.from_str('Pin', 'CMD CLK DAT0 DAT1 DAT2 DAT3')

a = ['CMD%d' % i for i in range(64)] + ['ACMD%d' % i for i in range(64)] + \
    ['RESPONSE_R' + r.upper() for r in responses] + \
    ['R_STATUS_' + r for r in reg_device_status] + \
    ['R_CID_' + r for r in reg_cid] + \
    ['R_CSD_' + r for r in reg_csd] + \
    ['BIT_' + r for r in ('0', '1')] + \
    ['F_' + f for f in token_fields] + \
    ['DECODED_BIT', 'DECODED_F']
Ann = SrdIntEnum.from_list('Ann', a)

s = ['GET_COMMAND_TOKEN', 'HANDLE_CMD999'] + \
    ['HANDLE_CMD%d' % i for i in range(64)] + \
    ['HANDLE_ACMD%d' % i for i in range(64)] + \
    ['GET_RESPONSE_R%s' % r.upper() for r in responses]
St = SrdStrEnum.from_list('St', s)

class Bit:
    def __init__(self, s, e, b):
        self.ss, self.es, self.bit = s, e ,b

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
    optional_channels = (
        {'id': 'dat0', 'name': 'DAT0', 'desc': 'Data pin 0'},
        {'id': 'dat1', 'name': 'DAT1', 'desc': 'Data pin 1'},
        {'id': 'dat2', 'name': 'DAT2', 'desc': 'Data pin 2'},
        {'id': 'dat3', 'name': 'DAT3', 'desc': 'Data pin 3'},
    )
    annotations = \
        tuple(('cmd%d' % i, 'CMD%d' % i) for i in range(64)) + \
        tuple(('acmd%d' % i, 'ACMD%d' % i) for i in range(64)) + \
        tuple(('response_r%s' % r, 'R%s' % r) for r in responses) + \
        tuple(('reg_status_' + r.lower(), 'Status: ' + r) for r in reg_device_status) + \
        tuple(('reg_cid_' + r.lower(), 'CID: ' + r) for r in reg_cid) + \
        tuple(('reg_csd_' + r.lower(), 'CSD: ' + r) for r in reg_csd) + \
        tuple(('bit_' + r, 'Bit ' + r) for r in ('0', '1')) + \
        tuple(('field-' + r.lower(), r) for r in token_fields) + \
    ( \
        ('decoded-bit', 'Decoded bit'),
        ('decoded-field', 'Decoded field'),
    )
    annotation_rows = (
        ('raw-bits', 'Raw bits', Ann.prefixes('BIT_')),
        ('decoded-bits', 'Decoded bits', (Ann.DECODED_BIT,) + Ann.prefixes('R_')),
        ('decoded-fields', 'Decoded fields', (Ann.DECODED_F,)),
        ('fields', 'Fields', Ann.prefixes('F_')),
        ('commands', 'Commands', Ann.prefixes('CMD ACMD RESPONSE_')),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = St.GET_COMMAND_TOKEN
        self.token = []
        self.is_acmd = False # Indicates CMD vs. ACMD
        self.cmd = None
        self.last_cmd = None
        self.arg = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putt(self, data):
        self.put(self.token[0].ss, self.token[47].es, self.out_ann, data)

    def putf(self, s, e, data):
        self.put(self.token[s].ss, self.token[e].es, self.out_ann, data)

    def puta(self, s, e, data):
        self.put(self.token[47 - 8 - e].ss, self.token[47 - 8 - s].es,
                 self.out_ann, data)

    def putc(self, desc):
        cmd = Ann.ACMD0 + self.cmd if self.is_acmd else self.cmd
        self.last_cmd = cmd
        self.putt([cmd, ['%s: %s' % (self.cmd_str, desc), self.cmd_str,
                         self.cmd_str.split(' ')[0]]])

    def putr(self, r):
        self.putt([r, ['Response: %s' % r.name.split('_')[1]]])

    def cmd_name(self, cmd):
        c = acmd_names if self.is_acmd else cmd_names
        return c.get(cmd, 'Unknown')

    def get_token_bits(self, cmd_pin, n):
        # Get a bit, return True if we already got 'n' bits, False otherwise.
        self.token.append(Bit(self.samplenum, self.samplenum, cmd_pin))
        if len(self.token) > 0:
            self.token[len(self.token) - 2].es = self.samplenum
        if len(self.token) < n:
            return False
        self.token[n - 1].es += self.token[n - 1].ss - self.token[n - 2].ss
        return True

    def handle_common_token_fields(self):
        s = self.token

        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [Ann.BIT_0 + s[bit].bit, ['%d' % s[bit].bit]])

        # CMD[47:47]: Start bit (always 0)
        self.putf(0, 0, [Ann.F_START, ['Start bit', 'Start', 'S']])

        # CMD[46:46]: Transmission bit (1 == host)
        t = 'host' if s[1].bit == 1 else 'device'
        self.putf(1, 1, [Ann.F_TRANSMISSION, ['Transmission: ' + t, 'T: ' + t, 'T']])

        # CMD[45:40]: Command index (BCD; valid: 0-63)
        self.cmd = int('0b' + ''.join([str(s[i].bit) for i in range(2, 8)]), 2)
        c = '%s (%d)' % (self.cmd_name(self.cmd), self.cmd)
        self.putf(2, 7, [Ann.F_CMD, ['Command: ' + c, 'Cmd: ' + c,
                               'CMD%d' % self.cmd, 'Cmd', 'C']])

        # CMD[39:08]: Argument
        self.arg = int('0b' + ''.join([str(s[i].bit) for i in range(8, 40)]), 2)
        self.putf(8, 39, [Ann.F_ARG, ['Argument: 0x%08x' % self.arg, 'Arg', 'A']])

        # CMD[07:01]: CRC7
        self.crc = int('0b' + ''.join([str(s[i].bit) for i in range(40, 47)]), 2)
        self.putf(40, 46, [Ann.F_CRC, ['CRC: 0x%x' % self.crc, 'CRC', 'C']])

        # CMD[00:00]: End bit (always 1)
        self.putf(47, 47, [Ann.F_END, ['End bit', 'End', 'E']])

    def get_command_token(self, cmd_pin):
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

        if not self.get_token_bits(cmd_pin, 48):
            return

        self.handle_common_token_fields()

        # Handle command.
        s = 'ACMD' if self.is_acmd else 'CMD'
        self.cmd_str = '%s%d (%s)' % (s, self.cmd, self.cmd_name(self.cmd))
        if hasattr(self, 'handle_%s%d' % (s.lower(), self.cmd)):
            self.state = St['HANDLE_CMD%d' % self.cmd]
        else:
            self.state = St.HANDLE_CMD999
            self.putc('%s%d' % (s, self.cmd))

    def handle_cmd0(self):
        # CMD0 (GO_IDLE_STATE) -> no response
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Reset all Devices')
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_cmd1(self):
        # CMD1 (SEND_OP_COND) -> R3
        self.puta(0, 31, [Ann.DECODED_F, ['OCR_WO_BUSY', 'OCR', 'O']])
        self.putc('Ask Device for OCR (in idle state)')
        self.token, self.state = [], St.GET_RESPONSE_R3

    def handle_cmd2(self):
        # CMD2 (ALL_SEND_CID) -> R2
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Ask Device for CID number')
        self.token, self.state = [], St.GET_RESPONSE_R2

    def handle_cmd3(self):
        # CMD3 (SEND_RELATIVE_ADDR) -> R1
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'RCA']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Assigns relative address (RCA) to the Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd4(self):
        # CMD4 (SET_DSR) -> no response
        self.puta(16, 31, [Ann.DECODED_F, ['DSR', 'DSR']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(4, 'Programs the DSR of the Device')
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_cmd5(self):
        # CMD5 (SLEEP_AWAKE) -> R1b
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'RCA']])
        self.puta(15, 15, [Ann.DECODED_F, ['Sleep/Awake', 'S/A']])
        self.puta(0, 14, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc(5, 'Sleep / Awake')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd6(self):
        # CMD6 (SWITCH_FUNC) -> R1b
        self.puta(26, 31, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(24, 25, [Ann.DECODED_F, ['Access', 'A']])
        self.puta(16, 23, [Ann.DECODED_F, ['Index', 'Id']])
        self.puta(8, 15, [Ann.DECODED_F, ['Value', 'Val', 'V']])
        self.puta(3, 7, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(0, 2, [Ann.DECODED_F, ['CMD Set', 'CMD S']])
        self.putc('Switch / check Device function')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd7(self):
        # CMD7 (SELECT/DESELECT_CARD) -> R1/R1b
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'RCA']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Select / deselect Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd8(self):
        # CMD8 (SEND_EXT_CSD) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Device sends its EXT_CSD register as a block of data')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd9(self):
        # CMD9 (SEND_CSD) -> R2
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Addressed Device sends its Device-specific data (CSD)')
        self.token, self.state = [], St.GET_RESPONSE_R2

    def handle_cmd10(self):
        # CMD10 (SEND_CID) -> R2
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Addressed Device sends its Device identification (CID)')
        self.token, self.state = [], St.GET_RESPONSE_R2

    def handle_cmd12(self):
        # CMD13 (STOP_TRANSMISSION) -> R1/R1b
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(1, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [Ann.DECODED_F, ['HPI']])
        self.putc('Forces the Device to stop transmission')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd13(self):
        # CMD13 (SEND_STATUS) -> R1
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(15, 15, [Ann.DECODED_F, ['SQS']])
        self.puta(1, 14, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [Ann.DECODED_F, ['HPI']])
        self.putc('Addressed Device sends its status register')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd14(self):
        # CMD14 (BUSTEST_R) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Read the reversed bus testing data pattern from a Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd15(self):
        # CMD15 (GO_INACTIVE_STATE) -> No response
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Set Device at RCA to Inactive State')
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_cmd16(self):
        # CMD16 (SET_BLOCKLEN) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Block length', 'Blocklen', 'BL', 'B']])
        self.putc('Set the block length to %d bytes' % self.arg)
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd17(self):
        # CMD16 (READ_SINGLE_BLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'Dat Addr', 'DAdd', 'DA']])
        self.putc('Read a block of data set by SET_BLOCKLEN')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd18(self):
        # CMD18 (READ_MULTIPLE_BLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'Dat Addr', 'DAdd', 'DA']])
        self.putc('Read Multiple blocks of data set by SET_BLOCKLEN')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd19(self):
        # CMD19 (BUSTEST_W) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('A host sends the bus test data pattern to a Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd21(self):
        # CMD21 (SEND_TUNING_ BLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('128 clocks of tuning pattern for HS200')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd23(self):
        # CMD23 (SET_BLOCK_COUNT) -> R1
        self.puta(30, 30, [Ann.DECODED_F, ['Packed']])
        if self.token[30] == 1:
            self.puta(31, 31, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
            self.puta(16, 29, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
        else:
            self.puta(31, 31, [Ann.DECODED_F, ['Reliable Write', 'RLB W']])
            self.puta(29, 29, [Ann.DECODED_F, ['Tag request', 'TagReq']])
            self.puta(25, 28, [Ann.DECODED_F, ['Context ID', 'CntxtID']])
            self.puta(24, 24, [Ann.DECODED_F, ['Forced Programming', 'Forced Prog', 'FP']])
            self.puta(16, 23, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])

        self.puta(0, 15, [Ann.DECODED_F, ['Number of Blocks', 'NUM BLK', 'NoB']])
        self.putc('Defines the number of blocks')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd24(self):
        # CMD24 (WRITE_BLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc('Writes a block of the size selected by SET_BLOCKLEN')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd25(self):
        # CMD25 (WRITE_MULTIPLE_BLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAT ADDR', 'DA']])
        self.putc('Writes multiple blocks of data')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd26(self):
        # CMD26 (PROGRAM_CID) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Programming of the Device identification register (CID)')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd27(self):
        # CMD27 (PROGRAM_CSD) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Programming of the programmable bits of the CSD')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd28(self):
        # CMD28 (SET_WRITE_PROT) -> R1b
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAddr', 'DA']])
        self.putc('Set Write Protect or Release address group')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd29(self):
        # CMD29 (CLR_WRITE_PROT) -> R1b
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAddr', 'DA']])
        self.putc('Clear Write Protect or Ignored')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd30(self):
        # CMD30 (SEND_WRITE_PROT) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Write Protect Data Address', 'WrProtDAddr', 'WPDA']])
        self.putc('Send status of Write Protect or released group')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd31(self):
        # CMD31 (SEND_WRITE_PROT_TYPE) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Write Protect Data Address', 'WrProtDAddr', 'DA']])
        self.putc('Send type of Write Protect or 64bit 0s')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd35(self):
        # CMD35 (ERASE_GROUP_START) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAddr', 'DA']])
        self.putc('Set Address of the 1st erase group')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd36(self):
        # CMD36 (ERASE_GROUP_END) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Data Address', 'DAddr', 'DA']])
        self.putc('Set Address of the last erase group')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd38(self):
        # CMD38 (ERASE) -> R1b
        self.puta(31, 31, [Ann.DECODED_F, ['Secure Request', 'Sec Req', 'SR']])
        self.puta(16, 30, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(15, 15, [Ann.DECODED_F, ['Force Garbage Collect', 'F Garb Clct', 'FGC']])
        self.puta(2, 14, [Ann.DECODED_F, ['Set to 0', 'Set 0', 'S0', 'Z']])
        self.puta(1, 1, [Ann.DECODED_F, ['Discard Enable', 'DISG EN', 'DE']])
        self.puta(0, 0, [Ann.DECODED_F, ['TRIM Enable', 'TRIM EN', 'TE']])
        self.putc('Erase all write blocks defined by CMD35/36')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd39(self):
        # CMD39 (FAST_IO) -> R4
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(15, 15, [Ann.DECODED_F, ['Register Write Flag', 'Reg W Flag', 'RWF', 'W']])
        self.puta(8, 14, [Ann.DECODED_F, ['Register Addr', 'RegAdd', 'RA']])
        self.puta(0, 7, [Ann.DECODED_F, ['Register Data', 'RegDat', 'DAT', 'D']])
        self.putc('R/W 8 bit (register) data fields')
        self.token, self.state = [], St.GET_RESPONSE_R4

    def handle_cmd40(self):
        # CMD40 (GO_IRQ_STATE) -> R5
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Sets the system into interrupt mode')
        self.token, self.state = [], St.GET_RESPONSE_R5

    def handle_cmd42(self):
        # CMD42 (LOCK_UNLOCK) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Set/reset the password or lock/unlock the Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd44(self):
        # CMD44 (QUEUED_TASK_PARAMS) -> R1
        self.puta(31, 31, [Ann.DECODED_F, ['Reliable Write Request', 'RWR']])
        self.puta(30, 30, [Ann.DECODED_F, ['Data Direction(1:R/0:W)', 'DD']])
        self.puta(29, 29, [Ann.DECODED_F, ['Tag request', 'Tag Req', 'TR']])
        self.puta(25, 28, [Ann.DECODED_F, ['Context ID', 'CntxtID']])
        self.puta(24, 24, [Ann.DECODED_F, ['Forced Programming', 'F Prog', 'FP']])
        self.puta(23, 23, [Ann.DECODED_F, ['Priority(0:Simple/1:High)', 'Prio']])
        self.puta(21, 22, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.puta(16, 20, [Ann.DECODED_F, ['Task ID', 'TID']])
        self.puta(0, 15, [Ann.DECODED_F, ['Number of Blocks', 'NumBlk']])
        self.putc('Def data dir for R/W, Priority, Task ID, blk# of queuedd Task')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd45(self):
        # CMD45 (QUEUED_TAKS_ADDRESS) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Start block address', 'Start Blk Addr', 'SBA', 'SA']])
        self.putc('Defines the block address of queued task')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd46(self):
        # CMD46 (EXECUTE_READ_TASK) -> R1
        self.puta(21, 31, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.puta(16, 20, [Ann.DECODED_F, ['Task ID', 'TID']])
        self.puta(0, 15, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.putc('Execute task from the queue with TID')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd47(self):
        # CMD42 (EXECUTE_WRITE_TASK) -> R1
        self.puta(21, 31, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.puta(16, 20, [Ann.DECODED_F, ['Task ID', 'TID']])
        self.puta(0, 15, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.putc('Execute task from the queue with TID')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd48(self):
        # CMD48 (CMDQ_TASK_MGMT) -> R1b
        self.puta(21, 31, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.puta(16, 20, [Ann.DECODED_F, ['Task ID', 'TID']])
        self.puta(4, 15, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.puta(0, 3, [Ann.DECODED_F, ['TM Op-code', 'TMOP']])
        self.putc('Discard a specific task or entire queue')
        self.token, self.state = [], St.GET_RESPONSE_R1B

    def handle_cmd49(self):
        # CMD49 (SET_TIME) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Sets the real time clock according to the RTC info in 512 B data block')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd53(self):
        # CMD53 (PROTOCOL_RD) -> R1
        self.puta(16, 31, [Ann.DECODED_F, ['Security Protolcol Specific', 'Sec P Spec', 'SPS']])
        self.puta(8, 15, [Ann.DECODED_F, ['Security Protolcol', 'Sec P', 'SP']])
        self.puta(0, 7, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.putc('Transfer 512B Blk from device to host')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd54(self):
        # CMD54 (PROTOCOL_WR) -> R1
        self.puta(16, 31, [Ann.DECODED_F, ['Security Protolcol Specific', 'Sec P Spec', 'SPS']])
        self.puta(8, 15, [Ann.DECODED_F, ['Security Protolcol', 'Sec P', 'SP']])
        self.puta(0, 7, [Ann.DECODED_F, ['Reserved', 'RSVD']])
        self.putc('Transfer 512B Blk from host to device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd55(self):
        # CMD55 (APP_CMD) -> R1
        self.puta(16, 31, [Ann.DECODED_F, ['RCA', 'R']])
        self.puta(0, 15, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Next command is an application-specific command')
        self.is_acmd = True
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd56(self):
        # CMD55 (GEN_CMD) -> R1
        self.puta(1, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.puta(0, 0, [Ann.DECODED_F, ['RD/WR1', 'RW1', 'RW']])
        self.putc('R/W a data block from/to the Device')
        self.token, self.state = [], St.GET_RESPONSE_R1

    # Application-specific commands (ACMDs) follow:
    # TODO: Check if they need to be updated (currently copy-pasted from the sdcard_sd decoder)

    def handle_acmd6(self):
        # ACMD6 (SET_BUS_WIDTH) -> R1
        self.putc('Read SD config register (SCR)')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_acmd13(self):
        # ACMD13 (SD_STATUS) -> R1
        self.puta(0, 31, [Ann.DECODED_F, ['Stuff bits', 'Stuff', 'SB', 'S']])
        self.putc('Set SD status')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_acmd41(self):
        # ACMD41 (SD_SEND_OP_COND) -> R3
        self.puta(0, 23, [Ann.DECODED_F,
            ['VDD voltage window', 'VDD volt', 'VDD', 'V']])
        self.puta(24, 24, [Ann.DECODED_F, ['S18R']])
        self.puta(25, 27, [Ann.DECODED_F, ['Reserved', 'Res', 'R']])
        self.puta(28, 28, [Ann.DECODED_F, ['XPC']])
        self.puta(29, 29, [Ann.DECODED_F,
            ['Reserved for eSD', 'Reserved', 'Res', 'R']])
        self.puta(30, 30, [Ann.DECODED_F,
            ['Host capacity support info', 'Host capacity', 'HCS', 'H']])
        self.puta(31, 31, [Ann.DECODED_F, ['Reserved', 'Res', 'R']])
        self.putc('Send HCS info and activate the card init process')
        self.token, self.state = [], St.GET_RESPONSE_R3

    def handle_acmd51(self):
        # ACMD51 (SEND_SCR) -> R1
        self.putc('Read SD config register (SCR)')
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_cmd999(self):
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_acmd999(self):
        self.token, self.state = [], St.GET_RESPONSE_R1

    def handle_reg_status(self, current_state):
        self.putf(8, 8, [Ann.R_STATUS_OUT_OF_RANGE, ['OUT_OF_RANGE']])
        self.putf(9, 9, [Ann.R_STATUS_ADDRESS_MISALIGN, ['ADDRESS_MISALIGN']])
        self.putf(10, 10, [Ann.R_STATUS_BLOCK_LEN_ERROR, ['BLOCK_LEN_ERROR']])
        self.putf(11, 11, [Ann.R_STATUS_ERASE_SEQ_ERROR, ['ERASE_SEQ_ERROR']])
        self.putf(12, 12, [Ann.R_STATUS_ERASE_PARAM, ['ERASE_PARAM']])
        self.putf(13, 13, [Ann.R_STATUS_WP_VIOLATION, ['WP_VIOLATION']])
        self.putf(14, 14, [Ann.R_STATUS_DEVICE_IS_LOCKED, ['DEVICE_IS_LOCKED']])
        self.putf(15, 15, [Ann.R_STATUS_LOCK_UNLOCK_FAILED, ['LOCK_UNLOCK_FAILED']])
        self.putf(16, 16, [Ann.R_STATUS_COM_CRC_ERROR, ['COM_CRC_ERROR']])
        self.putf(17, 17, [Ann.R_STATUS_ILLEGAL_COMMAND, ['ILLEGAL_COMMAND']])
        self.putf(18, 18, [Ann.R_STATUS_DEVICE_ECC_FAILED, ['DEVICE_ECC_FAILED']])
        self.putf(19, 19, [Ann.R_STATUS_CC_ERROR, ['CC_ERROR']])
        self.putf(20, 20, [Ann.R_STATUS_ERROR, ['ERROR']])
        self.putf(21, 21, [Ann.R_STATUS_OBS_HOST_IGNORE_18, ['<Obsolete>', 'Obs', 'O']])
        self.putf(22, 22, [Ann.R_STATUS_OBS_HOST_IGNORE_17, ['<Obsolete>', 'Obs', 'O']])
        self.putf(23, 23, [Ann.R_STATUS_CID_CSD_OVERWRITE, ['CID_CSD_OVERWRITE']])
        self.putf(24, 24, [Ann.R_STATUS_WP_ERASE_SKIP, ['WP_ERASE_SKIP']])
        self.putf(25, 25, [Ann.R_STATUS_RSVD_14, ['Reserved', 'RSVD']])
        self.putf(26, 26, [Ann.R_STATUS_ERASE_RESET, ['ERASE_RESET']])
        self.putf(27, 30, [Ann.R_STATUS_CURRENT_STATE, ['CURRENT_STATE: %s' % current_state]])
        self.putf(31, 31, [Ann.R_STATUS_READY_FOR_DATA, ['READY_FOR_DATA']])
        self.putf(32, 32, [Ann.R_STATUS_SWITCH_ERROR, ['SWITCH_ERROR']])
        self.putf(33, 33, [Ann.R_STATUS_EXCEPTION_EVENT, ['EXCEPTION_EVENT']])
        self.putf(34, 34, [Ann.R_STATUS_APP_CMD, ['APP_CMD']])
        self.putf(35, 35, [Ann.R_STATUS_RSVD_4, ['Reserved', 'RSVD']])
        self.putf(36, 37, [Ann.R_STATUS_RSVD_APP_CMD, ['Reserved for application specific commands', 'RSVD_APP_CMD']])
        self.putf(38, 39, [Ann.R_STATUS_RSVD_TESTMODE, ['Reserved for manufacturer test mode', 'RSVD_TESTMODE']])

    def handle_reg_cid(self):
        self.putf(8, 15, [Ann.R_CID_MID, ['Manufacturer ID', 'MID']])
        self.putf(16, 21, [Ann.R_CID_RSVD, ['Reserved', 'RSVD', 'R']])
        self.putf(22, 23, [Ann.R_CID_CBX, ['Device/BGA', 'CBX']])
        self.putf(24, 31, [Ann.R_CID_OID, ['OEM/application ID', 'OID']])
        self.putf(32, 79, [Ann.R_CID_PNM, ['Product name', 'PNM']])
        self.putf(80, 87, [Ann.R_CID_PRV, ['Product revision', 'PRV']])
        self.putf(88, 119, [Ann.R_CID_PSN, ['Product serial number', 'PSN']])
        self.putf(120, 127, [Ann.R_CID_MDT, ['Manufacturing date', 'MDT']])
        self.putf(128, 134, [Ann.R_CID_CRC, ['CRC7 checksum', 'CRC']])
        #self.putf(135, 135, [Ann.R_CID_ONE, ['Always 1', '1']])  # No need to annotate, the stop bit is transmitted instead

    def handle_reg_csd(self):
        self.putf(8, 9, [Ann.R_CSD_CSD_STRUCTURE, ['CSD structure', 'CSD_STRUCTURE']])
        self.putf(10, 13, [Ann.R_CSD_SPEC_VERS, ['System specification version', 'SPEC_VERS', 'SV']])
        self.putf(14, 15, [Ann.R_CSD_RSVD, ['Reserved', 'RSVD', 'R']])
        self.putf(16, 23, [Ann.R_CSD_TAAC, ['Data read access-time - 1', 'TAAC']])
        self.putf(24, 31, [Ann.R_CSD_NSAC, ['Data read access-time - 2 in CLK cycles (NSAC * 100)', 'NSAC']])
        self.putf(32, 39, [Ann.R_CSD_TRAN_SPEED, ['Max. data transfer rate', 'TRAN_SPEED']])
        self.putf(40, 51, [Ann.R_CSD_CCC, ['Device command classes', 'CCC']])
        self.putf(52, 55, [Ann.R_CSD_READ_BL_LEN, ['Max. read data block length', 'READ_BL_LEN']])
        self.putf(56, 56, [Ann.R_CSD_READ_BL_PARTIAL, ['Partial blocks for read allowed', 'READ_BL_PARTIAL']])
        self.putf(57, 57, [Ann.R_CSD_WRITE_BLK_MISALIGN, ['Write block misalignment', 'WRITE_BLK_MISALIGN']])
        self.putf(58, 58, [Ann.R_CSD_READ_BLK_MISALIGN, ['Read block misalignment', 'READ_BLK_MISALIGN']])
        self.putf(59, 59, [Ann.R_CSD_DSR_IMP, ['DSR implemented', 'DSR_IMP']])
        self.putf(60, 61, [Ann.R_CSD_RSVD, ['Reserved', 'RSVD', 'R']])
        self.putf(62, 73, [Ann.R_CSD_C_SIZE, ['Device size', 'C_SIZE']])
        self.putf(74, 76, [Ann.R_CSD_VDD_R_CURR_MIN, ['Max. read current @VDD min', 'VDD_R_CURR_MIN']])
        self.putf(77, 79, [Ann.R_CSD_VDD_R_CURR_MAX, ['Max. read current @VDD max', 'VDD_R_CURR_MAX']])
        self.putf(80, 82, [Ann.R_CSD_VDD_W_CURR_MIN, ['Max. write current @VDD min', 'VDD_W_CURR_MIN']])
        self.putf(83, 85, [Ann.R_CSD_VDD_W_CURR_MAX, ['Max. write current @VDD max', 'VDD_W_CURR_MAX']])
        self.putf(86, 88, [Ann.R_CSD_C_SIZE_MULT, ['Device size multiplier', 'C_SIZE_MULT']])
        self.putf(89, 93, [Ann.R_CSD_ERASE_GRP_SIZE, ['Erase single block enable', 'ERASE_GRP_SIZE']])
        self.putf(94, 98, [Ann.R_CSD_ERASE_GRP_MULT, ['Erase single block enable', 'ERASE_GRP_MULT']])
        self.putf(99, 103, [Ann.R_CSD_WP_GRP_SIZE, ['Write protect group size', 'WP_GRP_SIZE']])
        self.putf(104, 104, [Ann.R_CSD_WP_GRP_ENABLE, ['Write protect group enable', 'WP_GRP_ENABLE']])
        self.putf(105, 106, [Ann.R_CSD_DEFAULT_ECC, ['Manufacturer default ECC', 'DEFAULT_ECC']])
        self.putf(107, 109, [Ann.R_CSD_R2W_FACTOR, ['Write speed factor', 'R2W_FACTOR']])
        self.putf(110, 113, [Ann.R_CSD_WRITE_BL_LEN, ['Max. write data block length', 'WRITE_BL_LEN']])
        self.putf(114, 114, [Ann.R_CSD_WRITE_BL_PARTIAL, ['Partial blocks for write allowed', 'WRITE_BL_PARTIAL']])
        self.putf(115, 118, [Ann.R_CSD_RSVD, ['Reserved', 'RSVD']])
        self.putf(119, 119, [Ann.R_CSD_CONTENT_PROT_APP, ['Content protection application', 'CONTENT_PROT_APP']])
        self.putf(120, 120, [Ann.R_CSD_FILE_FORMAT_GRP, ['File format group', 'FILE_FORMAT_GRP']])
        self.putf(121, 121, [Ann.R_CSD_COPY, ['Copy flag (OTP)', 'COPY']])
        self.putf(122, 122, [Ann.R_CSD_PERM_WRITE_PROTECT, ['Permanent write protection', 'PERM_WRITE_PROTECT']])
        self.putf(123, 123, [Ann.R_CSD_TMP_WRITE_PROTECT, ['Temporary write protection', 'TMP_WRITE_PROTECT']])
        self.putf(124, 125, [Ann.R_CSD_FILE_FORMAT, ['File format', 'FILE_FORMAT']])
        self.putf(126, 127, [Ann.R_CSD_ECC, ['ECC code', 'ECC']])
        self.putf(128, 134, [Ann.R_CSD_CRC, ['CRC', 'CRC', 'C']])
        #self.putf(135, 135, [Ann.R_CSD_ONE, ['Not used, always 1', '1']])  # No need to annotate, the stop bit is transmitted instead

    # Response tokens can have one of four formats (depends on content).
    # They can have a total length of 48 or 136 bits.
    # They're sent serially (MSB-first) by the Device that the host
    # addressed previously, or (synchronously) by all connected Devices.

    def handle_response_r1(self, cmd_pin):
        # R1: Normal response command
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == Device)
        #  - Bits[45:40]: Command index (BCD; valid: 0-63)
        #  - Bits[39:08]: Device status
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd_pin, 48):
            return
        self.handle_common_token_fields()
        self.putr(Ann.RESPONSE_R1)
        self.puta(0, 31, [Ann.DECODED_F, ['Device status', 'Status', 'S']])
        
        # This decodes the CURRENT_STATE value:
        dcs_val = int('0b' + ''.join([str(self.token[i].bit) for i in range(27, 31)]), 2)
        dcs = device_current_state.get(dcs_val, 'reserved')
        self.handle_reg_status(dcs)
        
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_response_r1b(self, cmd_pin):
        # R1b: Same as R1 with an optional busy signal (on the data line)
        if not self.get_token_bits(cmd_pin, 48):
            return
        self.handle_common_token_fields()
        self.putr(Ann.RESPONSE_R1B)
        self.puta(0, 31, [Ann.DECODED_F, ['Device status', 'Status', 'S']])
        
        # This decodes the CURRENT_STATE value:
        dcs_val = int('0b' + ''.join([str(self.token[i].bit) for i in range(27, 31)]), 2)
        dcs = device_current_state.get(dcs_val, 'reserved')
        self.handle_reg_status(dcs)
        
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_response_r2(self, cmd_pin):
        # R2: CID/CSD register
        #  - Bits[135:135]: Start bit (always 0)
        #  - Bits[134:134]: Transmission bit (0 == Device)
        #  - Bits[133:128]: Check bits (always 0b111111)
        #  - Bits[127:001]: CID or CSD register including internal CRC7
        #  - Bits[000:000]: End bit (always 1)
        if not self.get_token_bits(cmd_pin, 136):
            return
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [Ann.BIT_0 + self.token[bit].bit, ['%d' % self.token[bit].bit]])
        self.putf(0, 0, [Ann.F_START, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1].bit == 1 else 'device'
        self.putf(1, 1, [Ann.F_TRANSMISSION, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [Ann.F_CMD, ['Check bits (always 0b111111)', 'ChkBits', 'CB']])
        self.putf(8, 134, [Ann.F_ARG, ['Argument', 'Arg', 'A']])
        self.putf(135, 135, [Ann.F_END, ['End bit', 'End', 'E']])
        reg = 'CSD' if self.last_cmd == Ann.CMD9 else 'CID'
        self.putf(8, 134, [Ann.DECODED_F, ['%s register' % reg, reg, 'C']])
        self.putf(0, 135, [Ann.RESPONSE_R2, ['Response: R2']])

        if self.last_cmd in (Ann.CMD2, Ann.CMD10):
            self.handle_reg_cid()

        if self.last_cmd == Ann.CMD9:
            self.handle_reg_csd()

        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_response_r3(self, cmd_pin):
        # R3: OCR register
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == device)
        #  - Bits[45:40]: Reserved (always 0b111111)
        #  - Bits[39:08]: OCR register
        #  - Bits[07:01]: Reserved (always 0b111111)
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd_pin, 48):
            return
        self.putr(Ann.RESPONSE_R3)
        # Annotations for each individual bit.
        for bit in range(len(self.token)):
            self.putf(bit, bit, [Ann.BIT_0 + self.token[bit].bit, ['%d' % self.token[bit].bit]])
        self.putf(0, 0, [Ann.F_START, ['Start bit', 'Start', 'S']])
        t = 'host' if self.token[1].bit == 1 else 'device'
        self.putf(1, 1, [Ann.F_TRANSMISSION, ['Transmission: ' + t, 'T: ' + t, 'T']])
        self.putf(2, 7, [Ann.F_CMD, ['Check bits', 'CB']])
        self.putf(8, 39, [Ann.F_ARG, ['Argument', 'Arg', 'A']])
        self.putf(40, 46, [Ann.F_CRC, ['Check bits', 'CB']])
        self.putf(47, 47, [Ann.F_END, ['End bit', 'End', 'E']])
        self.puta(0, 31, [Ann.DECODED_F, ['OCR register', 'OCR reg', 'OCR', 'O']])

        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_response_r4(self, cmd_pin):
        # R4: (Fast I/O)
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == device)
        #  - Bits[45:40]: Command index (always 0b100111)
        #  - Bits[39:24]: Argument[31:16]: RCA
        #  - Bits[23:23]: Argument[15:15]: Status
        #  - Bits[22:16]: Argument[14: 8]: Register address
        #  - Bits[15: 8]: Argument[ 7: 0]: Read register contents
        #  - Bits[ 7: 1]: CRC7
        #  - Bits[ 0: 0]: End bit (always 1)
        if not self.get_token_bits(cmd_pin, 48):
            return
        self.handle_common_token_fields()
        self.putr(Ann.RESPONSE_R4)
        self.puta(16, 31, [Ann.DECODED_F, ['Relative device address (RCA)', 'RCA']])
        self.puta(15, 15, [Ann.DECODED_F, ['Status', 'S']])
        self.puta(8, 14, [Ann.DECODED_F, ['Register address', 'RegAddr', 'RA']])
        self.puta(0, 7, [Ann.DECODED_F, ['Read register contents', 'RRC']])
        self.token, self.state = [], St.GET_COMMAND_TOKEN

    def handle_response_r5(self, cmd_pin):
        # R5: (Interrupt request)
        #  - Bits[47:47]: Start bit (always 0)
        #  - Bits[46:46]: Transmission bit (0 == device)
        #  - Bits[45:40]: Command index (always 0b101000)
        #  - Bits[39:20]: Argument[31:16]: RCA of winning Device or of the host
        #  - Bits[19:16]: Argument[15: 0]: Not defined. May be used for IRQ data
        #  - Bits[07:01]: CRC7
        #  - Bits[00:00]: End bit (always 1)
        if not self.get_token_bits(cmd_pin, 48):
            return
        self.handle_common_token_fields()
        self.putr(Ann.RESPONSE_R5)

        # # Arg[11:08]: Voltage accepted
        # v = ''.join(str(i.bit) for i in self.token[28:32])
        # av = accepted_voltages.get(int('0b' + v, 2), 'Unknown')
        # self.puta(8, 11, [Ann.DECODED_F, ['Voltage accepted: ' + av, 'Voltage', 'Volt', 'V']])

        self.puta(16, 31, [Ann.DECODED_F, ['RCA of winning Device or of the host', 'RCA_W']])
        self.puta(0, 15, [Ann.DECODED_F, ['Undefined', 'Undef', 'U']])

        self.token, self.state = [], St.GET_COMMAND_TOKEN


    def decode(self):
        while True:
            # Wait for a rising CLK edge.
            (cmd_pin, clk, dat0, dat1, dat2, dat3) = self.wait({Pin.CLK: 'r'})

            # State machine.
            if self.state == St.GET_COMMAND_TOKEN:
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd_pin != 0:
                        continue
                self.get_command_token(cmd_pin)
            elif self.state.value.startswith('HANDLE_CMD'):
                # Call the respective handler method for the command.
                a, cmdstr = 'a' if self.is_acmd else '', self.state.value[10:].lower()
                handle_cmd = getattr(self, 'handle_%scmd%s' % (a, cmdstr))
                handle_cmd()
                # Leave ACMD mode again after the first command after CMD55.
                if self.is_acmd and cmdstr not in ('55', '63'):
                    self.is_acmd = False
            elif self.state.value.startswith('GET_RESPONSE'):
                if len(self.token) == 0:
                    # Wait for start bit (CMD = 0).
                    if cmd_pin != 0:
                        continue
                # Call the respective handler method for the response.
                s = 'handle_response_%s' % self.state.value[13:].lower()
                handle_response = getattr(self, s)
                handle_response(cmd_pin)
