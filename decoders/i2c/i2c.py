##
## This file is part of the sigrok project.
##
## Copyright (C) 2010-2011 Uwe Hermann <uwe@hermann-uwe.de>
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
# TODO: Handle clock stretching.
# TODO: Handle combined messages / repeated START.
# TODO: Implement support for 7bit and 10bit slave addresses.
# TODO: Implement support for inverting SDA/SCL levels (0->1 and 1->0).
# TODO: Implement support for detecting various bus errors.
# TODO: I2C address of slaves.
# TODO: Handle multiple different I2C devices on same bus
#       -> we need to decode multiple protocols at the same time.

import sigrokdecode as srd

# Annotation feed formats
ANN_SHIFTED = 0
ANN_SHIFTED_SHORT = 1
ANN_RAW = 2

# Values are verbose and short annotation, respectively.
proto = {
    'START':           ['START',         'S'],
    'START REPEAT':    ['START REPEAT',  'Sr'],
    'STOP':            ['STOP',          'P'],
    'ACK':             ['ACK',           'A'],
    'NACK':            ['NACK',          'N'],
    'ADDRESS READ':    ['ADDRESS READ',  'AR'],
    'ADDRESS WRITE':   ['ADDRESS WRITE', 'AW'],
    'DATA READ':       ['DATA READ',     'DR'],
    'DATA WRITE':      ['DATA WRITE',    'DW'],
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
        'addressing': ['Slave addressing (in bits)', 7], # 7 or 10
    }
    annotations = [
        # ANN_SHIFTED
        ['7-bit shifted hex',
         'Read/write bit shifted out from the 8-bit I2C slave address'],
        # ANN_SHIFTED_SHORT
        ['7-bit shifted hex (short)',
         'Read/write bit shifted out from the 8-bit I2C slave address'],
        # ANN_RAW
        ['Raw hex', 'Unaltered raw data'],
    ]

    def __init__(self, **kwargs):
        self.startsample = -1
        self.samplenum = None
        self.bitcount = 0
        self.databyte = 0
        self.wr = -1
        self.is_repeat_start = 0
        self.state = 'FIND START'
        self.oldscl = None
        self.oldsda = None
        self.oldpins = None

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'i2c')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'i2c')

    def report(self):
        pass

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
        self.put(self.out_proto, [cmd, None])
        self.put(self.out_ann, [ANN_SHIFTED, [proto[cmd][0]]])
        self.put(self.out_ann, [ANN_SHIFTED_SHORT, [proto[cmd][1]]])

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

        # Send raw output annotation before we start shifting out
        # read/write and ACK/NACK bits.
        self.put(self.out_ann, [ANN_RAW, ['0x%.2x' % self.databyte]])

        if self.state == 'FIND ADDRESS':
            # The READ/WRITE bit is only in address bytes, not data bytes.
            self.wr = 0 if (self.databyte & 1) else 1
            d = self.databyte >> 1
        elif self.state == 'FIND DATA':
            d = self.databyte

        if self.state == 'FIND ADDRESS' and self.wr == 1:
            cmd = 'ADDRESS WRITE'
        elif self.state == 'FIND ADDRESS' and self.wr == 0:
            cmd = 'ADDRESS READ'
        elif self.state == 'FIND DATA' and self.wr == 1:
            cmd = 'DATA WRITE'
        elif self.state == 'FIND DATA' and self.wr == 0:
            cmd = 'DATA READ'

        self.put(self.out_proto, [cmd, d])
        self.put(self.out_ann, [ANN_SHIFTED, [proto[cmd][0], '0x%02x' % d]])
        self.put(self.out_ann, [ANN_SHIFTED_SHORT, [proto[cmd][1], '0x%02x' % d]])

        # Done with this packet.
        self.startsample = -1
        self.bitcount = self.databyte = 0
        self.state = 'FIND ACK'

    def get_ack(self, scl, sda):
        self.startsample = self.samplenum
        ack_bit = 'NACK' if (sda == 1) else 'ACK'
        self.put(self.out_proto, [ack_bit, None])
        self.put(self.out_ann, [ANN_SHIFTED, [proto[ack_bit][0]]])
        self.put(self.out_ann, [ANN_SHIFTED_SHORT, [proto[ack_bit][1]]])
        # There could be multiple data bytes in a row, so either find
        # another data byte or a STOP condition next.
        self.state = 'FIND DATA'

    def found_stop(self, scl, sda):
        self.startsample = self.samplenum
        self.put(self.out_proto, ['STOP', None])
        self.put(self.out_ann, [ANN_SHIFTED, [proto['STOP'][0]]])
        self.put(self.out_ann, [ANN_SHIFTED_SHORT, [proto['STOP'][1]]])

        self.state = 'FIND START'
        self.is_repeat_start = 0
        self.wr = -1

    def put(self, output_id, data):
        # Inject sample range into the call up to sigrok.
        super(Decoder, self).put(self.startsample, self.samplenum, output_id, data)

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (scl, sda) = pins, pins

            # First sample: Save SCL/SDA value.
            if self.oldscl == None:
                self.oldscl = scl
                self.oldsda = sda
                continue

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
                raise Exception('Invalid state %d' % self.STATE)

            # Save current SDA/SCL values for the next round.
            self.oldscl = scl
            self.oldsda = sda

