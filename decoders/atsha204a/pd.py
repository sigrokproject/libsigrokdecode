##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2018 Michalis Pappas <mpappas@fastmail.fm>
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

WORD_ADDR_RESET         = 0x00
WORD_ADDR_SLEEP         = 0x01
WORD_ADDR_IDLE          = 0x02
WORD_ADDR_COMMAND       = 0x03

WORD_ADDR = {0x00: 'RESET', 0x01: 'SLEEP', 0x02: 'IDLE', 0x03: 'COMMAND'}

OPCODE_DERIVE_KEY       = 0x1c
OPCODE_DEV_REV          = 0x30
OPCODE_GEN_DIG          = 0x15
OPCODE_HMAC             = 0x11
OPCODE_CHECK_MAC        = 0x28
OPCODE_LOCK             = 0x17
OPCODE_MAC              = 0x08
OPCODE_NONCE            = 0x16
OPCODE_PAUSE            = 0x01
OPCODE_RANDOM           = 0x1b
OPCODE_READ             = 0x02
OPCODE_SHA              = 0x47
OPCODE_UPDATE_EXTRA     = 0x20
OPCODE_WRITE            = 0x12

OPCODES = {
    0x01: 'Pause',
    0x02: 'Read',
    0x08: 'MAC',
    0x11: 'HMAC',
    0x12: 'Write',
    0x15: 'GenDig',
    0x16: 'Nonce',
    0x17: 'Lock',
    0x1b: 'Random',
    0x1c: 'DeriveKey',
    0x20: 'UpdateExtra',
    0x28: 'CheckMac',
    0x30: 'DevRev',
    0x47: 'SHA',
}

ZONE_CONFIG             = 0x00
ZONE_OTP                = 0x01
ZONE_DATA               = 0x02

ZONES = {0x00: 'CONFIG', 0x01: 'OTP', 0x02: 'DATA'}

STATUS_SUCCESS          = 0x00
STATUS_CHECKMAC_FAIL    = 0x01
STATUS_PARSE_ERROR      = 0x03
STATUS_EXECUTION_ERROR  = 0x0f
STATUS_READY            = 0x11
STATUS_CRC_COMM_ERROR   = 0xff

