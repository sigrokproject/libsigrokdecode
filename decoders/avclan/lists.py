##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2023 Maciej Grela <enki@fsck.pl>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <https://www.gnu.org/licenses/>.

'''
Lists of known values used by the AVC-LAN protocol in Toyota vehicles.

The values here have been either copied from other reference sources,
and existing code:
- http://softservice.com.pl/corolla/avc/avclan.php
- https://github.com/halleysfifthinc/Toyota-AVC-LAN/

or reverse-engineered using a Head Unit and CD changer documented in detail on

https://pop.fsck.pl/hardware/toyota-corolla.html
'''

from enum import IntEnum, IntFlag


class Searchable:  # pylint: disable=too-few-public-methods
    '''A trait implementing value search in enums.'''
    @classmethod
    def has_value(cls, value):
        '''Searches for a particular integer value in the enum'''
        return value in iter(cls)


class Commands(Searchable, IntEnum):
    '''
    Valid values for the control bits if IEBus frames.

    Reference: https://en.wikipedia.org/wiki/IEBus
    Reference: http://softservice.com.pl/corolla/avc/avclan.php
    '''
    READ_STATUS         = 0x00  # Reads slave status
    READ_DATA_LOCK      = 0x03  # Reads data and locks unit
    READ_LOCK_ADDR_LO   = 0x04  # Reads lock address (lower 8 bits)
    READ_LOCK_ADDR_HI   = 0x05  # Reads lock address (higher 4 bits)
    READ_STATUS_UNLOCK  = 0x06  # Reads slave status and unlocks unit
    READ_DATA           = 0x07  # Reads data
    WRITE_CMD_LOCK      = 0x0a  # Writes command and locks unit
    WRITE_DATA_LOCK     = 0x0b  # Writes data and locks unit
    WRITE_CMD           = 0x0e  # Writes command
    WRITE_DATA          = 0x0f  # Writes data


class HWAddresses(Searchable, IntEnum):
    '''
    Known hardware addresses.
    '''
    EMV             = 0x110
    AVX             = 0x120
    DIN1_TV         = 0x128  # 1DIN TV
    AVN             = 0x140
    G_BOOK          = 0x144  # G-BOOK
    AUDIO_HU1       = 0x160  # AUDIO H/U: Control Panel subassy
    NAVI            = 0x178
    MONET           = 0x17C
    TEL             = 0x17D
    Rr_TV           = 0x180  # Rr-TV (sic!) pylint: disable=invalid-name
    AUDIO_HU2       = 0x190  # AUDIO H/U: CD Player + Tuner + Audio Amplifier subassy
    DVD_P           = 0x1A0
    CLOCK           = 0x1D6
    CAMERA_C        = 0x1AC  # CAMERA-C
    Rr_CONT         = 0x1C0  # Rr-CONT (sic!) pylint: disable=invalid-name
    TV_TUNER2       = 0x1C2  # TV-TUNER2
    PANEL           = 0x1C4
    GW              = 0x1C6  # G/W
    FM_M_LCD        = 0x1C8  # FM-M-LCD
    ST_WHEEL_CTRL   = 0x1CC
    GW_TRIP         = 0x1D8  # G/W for Trip
    BODY            = 0x1EC
    RADIO_TUNER     = 0x1F0
    XM              = 0x1F1
    SIRIUS          = 0x1F2
    RSA             = 0x1F4
    RSE             = 0x1F6
    GROUP_AUDIO     = 0x1FF  # Group 1 - All Audio devices
    TV_TUNER        = 0x230
    CD_CH2          = 0x240
    DVD_CH          = 0x250
    CAMERA          = 0x280
    CD_CH1          = 0x360
    MD_CH           = 0x3A0
    DSP_AMP         = 0x440
    AMP             = 0x480
    ETC             = 0x530
    MAYDAY          = 0x5C8
    BROADCAST       = 0xFFF  # General Broadcast (All devices on bus)


class FunctionIDs(Searchable, IntEnum):
    '''
    These are called "Logical Addresses" in the Softservice site
    but I think a better term would be "functions"
    Reference: http://softservice.com.pl/corolla/avc/avclan.php
    '''
    COMM_CTRL           = 0x01  # communication ctrl
    COMMUNICATION       = 0x12  # communication
    SW                  = 0x21
    SW_NAME             = 0x23  # SW with name
    SW_CONVERTING       = 0x24
    CMD_SW              = 0x25  # command SW
    BEEP_HU             = 0x28  # beep dev in HU
    BEEP_SPEAKERS       = 0x29  # beep via speakers
    FRONT_PSNG_MONITOR  = 0x34  # front passenger monitor
    CD_CHANGER2         = 0x43  # Reported by CD_CH2 (0x240)
    BLUETOOTH_TEL       = 0x55
    INFO_DRAWING        = 0x56  # information drawing
    NAV_ECU             = 0x58  # navigation ECU
    CAMERA              = 0x5C
    CLIMATE_DRAWING     = 0x5D  # Climate ctrl drawing
    AUDIO_DRAWING       = 0x5E
    TRIP_INFO_DRAWING   = 0x5F
    TUNER               = 0x60
    TAPE_DECK           = 0x61
    CD                  = 0x62
    CD_CHANGER          = 0x63  # Reported by CD_CH1 (0x360)
    AUDIO_AMP           = 0x74  # Audio amplifier
    GPS                 = 0x80  # GPS receiver
    VOICE_CTRL          = 0x85  # voice control
    CLIMATE_CTRL_DEV    = 0xE0  # climate ctrl dev
    TRIP_INFO           = 0xE5


