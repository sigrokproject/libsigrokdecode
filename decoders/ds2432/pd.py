##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2017 Kevin Redon <kingkevin@cuvoodoo.info>
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

# Dictionary of FUNCTION commands and their names.
commands = {
    0x0f: 'Write scratchpad',
    0xaa: 'Read scratchpad',
    0x55: 'Copy scratchpad',
    0xf0: 'Read memory',
    0x5a: 'Load first secret',
    0x33: 'Compute next secret',
    0xa5: 'Read authenticated page',
}

# Maxim DS2432 family code, present at the end of the ROM code.
family_code = 0x33

# Calculate the CRC-16 checksum.
# Initial value: 0x0000, xor-in: 0x0000, polynom 0x8005, xor-out: 0xffff.
def crc16(byte_array):
    reverse = 0xa001 # Use the reverse polynom to make algo simpler.
    crc = 0x0000 # Initial value.
    # Reverse CRC calculation.
    for byte in byte_array:
        for bit in range(8):
            if (byte ^ crc) & 1:
                crc = (crc >> 1) ^ reverse
            else:
                crc >>= 1
            byte >>= 1
    crc ^= 0xffff # Invert CRC.
    return crc

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ds2432'
    name = 'DS2432'
    longname = 'Maxim DS2432 1-Wire 1k-Bit Protected EEPROM with SHA-1 Engine'
    desc = '1-Wire 1k-Bit Protected EEPROM with SHA-1 Engine.'
    license = 'gplv2+'
    inputs = ['onewire_network']
    outputs = ['ds2432']
    annotations = (
        ('text', 'Human-readable text'),
    )

    def __init__(self):
        # Bytes for function command.
        self.bytes = []

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def decode(self, ss, es, data):
        code, val = data

        if code == 'RESET/PRESENCE':
            self.ss, self.es = ss, es
            self.putx([0, ['Reset/presence: %s'
                           % ('true' if val else 'false')]])
            self.bytes = []
        elif code == 'ROM':
            self.ss, self.es = ss, es
            self.putx([0, ['ROM: 0x%016x (family code %s to 0x%02x)'
                           % (val, 'matches' if family_code == (val & 0xff)
                               else 'does not match', family_code),
                           'ROM: 0x%016x (family code %s)'
                           % (val, 'match' if family_code == (val & 0xff)
                               else 'mismatch')]])
            self.bytes = []
        elif code == 'DATA':
            self.bytes.append(val)
            if 1 == len(self.bytes):
                self.ss, self.es = ss, es
                if val not in commands:
                    self.putx([0, ['Unrecognized command: 0x%02x' % val]])
                else:
                    self.putx([0, ['Function command: %s (0x%02x)'
                                   % (commands[val], val)]])
            elif 0x0f == self.bytes[0]: # Write scratchpad
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 3 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Target address: 0x%04x'
                                   % ((self.bytes[2] << 8) + self.bytes[1])]])
                elif 4 == len(self.bytes):
                    self.ss = ss
                elif 11 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Data: ' + (','.join(format(n, '#04x')
                                       for n in self.bytes[3:11]))]])
                elif 12 == len(self.bytes):
                    self.ss = ss
                elif 13 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['CRC: '
                        + ('ok' if crc16(self.bytes[0:11]) == (self.bytes[11]
                        + (self.bytes[12] << 8)) else 'error')]])
            elif 0xaa == self.bytes[0]: # Read scratchpad
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 3 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Target address: 0x%04x'
                                   % ((self.bytes[2] << 8) + self.bytes[1])]])
                elif 4 == len(self.bytes):
                    self.ss, self.es = ss, es
                    self.putx([0, ['Data status (E/S): 0x%02x'
                                   % (self.bytes[3])]])
                elif 5 == len(self.bytes):
                    self.ss = ss
                elif 12 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Data: ' + (','.join(format(n, '#04x')
                                       for n in self.bytes[4:12]))]])
                elif 13 == len(self.bytes):
                    self.ss = ss
                elif 14 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['CRC: '
                        + ('ok' if crc16(self.bytes[0:12]) == (self.bytes[12]
                        + (self.bytes[13] << 8)) else 'error')]])
            elif 0x5a == self.bytes[0]: # Load first secret
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 4 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Authorization pattern (TA1, TA2, E/S): '
                        + (','.join(format(n, '#04x')
                            for n in self.bytes[1:4]))]])
                elif 4 < len(self.bytes):
                    self.ss, self.es = ss, es
                    if (0xaa == self.bytes[-1] or 0x55 == self.bytes[-1]):
                        self.putx([0, ['End of operation']])
            elif 0x33 == self.bytes[0]: # Compute next secret
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 3 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Target address: 0x%04x'
                                   % ((self.bytes[2] << 8) + self.bytes[1])]])
                elif 3 < len(self.bytes):
                    self.ss, self.es = ss, es
                    if (0xaa == self.bytes[-1] or 0x55 == self.bytes[-1]):
                        self.putx([0, ['End of operation']])
            elif 0x55 == self.bytes[0]: # Copy scratchpad
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 4 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Authorization pattern (TA1, TA2, E/S): '
                        + (','.join(format(n, '#04x')
                            for n in self.bytes[1:4]))]])
                elif 5 == len(self.bytes):
                    self.ss = ss
                elif 24 == len(self.bytes):
                    self.es = es
                    mac = ','.join(format(n, '#04x') for n in self.bytes[4:24])
                    self.putx([0, ['Message authentication code: ' + mac,
                                   'MAC: ' + mac]])
                elif 24 < len(self.bytes):
                    self.ss, self.es = ss, es
                    if (0xaa == self.bytes[-1] or 0x55 == self.bytes[-1]):
                        self.putx([0, ['Operation succeeded']])
                    elif (0 == self.bytes[-1]):
                        self.putx([0, ['Operation failed']])
            elif 0xa5 == self.bytes[0]: # Read authenticated page
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 3 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Target address: 0x%04x'
                                   % ((self.bytes[2] << 8) + self.bytes[1])]])
                elif 4 == len(self.bytes):
                    self.ss = ss
                elif 35 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Data: ' + (','.join(format(n, '#04x')
                                       for n in self.bytes[3:35]))]])
                elif 36 == len(self.bytes):
                    self.ss, self.es = ss, es
                    self.putx([0, ['Padding: '
                        + ('ok' if 0xff == self.bytes[-1] else 'error')]])
                elif 37 == len(self.bytes):
                    self.ss = ss
                elif 38 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['CRC: '
                        + ('ok' if crc16(self.bytes[0:36]) == (self.bytes[36]
                        + (self.bytes[37] << 8)) else 'error')]])
                elif 39 == len(self.bytes):
                    self.ss = ss
                elif 58 == len(self.bytes):
                    self.es = es
                    mac = ','.join(format(n, '#04x') for n in self.bytes[38:58])
                    self.putx([0, ['Message authentication code: ' + mac,
                                   'MAC: ' + mac]])
                elif 59 == len(self.bytes):
                    self.ss = ss
                elif 60 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['MAC CRC: '
                        + ('ok' if crc16(self.bytes[38:58]) == (self.bytes[58]
                        + (self.bytes[59] << 8)) else 'error')]])
                elif 60 < len(self.bytes):
                    self.ss, self.es = ss, es
                    if (0xaa == self.bytes[-1] or 0x55 == self.bytes[-1]):
                        self.putx([0, ['Operation completed']])
            elif 0xf0 == self.bytes[0]: # Read memory
                if 2 == len(self.bytes):
                    self.ss = ss
                elif 3 == len(self.bytes):
                    self.es = es
                    self.putx([0, ['Target address: 0x%04x'
                                   % ((self.bytes[2] << 8) + self.bytes[1])]])
                elif 3 < len(self.bytes):
                    self.ss, self.es = ss, es
                    self.putx([0, ['Data: 0x%02x' % (self.bytes[-1])]])
