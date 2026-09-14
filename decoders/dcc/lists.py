##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2025 Vincent Hamp <hamp@zimo.at>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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
'''
| NMRA (English)                                                                                                                                                                       | RailCommunity (German)                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| [S-9.1 Electrical Standards for Digital Command Control](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.1_electrical_standards_for_digital_command_control.pdf) | [RCN-210 DCC - Protokoll Bit - Übertragung](https://normen.railcommunity.de/RCN-210.pdf)                                 |
| [S-9.2 Communications Standards For Digital Command Control, All Scales](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-92-2004-07.pdf)                           | [RCN-211 DCC - Protokoll Paketstruktur, Adressbereiche und globale Befehle](https://normen.railcommunity.de/RCN-211.pdf) |
| [S-9.2.1 DCC Extended Packet Formats](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1_dcc_extended_packet_formats.pdf)                                       | [RCN-212 DCC - Protokoll Betriebsbefehle für Fahrzeugdecoder](https://normen.railcommunity.de/RCN-212.pdf)               |
| [S-9.2.1 DCC Extended Packet Formats](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1_dcc_extended_packet_formats.pdf)                                       | [RCN-213 DCC - Protokoll Betriebsbefehle für Zubehördecoder](https://normen.railcommunity.de/RCN-213.pdf)                |
| [S-9.2.1 DCC Extended Packet Formats](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1_dcc_extended_packet_formats.pdf)                                       | [RCN-214 DCC - Protokoll Konfigurationsbefehle](https://normen.railcommunity.de/RCN-214.pdf)                             |
| [S-9.2.3 Service Mode For Digital Command Control, All Scales](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/S-9.2.3_2012_07.pdf)                                  | [RCN-216 DCC - Protokoll Programmierumgebung](https://normen.railcommunity.de/RCN-216.pdf)                               |
| [S-9.3.2 Communications Standard for Digital Command Control Basic Decoder Transmission](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/S-9.3.2_2012_12_10.pdf)     | [RCN-217 RailCom DCC-Rückmeldeprotokoll](https://normen.railcommunity.de/RCN-217.pdf)                                    |
| [S-9.2.1.1 Advanced Extended Packet Formats](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1.1_advanced_extended_packet_formats.pdf)                         | [RCN-218 DCC - Protokoll DCC-A - Automatische Anmeldung](https://normen.railcommunity.de/RCN-218.pdf)                    |
| [S-9.2.2 Configuration Variables For Digital Command Control, All Scales](https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.2_decoder_cvs_2012.07.pdf)           | [RCN-225 DCC - Protokoll Konfigurationsvariablen](https://normen.railcommunity.de/RCN-225.pdf)                           |
'''

BIT_HBIT = 1 * 2  # Halfbits per bit
BYTE_HBIT = 8 * BIT_HBIT  # Halfbits per byte

# BiDi timings [µs], see RCN-217 table 1
# https://normen.railcommunity.de/RCN-217.pdf
BIDI_BIT_TIME = 4  # BiDi UART (250kBaud) bit time in
BIDI_TCS_MIN = 26  # Minimal timing for cutout start
BIDI_TCS = 29  # Standard timing for cutout start
BIDI_TCS_MAX = 32  # Maximum timing for cutout start
BIDI_TCE_MIN = 454  # Minimum timing for cutout end
BIDI_TCE = 471  # Standard timing for cutout end
BIDI_TCE_MAX = 488  # Maximum timing for cutout end
BIDI_TTS1 = 80  # Minimum timing for channel 1 start
BIDI_TTC1 = 177  # Maximum timing for channel 1 end
BIDI_TTS2 = 193  # Minimum timing for channel 2 start
BIDI_TTC2 = 454  # Maximum timing for channel 2 end
BIDI_ACKS = (0b00001111, 0b11110000)
BIDI_NAK = 0b00111100

# LUT for decoding BiDi, see RCN-217 table 2
# https://normen.railcommunity.de/RCN-217.pdf
BIDI_DECODE = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x33,
    0x00, 0x00, 0x00, 0x34, 0x00, 0x35, 0x36, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x3A, 0x00, 0x00, 0x00, 0x3B, 0x00, 0x3C, 0x37, 0x00,
    0x00, 0x00, 0x00, 0x3F, 0x00, 0x3D, 0x38, 0x00, 0x00, 0x3E, 0x39, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x24,
    0x00, 0x00, 0x00, 0x23, 0x00, 0x22, 0x21, 0x00, 0x00, 0x00, 0x00, 0x1F,
    0x00, 0x1E, 0x20, 0x00, 0x00, 0x1D, 0x1C, 0x00, 0x1B, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x19, 0x00, 0x18, 0x1A, 0x00, 0x00, 0x17, 0x16, 0x00,
    0x15, 0x00, 0x00, 0x00, 0x00, 0x25, 0x14, 0x00, 0x13, 0x00, 0x00, 0x00,
    0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0E, 0x00, 0x0D, 0x0C, 0x00,
    0x00, 0x00, 0x00, 0x0A, 0x00, 0x09, 0x0B, 0x00, 0x00, 0x08, 0x07, 0x00,
    0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x03, 0x05, 0x00,
    0x00, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x10, 0x00,
    0x11, 0x00, 0x00, 0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x2B, 0x30, 0x00, 0x00, 0x2A, 0x2F, 0x00,
    0x31, 0x00, 0x00, 0x00, 0x00, 0x29, 0x2E, 0x00, 0x2D, 0x00, 0x00, 0x00,
    0x2C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x28, 0x00,
    0x27, 0x00, 0x00, 0x00, 0x26, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00
])