STATUS = {
    0x00: 'Command success',
    0x01: 'Checkmac failure',
    0x03: 'Parse error',
    0x0f: 'Execution error',
    0x11: 'Ready',
    0xff: 'CRC / communications error',
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'atsha204a'
    name = 'ATSHA204A'
    longname = 'Microchip ATSHA204A'
    desc = 'Microchip ATSHA204A CryptoAuthentication device'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['atsha204a']
    annotations = (
        ('waddr', 'Word address'),
        ('count', 'Count'),
        ('opcode', 'Opcode'),
        ('param1', 'Param1'),
        ('param2', 'Param2'),
        ('data', 'Data'),
        ('crc', 'CRC'),
        ('status', 'Status'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('frame', 'Frame', (0, 1, 2, 3, 4, 5, 6)),
        ('status', 'Status', (7,)),
        ('warnings', 'Warnings', (8,)),
    )

    def __init__(self):
        self.state = 'IDLE'
        self.waddr = self.opcode = -1
        self.ss_block = self.es_block = 0
        self.bytes = []

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def output_tx_bytes(self):
        b = self.bytes
        if len(b) < 1: # Ignore wakeup.
            return
        self.waddr = b[0][2]
        self.display_waddr(b[0])
        if self.waddr == WORD_ADDR_COMMAND:
            count = b[1][2]
            self.display_count(b[1])
            if len(b) - 1 != count:
                self.display_warning(b[0][0], b[-1][1],
                    'Invalid frame length: Got {}, expecting {} '.format(
                      len(b) - 1, count))
                return
            self.opcode = b[2][2]
            self.display_opcode(b[2])
            self.display_param1(b[3])
            self.display_param2([b[4], b[5]])
            self.display_data(b[6:-2])
            self.display_crc([b[-2], b[-1]])

    def output_rx_bytes(self):
        b = self.bytes
        count = b[0][2]
        self.display_count(b[0])
        if self.waddr == WORD_ADDR_RESET:
            self.display_data([b[1]])
            self.display_crc([b[2], b[3]])
            self.display_status(b[0][0], b[-1][1], b[1][2])
        elif self.waddr == WORD_ADDR_COMMAND:
            if count == 4: # Status / Error.
                self.display_data([b[1]])
                self.display_crc([b[2], b[3]])
                self.display_status(b[0][0], b[-1][1], b[1][2])
            else:
                self.display_data(b[1:-2])
                self.display_crc([b[-2], b[-1]])

    def display_waddr(self, data):
        self.put(data[0], data[1], self.out_ann, [0, ['Word addr: %s' % WORD_ADDR[data[2]]]])

    def display_count(self, data):
        self.put(data[0], data[1], self.out_ann, [1, ['Count: %s' % data[2]]])

    def display_opcode(self, data):
        self.put(data[0], data[1], self.out_ann, [2, ['Opcode: %s' % OPCODES[data[2]]]])

    def display_param1(self, data):
        if self.opcode in (OPCODE_CHECK_MAC, OPCODE_DEV_REV, OPCODE_HMAC, \
                OPCODE_MAC, OPCODE_NONCE, OPCODE_RANDOM, OPCODE_SHA):
            self.put(data[0], data[1], self.out_ann, [3, ['Mode: %02X' % data[2]]])
        elif self.opcode == OPCODE_DERIVE_KEY:
            self.put(data[0], data[1], self.out_ann, [3, ['Random: %s' % data[2]]])
        elif self.opcode == OPCODE_GEN_DIG:
            self.put(data[0], data[1], self.out_ann, [3, ['Zone: %s' % ZONES[data[2]]]])
        elif self.opcode == OPCODE_LOCK:
            self.put(data[0], data[1], self.out_ann, [3, ['Zone: {}, Summary: {}'.format(
                'DATA/OTP' if data[2] else 'CONFIG',
                'Ignored' if data[2] & 0x80 else 'Used')]])
        elif self.opcode == OPCODE_PAUSE:
            self.put(data[0], data[1], self.out_ann, [3, ['Selector: %02X' % data[2]]])
        elif self.opcode == OPCODE_READ:
            self.put(data[0], data[1], self.out_ann, [3, ['Zone: {}, Length: {}'.format(ZONES[data[2] & 0x03],
                '32 bytes' if data[2] & 0x90 else '4 bytes')]])
        elif self.opcode == OPCODE_WRITE:
            self.put(data[0], data[1], self.out_ann, [3, ['Zone: {}, Encrypted: {}, Length: {}'.format(ZONES[data[2] & 0x03],
                     'Yes' if data[2] & 0x40 else 'No', '32 bytes' if data[2] & 0x90 else '4 bytes')]])
        else:
            self.put(data[0], data[1], self.out_ann, [3, ['Param1: %02X' % data[2]]])

    def display_param2(self, data):
        if self.opcode == OPCODE_DERIVE_KEY:
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['TargetKey: {:02x} {:02x}'.format(data[1][2], data[0][2])]])
        elif self.opcode in (OPCODE_NONCE, OPCODE_PAUSE, OPCODE_RANDOM):
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['Zero: {:02x} {:02x}'.format(data[1][2], data[0][2])]])
        elif self.opcode in (OPCODE_HMAC, OPCODE_MAC, OPCODE_CHECK_MAC, OPCODE_GEN_DIG):
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['SlotID: {:02x} {:02x}'.format(data[1][2], data[0][2])]])
        elif self.opcode == OPCODE_LOCK:
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['Summary: {:02x} {:02x}'.format(data[1][2], data[0][2])]])
        elif self.opcode in (OPCODE_READ, OPCODE_WRITE):
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['Address: {:02x} {:02x}'.format(data[1][2], data[0][2])]])
        elif self.opcode == OPCODE_UPDATE_EXTRA:
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['NewValue: {:02x}'.format(data[0][2])]])
        else:
            self.put(data[0][0], data[1][1], self.out_ann, [4, ['-']])

    def display_data(self, data):
        if len(data) == 0:
            return
        if self.opcode == OPCODE_CHECK_MAC:
            self.put(data[0][0], data[31][1], self.out_ann, [5, ['ClientChal: %s' % ' '.join(format(i[2], '02x') for i in data[0:31])]])
            self.put(data[32][0], data[63][1], self.out_ann, [5, ['ClientResp: %s' % ' '.join(format(i[2], '02x') for i in data[32:63])]])
            self.put(data[64][0], data[76][1], self.out_ann, [5, ['OtherData: %s' % ' '.join(format(i[2], '02x') for i in data[64:76])]])
        elif self.opcode == OPCODE_DERIVE_KEY:
            self.put(data[0][0], data[31][1], self.out_ann, [5, ['MAC: %s' % ' '.join(format(i[2], '02x') for i in data)]])
        elif self.opcode == OPCODE_GEN_DIG:
            self.put(data[0][0], data[3][1], self.out_ann, [5, ['OtherData: %s' % ' '.join(format(i[2], '02x') for i in data)]])
        elif self.opcode == OPCODE_MAC:
            self.put(data[0][0], data[31][1], self.out_ann, [5, ['Challenge: %s' % ' '.join(format(i[2], '02x') for i in data)]])
        elif self.opcode == OPCODE_WRITE:
            if len(data) > 32: # Value + MAC.
                self.put(data[0][0], data[-31][1], self.out_ann, [5, ['Value: %s' % ' '.join(format(i[2], '02x') for i in data)]])
                self.put(data[-32][0], data[-1][1], self.out_ann, [5, ['MAC: %s' % ' '.join(format(i[2], '02x') for i in data)]])
            else: # Just value.
                self.put(data[0][0], data[-1][1], self.out_ann, [5, ['Value: %s' % ' '.join(format(i[2], '02x') for i in data)]])
        else:
            self.put(data[0][0], data[-1][1], self.out_ann, [5, ['Data: %s' % ' '.join(format(i[2], '02x') for i in data)]])

    def display_crc(self, data):
        self.put(data[0][0], data[1][1], self.out_ann, [6, ['CRC: {:02X} {:02X}'.format(data[0][2], data[1][2])]])

    def display_status(self, start, end, status):
        self.put(start, end, self.out_ann, [7, ['Status: %s' % STATUS[status]]])

    def display_warning(self, start, end, msg):
        self.put(start, end, self.out_ann, [8, ['Warning: %s' % msg]])

    def decode(self, ss, es, data):
        cmd, databyte = data

        # State machine.
        if self.state == 'IDLE':
            # Wait for an I²C START condition.
            if cmd != 'START':
                return
            self.state = 'GET SLAVE ADDR'
            self.ss_block = ss
        elif self.state == 'GET SLAVE ADDR':
            # Wait for an address read/write operation.
            if cmd == 'ADDRESS READ':
                self.state = 'READ REGS'
            elif cmd == 'ADDRESS WRITE':
                self.state = 'WRITE REGS'
        elif self.state == 'READ REGS':
            if cmd == 'DATA READ':
                self.bytes.append([ss, es, databyte])
            elif cmd == 'STOP':
                self.es_block = es
                # Reset the opcode before received data, as this causes
                # responses to be displayed incorrectly.
                self.opcode = -1
                self.output_rx_bytes()
                self.waddr = -1
                self.bytes = []
                self.state = 'IDLE'
        elif self.state == 'WRITE REGS':
            if cmd == 'DATA WRITE':
                self.bytes.append([ss, es, databyte])
            elif cmd == 'STOP':
                self.es_block = es
                self.output_tx_bytes()
                self.bytes = []
                self.state = 'IDLE'

