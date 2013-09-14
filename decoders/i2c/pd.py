##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2010-2013 Uwe Hermann <uwe@hermann-uwe.de>
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

# I2C protocol decoder

# TODO: Look into arbitration, collision detection, clock synchronisation, etc.
# TODO: Implement support for 10bit slave addresses.
# TODO: Implement support for inverting SDA/SCL levels (0->1 and 1->0).
# TODO: Implement support for detecting various bus errors.

import sigrokdecode as srd

'''
Protocol output format:

I2C packet:
[<cmd>, <data>]

<cmd> is one of:
 - 'START' (START condition)
 - 'START REPEAT' (Repeated START condition)
 - 'ADDRESS READ' (Slave address, read)
 - 'ADDRESS WRITE' (Slave address, write)
 - 'DATA READ' (Data, read)
 - 'DATA WRITE' (Data, write)
 - 'STOP' (STOP condition)
 - 'ACK' (ACK bit)
 - 'NACK' (NACK bit)

<data> is the data or address byte associated with the 'ADDRESS*' and 'DATA*'
command. Slave addresses do not include bit 0 (the READ/WRITE indication bit).
For example, a slave address field could be 0x51 (instead of 0xa2).
For 'START', 'START REPEAT', 'STOP', 'ACK', and 'NACK' <data> is None.
'''

# CMD: [annotation-type-index, long annotation, short annotation]
proto = {
    'START':           [0, 'Start',         'S'],
    'START REPEAT':    [1, 'Start repeat',  'Sr'],
    'STOP':            [2, 'Stop',          'P'],
    'ACK':             [3, 'ACK',           'A'],
    'NACK':            [4, 'NACK',          'N'],
    'ADDRESS READ':    [5, 'Address read',  'AR'],
    'ADDRESS WRITE':   [6, 'Address write', 'AW'],
    'DATA READ':       [7, 'Data read',     'DR'],
    'DATA WRITE':      [8, 'Data write',    'DW'],
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'i2c'
    name = 'I2C'
    longname = 'Inter-Integrated Circuit'
    desc = 'Two-wire, multi-master, serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2c']
    probes = [
        {'id': 'scl', 'name': 'SCL', 'desc': 'Serial clock line'},
        {'id': 'sda', 'name': 'SDA', 'desc': 'Serial data line'},
    ]
    optional_probes = []
    options = {
        'address_format': ['Displayed slave address format', 'shifted'],
    }
    annotations = [
        ['Start', 'Start condition'],
        ['Repeat start', 'Repeat start condition'],
        ['Stop', 'Stop condition'],
        ['ACK', 'ACK'],
        ['NACK', 'NACK'],
        ['Address read', 'Address read'],
        ['Address write', 'Address write'],
        ['Data read', 'Data read'],
        ['Data write', 'Data write'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.startsample = -1
        self.samplenum = None
        self.bitcount = 0
        self.databyte = 0
        self.wr = -1
        self.is_repeat_start = 0
        self.state = 'FIND START'
        self.oldscl = 1
        self.oldsda = 1
        self.oldpins = [1, 1]

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'i2c')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'i2c')

    def report(self):
        pass

    def putx(self, data):
        self.put(self.startsample, self.samplenum, self.out_ann, data)

    def putp(self, data):
        self.put(self.startsample, self.samplenum, self.out_proto, data)

    def is_start_condition(self, scl, sda):
        # START condition (S): SDA = falling, SCL = high
        if (self.oldsda == 1 and sda == 0) and scl == 1:
            return True
        return False

    def is_data_bit(self, scl, sda):
        # Data sampling of receiver: SCL = rising
        if self.oldscl == 0 and scl == 1:
            return True
        return False

    def is_stop_condition(self, scl, sda):
        # STOP condition (P): SDA = rising, SCL = high
        if (self.oldsda == 0 and sda == 1) and scl == 1:
            return True
        return False

    def found_start(self, scl, sda):
        self.startsample = self.samplenum
        cmd = 'START REPEAT' if (self.is_repeat_start == 1) else 'START'
        self.putp([cmd, None])
        self.putx([proto[cmd][0], proto[cmd][1:]])
        self.state = 'FIND ADDRESS'
        self.bitcount = self.databyte = 0
        self.is_repeat_start = 1
        self.wr = -1

    # Gather 8 bits of data plus the ACK/NACK bit.
    def found_address_or_data(self, scl, sda):
        # Address and data are transmitted MSB-first.
        self.databyte <<= 1
        self.databyte |= sda

        if self.bitcount == 0:
            self.startsample = self.samplenum

        # Return if we haven't collected all 8 + 1 bits, yet.
        self.bitcount += 1
        if self.bitcount != 8:
            return

        # We triggered on the ACK/NACK bit, but won't report that until later.
        self.startsample -= 1

        d = self.databyte
        if self.state == 'FIND ADDRESS':
            # The READ/WRITE bit is only in address bytes, not data bytes.
            self.wr = 0 if (self.databyte & 1) else 1
            if self.options['address_format'] == 'shifted':
                d = d >> 1

        if self.state == 'FIND ADDRESS' and self.wr == 1:
            cmd = 'ADDRESS WRITE'
        elif self.state == 'FIND ADDRESS' and self.wr == 0:
            cmd = 'ADDRESS READ'
        elif self.state == 'FIND DATA' and self.wr == 1:
            cmd = 'DATA WRITE'
        elif self.state == 'FIND DATA' and self.wr == 0:
            cmd = 'DATA READ'

        self.putp([cmd, d])
        self.putx([proto[cmd][0], ['%s: %02X' % (proto[cmd][1], d),
                  '%s: %02X' % (proto[cmd][2], d), '%02X' % d]])

        # Done with this packet.
        self.startsample = -1
        self.bitcount = self.databyte = 0
        self.state = 'FIND ACK'

    def get_ack(self, scl, sda):
        self.startsample = self.samplenum
        cmd = 'NACK' if (sda == 1) else 'ACK'
        self.putp([cmd, None])
        self.putx([proto[cmd][0], proto[cmd][1:]])
        # There could be multiple data bytes in a row, so either find
        # another data byte or a STOP condition next.
        self.state = 'FIND DATA'

    def found_stop(self, scl, sda):
        self.startsample = self.samplenum
        cmd = 'STOP'
        self.putp([cmd, None])
        self.putx([proto[cmd][0], proto[cmd][1:]])
        self.state = 'FIND START'
        self.is_repeat_start = 0
        self.wr = -1

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (scl, sda) = pins, pins

            # TODO: Wait until the bus is idle (SDA = SCL = 1) first?

            # State machine.
            if self.state == 'FIND START':
                if self.is_start_condition(scl, sda):
                    self.found_start(scl, sda)
            elif self.state == 'FIND ADDRESS':
                if self.is_data_bit(scl, sda):
                    self.found_address_or_data(scl, sda)
            elif self.state == 'FIND DATA':
                if self.is_data_bit(scl, sda):
                    self.found_address_or_data(scl, sda)
                elif self.is_start_condition(scl, sda):
                    self.found_start(scl, sda)
                elif self.is_stop_condition(scl, sda):
                    self.found_stop(scl, sda)
            elif self.state == 'FIND ACK':
                if self.is_data_bit(scl, sda):
                    self.get_ack(scl, sda)
            else:
                raise Exception('Invalid state: %s' % self.state)

            # Save current SDA/SCL values for the next round.
            self.oldscl = scl
            self.oldsda = sda

