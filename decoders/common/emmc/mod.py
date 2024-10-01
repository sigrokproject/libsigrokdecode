##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2014 Uwe Hermann <uwe@hermann-uwe.de>
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

# Normal commands (CMD)
# Unlisted items are 'Reserved' as per SD spec. The 'Unknown' items don't
# seem to be mentioned in the spec, but aren't marked as reserved either.
cmd_names = {
    0:  'GO_IDLE_STATE',
    1:  'SEND_OP_COND',
    2:  'ALL_SEND_CID',
    3:  'SET_RELATIVE_ADDR',
    4:  'SET_DSR',
    5:  'SLEEP_AWAKE', # SDIO-only
    6:  'SWITCH',
    7:  'SELECT/DESELECT_CARD',
    8:  'SEND_EXT_CSD',
    9:  'SEND_CSD',
    10: 'SEND_CID',
    11: 'OBSOLETE',
    12: 'STOP_TRANSMISSION',
    13: 'SEND_STATUS',
    14: 'BUSTEST_R',
    15: 'GO_INACTIVE_STATE',
    16: 'SET_BLOCKLEN',
    17: 'READ_SINGLE_BLOCK',
    18: 'READ_MULTIPLE_BLOCK',
    19: 'BUSTEST_W',
    20: 'OBSOLETE',
    21: 'SEND_TUNING_BLOCK',
    # 22: Reserved
    23: 'SET_BLOCK_COUNT',
    24: 'WRITE_BLOCK',
    25: 'WRITE_MULTIPLE_BLOCK',
    26: 'PROGRAM_CID',
    27: 'PROGRAM_CSD',
    28: 'SET_WRITE_PROT',
    29: 'CLR_WRITE_PROT',
    30: 'SEND_WRITE_PROT',
    31: 'SEND_WRITE_PROT_TYPE',
    # 32-34: Reserved for backwards compatibility
    35: 'ERASE_GROUP_START',
    36: 'ERASE_GROUP_END',
    # 37: Reserved
    38: 'ERASE',
    39: 'FAST_IO',
    40: 'GO_IRQ_STATE',
    # 41: Reserved
    42: 'LOCK_UNLOCK',
    # 43: Reserved
    44: 'QUEUED_TASK_PARAMS',
    45: 'QUEUED_TASK_ADDRESS',
    46: 'EXECUTE_READ_TASK',
    47: 'EXECUTE_WRITE_TASK',
    48: 'CMDQ_TASK_MGMT',
    49: 'SET_TIME',
    # 50-52: Reserved
    53: 'PROTOCOL_RD', # SDIO-only
    54: 'PROTOCOL_WR',
    55: 'APP_CMD',
    56: 'GEN_CMD',
    # 57-59: Reserved
    60: 'Reserved for manufacturer',
    61: 'Reserved for manufacturer',
    62: 'Reserved for manufacturer',
    63: 'Reserved for manufacturer',
}

# These are copy-paste from the sdcard_sd decoder
# TODO: Find how they are specified in the eMMC 5.1 spec
#
# Application-specific commands (ACMD)
# Unlisted items are 'Reserved' as per SD spec. The 'Unknown' items don't
# seem to be mentioned in the spec, but aren't marked as reserved either.
acmd_names = {
    # 1-5: Reserved
    6:  'SET_BUS_WIDTH',
    # 7-12: Reserved
    13: 'SD_STATUS',
    14: 'Reserved for Security Application',
    15: 'Reserved for Security Application',
    16: 'Reserved for Security Application',
    # 17: Reserved
    18: 'Reserved for SD security applications',
    # 19-21: Reserved
    22: 'SEND_NUM_WR_BLOCKS',
    23: 'SET_WR_BLK_ERASE_COUNT',
    # 24: Reserved
    25: 'Reserved for SD security applications',
    26: 'Reserved for SD security applications',
    27: 'Reserved for security specification',
    28: 'Reserved for security specification',
    # 29: Reserved
    30: 'Reserved for security specification',
    31: 'Reserved for security specification',
    32: 'Reserved for security specification',
    33: 'Reserved for security specification',
    34: 'Reserved for security specification',
    35: 'Reserved for security specification',
    # 36-37: Reserved
    38: 'Reserved for SD security applications',
    # 39-40: Reserved
    41: 'SD_SEND_OP_COND',
    42: 'SET_CLR_CARD_DETECT',
    43: 'Reserved for SD security applications',
    44: 'Reserved for SD security applications',
    45: 'Reserved for SD security applications',
    46: 'Reserved for SD security applications',
    47: 'Reserved for SD security applications',
    48: 'Reserved for SD security applications',
    49: 'Reserved for SD security applications',
    50: 'Unknown',
    51: 'SEND_SCR',
    52: 'Reserved for security specification',
    53: 'Reserved for security specification',
    54: 'Reserved for security specification',
    55: 'Non-existant', # Doesn't exist (equivalent to CMD55)
    56: 'Reserved for security specification',
    57: 'Reserved for security specification',
    58: 'Reserved for security specification',
    59: 'Reserved for security specification',
    60: 'Unknown',
    61: 'Unknown',
    62: 'Unknown',
    63: 'Unknown',
}

accepted_voltages = {
    0b0001: '2.7-3.6V',
    0b0010: 'reserved for low voltage range',
    0b0100: 'reserved',
    0b1000: 'reserved',
    # All other values: "not defined".
}

device_current_state = {
    0: 'Idle',
    1: 'Ready',
    2: 'Ident',
    3: 'Stby',
    4: 'Tran',
    5: 'Data',
    6: 'Rcv',
    7: 'Prg',
    8: 'Dis',
    9: 'Btst',
    10: 'Slp',
    #11-15: 'reserved',
}