# Switch times
SWITCH_TIMES = [
    'Off', '0.1s', '0.2s', '0.3s', '0.4s', '0.5s', '0.6s', '0.7s', '0.8s',
    '0.9s', '1.0s', '1.1s', '1.2s', '1.3s', '1.4s', '1.5s', '1.6s', '1.7s',
    '1.8s', '1.9s', '2.0s', '2.1s', '2.2s', '2.3s', '2.4s', '2.5s', '2.6s',
    '2.7s', '2.8s', '2.9s', '3.0s', '3.1s', '3.2s', '3.3s', '3.4s', '3.5s',
    '3.6s', '3.7s', '3.8s', '3.9s', '4.0s', '4.1s', '4.2s', '4.3s', '4.4s',
    '4.5s', '4.6s', '4.7s', '4.8s', '4.9s', '5.0s', '5.1s', '5.2s', '5.3s',
    '5.4s', '5.5s', '5.6s', '5.7s', '5.8s', '5.9s', '6.0s', '6.1s', '6.2s',
    '6.3s', '6.4s', '6.5s', '6.6s', '6.7s', '6.8s', '6.9s', '7.0s', '7.1s',
    '7.2s', '7.3s', '7.4s', '7.5s', '7.6s', '7.7s', '7.8s', '7.9s', '8.0s',
    '8.1s', '8.2s', '8.3s', '8.4s', '8.5s', '8.6s', '8.7s', '8.8s', '8.9s',
    '9.0s', '9.1s', '9.2s', '9.3s', '9.4s', '9.5s', '9.6s', '9.7s', '9.8s',
    '9.9s', '10.0s', '10.1s', '10.2s', '10.3s', '10.4s', '10.5s', '10.6s',
    '10.7s', '10.8s', '10.9s', '11.0s', '11.1s', '11.2s', '11.3s', '11.4s',
    '11.5s', '11.6s', '11.7s', '11.8s', '11.9s', '12.0s', '12.1s', '12.2s',
    '12.3s', '12.4s', '12.5s', '12.6s', 'On'
]

CHECK_SIGN = '\u2714'
CROSS_MARK = '\u2718'


def decode_instruction(byte):
    '''Decode instruction for basic or extended loco decoder.

    See RCN-212 2.1
    https://normen.railcommunity.de/RCN-212.pdf
    or S-9.2.1
    https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/s-9.2.1_dcc_extended_packet_formats.pdf

    :param byte: Instruction byte
    :type byte: Integer
    :return: Instruction type
    :rtype: str
    '''
    if byte in (0b00000000, 0b00000001, 0b00000010, 0b00000011, 0b00001010,
                0b00001011, 0b00001111):
        return 'DECODER_CONTROL'
    elif byte in (0b00010010, 0b00010011):
        return 'CONSIST_CONTROL'
    elif byte in (0b00111100, 0b00111101, 0b00111110, 0b00111111):
        return 'ADVANCED_OPERATIONS'
    elif 0b01000000 <= byte <= 0b01111111:
        return 'SPEED_AND_DIRECTION'
    elif 0b10000000 <= byte <= 0b10111111:
        return 'FUNCTION_GROUP'
    elif byte in (0b11000000, 0b11000001, 0b11000010, 0b11000011, 0b11011000,
                  0b11011001, 0b11011010, 0b11011011, 0b11011100, 0b11011101,
                  0b11011110, 0b11011111):
        return 'FEATURE_EXPANSION'
    elif byte in (0b11100100, 0b11100101, 0b11100110, 0b11100111, 0b11101000,
                  0b11101001, 0b11101010, 0b11101011, 0b11101100, 0b11101101,
                  0b11101110, 0b11101111, 0b11110010, 0b11110011, 0b11110100,
                  0b11110101, 0b11110110, 0b11111001):
        return 'CV_ACCESS'
    elif byte == 0b11111110:
        return 'AUTOMATIC_LOGON'
    else:
        return 'UNKNOWN_SERVICE'


