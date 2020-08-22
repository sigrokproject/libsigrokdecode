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

accepted_voltages = {
    0b0001: '2.7-3.6V',
    0b0010: 'reserved for low voltage range',
    0b0100: 'reserved',
    0b1000: 'reserved',
    # All other values: "not defined".
}

device_status = {
    0:  'Reserved for manufacturer test mode',
    1:  'Reserved for manufacturer test mode',
    2:  'Reserved for application specific commands',
    3:  'AKE_SEQ_ERROR',
    4:  'Reserved',
    5:  'APP_CMD',
    6:  'EXCEPTION_EVENT',
    7:  'SWITCH_ERROR',
    8:  'READY_FOR_DATA',
    9:  'CURRENT_STATE', # CURRENT_STATE is a 4-bit value (decimal: 0..15).
    10: 'CURRENT_STATE',
    11: 'CURRENT_STATE',
    12: 'CURRENT_STATE',
    13: 'ERASE_RESET',
    14: 'Reserved(must be 0)',
    15: 'WP_ERASE_SKIP',
    16: 'CIS/CSD_OVERWRITE',
    17: 'Obsolete',
    18: 'Obsolete',
    19: 'ERROR',
    20: 'CC_ERROR',
    21: 'DEVICE_ECC_FAILED',
    22: 'ILLEGAL_COMMAND',
    23: 'COM_CRC_ERROR',
    24: 'LOCK_UNLOCK_FAILED',
    25: 'DEVICE_IS_LOCKED',
    26: 'WP_VIOLATION',
    27: 'ERASE_PARAM',
    28: 'ERASE_SEQ_ERROR',
    29: 'BLOCK_LEN_ERROR',
    30: 'ADDR_MISALIGN',
    31: 'ADDR_OUT_OF_RANGE',
}

sd_status = {
    # 311:0: Reserved for manufacturer
    # 391:312: Reserved
}