class CommCtrlOpcodes(Searchable, IntEnum):
    '''
    Opcodes for the COMM_CTRL function.

    It looks like response opcode = request opcode + 0x10 but
    this rule doesn't match all the opcodes seen. Specifically
    the 0x45 code does not match.
    '''
    LIST_FUNCTIONS_REQ   = 0x00
    LIST_FUNCTIONS_RESP  = 0x10
    RESTART_LAN          = 0x01
    LANCHECK_END_REQ     = 0x08
    LANCHECK_END_RESP    = 0x18
    LANCHECK_SCAN_REQ    = 0x0a
    LANCHECK_SCAN_RESP   = 0x1a
    LANCHECK_REQ         = 0x0c
    LANCHECK_RESP        = 0x1c
    PING_REQ             = 0x20
    PING_RESP            = 0x30

    # Used when HU is switching between Radio and CD
    DISABLE_FUNCTION_REQ    = 0x43
    DISABLE_FUNCTION_RESP   = 0x53
    ENABLE_FUNCTION_REQ     = 0x42
    ENABLE_FUNCTION_RESP    = 0x52

    ADVERTISE_FUNCTION   = 0x45  # xx=60,61,62,63... function
    GENERAL_QUERY        = 0x46  # any device is use


class CDOpcodes(Searchable, IntEnum):
    '''
    Opcodes for the CD Player function.
    These seem to be also common for the CD Changer function.
    '''
    # Events
    INSERTED_CD         = 0x50
    REMOVED_CD          = 0x51

    # Requests
    REQUEST_PLAYBACK2   = 0xe2
    REQUEST_LOADER2     = 0xe4
    REQUEST_TRACK_NAME  = 0xed

    # Reports
    REPORT_PLAYBACK     = 0xf1
    REPORT_PLAYBACK2    = 0xf2
    REPORT_LOADER       = 0xf3
    REPORT_LOADER2      = 0xf4   # Requested with REQUEST_LOADER
    REPORT_TOC          = 0xf9
    REPORT_TRACK_NAME   = 0xfd


class CDSlots(Searchable, IntFlag):
    SLOT1               = 0x01
    SLOT2               = 0x02
    SLOT3               = 0x04
    SLOT4               = 0x08
    SLOT5               = 0x10
    SLOT6               = 0x20


class CDStateCodes(Searchable, IntFlag):
    '''State codes for the CD Player function.'''
    OPEN                = 0x01
    ERR1                = 0x02
    BIT2                = 0x04
    SEEKING             = 0x08
    PLAYBACK            = 0x10
    SEEKING_TRACK       = 0x20
    BIT6                = 0x40
    LOADING             = 0x80


class CDFlags(Searchable, IntFlag):
    '''Bit flags for the CD Player function.'''
    BIT0                = 0x01
    DISK_RANDOM         = 0x02
    RANDOM              = 0x04
    DISK_REPEAT         = 0x08
    REPEAT              = 0x10
    DISK_SCAN           = 0x20
    SCAN                = 0x40
    BIT7                = 0x80


class CmdSwOpcodes(Searchable, IntEnum):
    '''Opcodes for the SW_CMD function.'''
    EJECT                           = 0x80
    DISC_UP                         = 0x90
    DISC_DOWN                       = 0x91
    PWRVOL_KNOB_RIGHTHAND_TURN      = 0x9c
    PWRVOL_KNOB_LEFTHAND_TURN       = 0x9d
    TRACK_SEEK_UP                   = 0x94
    TRACK_SEEK_DOWN                 = 0x95
    CD_ENABLE_SCAN                  = 0xa6
    CD_DISABLE_SCAN                 = 0xa7
    CD_ENABLE_REPEAT                = 0xa0
    CD_DISABLE_REPEAT               = 0xa1
    CD_ENABLE_RANDOM                = 0xb0
    CD_DISABLE_RANDOM               = 0xb1


class AudioAmpOpcodes(Searchable, IntEnum):
    '''Opcodes for the AUDIO_AMP function.'''
    REPORT          = 0xf1


class AudioAmpFlags(Searchable, IntFlag):
    '''Flags for the AUDIO_AMP functions.'''
    BIT0            = 0x01
    BIT1            = 0x02
    MUTE            = 0x04
    BIT3            = 0x08
    BIT4            = 0x10
    BIT5            = 0x20
    BIT6            = 0x40
    BIT7            = 0x80


class TunerOpcodes(Searchable, IntEnum):
    '''Opcodes for the TUNER function.'''
    REPORT          = 0xf1


class TunerFlags(Searchable, IntFlag):
    '''Bit flags for the TUNER function.'''
    BIT0            = 0x01
    BIT1            = 0x02
    TP              = 0x04
    TA              = 0x08
    REG             = 0x10
    BIT5            = 0x20
    AF              = 0x40
    BIT7            = 0x80


class TunerState(Searchable, IntEnum):
    '''States for the TUNER function.'''
    ON              = 0x01
    OFF             = 0x00


class TunerModes(Searchable, IntEnum):
    '''Modes for the TUNER function.'''
    MANUAL          = 0x27
    AST_SEARCH      = 0x0a
    SCAN_DOWN       = 0x07
    SCAN_UP         = 0x06
    READY           = 0x01
    OFF             = 0x00