def decode_rggggg(rggggg, cv29_1):
    '''Decode speed from instruction byte of speed and direction command.

    :param rggggg: Instruction byte of speed and direction command
    :type rggggg: int
    :param cv29_1: CV29 bit1
    :type cv29_1: bool
    :return: Decoded speed from instruction byte
    :rtype: str
    '''
    if not (rggggg & 0b00001111):
        return 'Stop'
    elif not (rggggg & 0b00001110):
        return 'EStop'
    # 14-step speed
    speed = (rggggg & 0b00001111) - 1
    # 28-step mode
    if cv29_1:
        speed *= 2
        if speed and not (rggggg & 0b10000):
            speed -= 1
    return str(speed)


def decode_ssssssss(ssssssss):
    '''Decode analog channel from analog function group command.

    :param ssssssss: Instruction byte of analog function group command
    :type ssssssss: int
    :return: Decoded analog channel from instruction byte
    :rtype: str
    '''
    if ssssssss == 0:
        return '0 (Reserved)'
    elif 1 <= ssssssss <= 15:
        if ssssssss == 1:
            return '1 (Volume)'
        else:
            return '{} (Reserved)'.format(ssssssss)
    elif 16 <= ssssssss <= 31:
        return '{} (Position)'.format(ssssssss)
    elif 32 <= ssssssss <= 127:
        return '{} (Reserved)'.format(ssssssss)
    else:
        return str(ssssssss)


def decode_rggggggg(rggggggg):
    '''Decode speed from instruction byte of 128 speed step control command.

    :param rggggggg: Instruction byte of 128 speed step control command
    :type rggggggg: int
    :return: Decoded speed from instruction byte
    :rtype: str
    '''
    if not (rggggggg & 0b01111111):
        return 'Stop'
    elif not (rggggggg & 0b01111110):
        return 'EStop'
    return str((rggggggg & 0b01111111) - 1)


def crc8(bytes, init=0x00):
    '''Calculate CRC8 maxim.
 
    :param bytes: Bytes of a DCC packet
    :type bytes: bytearray
    :param init: Initial value
    :type init: int
    :return: CRC8
    :rtype: int
    '''
    crc = init & 0xFF
    for b in bytes:
        crc ^= b
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
    return crc


def exor(bytes):
    '''Calculate XOR checksum.

    :param bytes: Bytes of a DCC packet
    :type bytes: bytearray
    :return: XOR checksum
    :rtype: int
    '''
    result = 0
    for b in bytes:
        result ^= b
    return result


def bidi_validate_datagram(datagram):
    '''
    Docstring for bidi_validate_bytes
    
    :param datagram: Encoded BiDi datagram
    :type datagram: bytearray
    :return: True if datagram is valid, false otherwise
    :rtype: bool
    '''
    for b in datagram:
        popcount = bin(b).count('1')
        if b and popcount != 4:
            return False
    return True


def bidi_decode_datagram(datagram):
    '''Decode BiDi datagram.

    :param datagram: Encoded BiDi datagram
    :type datagram: bytearray
    :return: Decoded BiDi datagram
    :rtype: bytearray
    '''
    return bytearray(BIDI_DECODE[b] for b in datagram)


def bidi_make_data(datagram):
    '''Make data from decoded BiDi bytes.

    :param datagram: Decoded BiDi bytes
    :type datagram: bytearray
    :return: Data from decoded BiDi bytes
    :rtype: int
    '''
    data = 0
    for b in datagram:
        data <<= 6
        data |= b & 0x3F
    bit_count = len(datagram) * 6 - 4
    return data & ((1 << bit_count) - 1)


def bidi_datagram_size(bits):
    '''Calculate BiDi datagram size from number of payload bits.

    Currently the following payload sizes are officially supported:
    - 12 bit -> 2 bytes
    - 18 bits -> 3 bytes
    - 24 bits -> 4 bytes
    - 36 bits -> 6 bytes
    - 48 bits -> 8 bytes

    :param bits: Number of payload bits
    :type bits: int
    :return: BiDi datagram size
    :rtype: int
    '''
    return (bits + 5) // 6


def float16_to_float(h):
    '''Convert a 16-bit integer to a Python float, interpreting it as IEEE-754 binary16.

    :param h: 16-bit integer holding float16
    :type h: int
    :return: float
    :rtype: float
    '''
    s = (h >> 15) & 0x0001  # sign: 1 bit
    e = (h >> 10) & 0x001F  # exponent: 5 bits
    f = h & 0x03FF  # fraction: 10 bits
    if e == 0:
        if f == 0:
            # Zero (signed)
            return -0.0 if s else 0.0
        else:
            # Subnormal number
            return (-1)**s * (f / (1 << 10)) * 2**(-14)
    elif e == 0x1F:
        if f == 0:
            # Infinity
            return float('-inf') if s else float('inf')
        else:
            # NaN
            return float('nan')
    else:
        # Normalized number
        return (-1)**s * (1 + f / (1 << 10)) * 2**(e - 15)
