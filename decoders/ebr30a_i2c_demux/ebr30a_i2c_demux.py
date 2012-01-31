##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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

#
# TrekStor EBR30-a I2C demux protocol decoder
#
# Takes an I2C stream as input and outputs 3 different I2C streams, for the
# 3 different I2C devices on the TrekStor EBR30-a eBook reader (which are all
# physically connected to the same SCL/SDA lines).
#
# I2C slave addresses:
#
#  - AXP199 battery management chip: 0x69/0x68 (8bit R/W), 0x34 (7bit)
#  - H8563S RTC chip: 0xa3/0xa2 (8bit R/W), 0x51 (7bit)
#  - Unknown accelerometer chip: 0x2b/0x2a (8bit R/W), 0x15 (7bit)
#

import sigrokdecode as srd

# I2C devices
AXP199 = 0
H8563S = 1
ACCEL = 2

class Decoder(srd.Decoder):
    api_version = 1
    id = 'ebr30a_i2c_demux'
    name = 'EBR30-a I2C demux'
    longname = 'TrekStor EBR30-a I2C demux'
    desc = 'TODO.'
    longdesc = 'TODO.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['i2c-axp199', 'i2c-h8563s', 'i2c-accel'] # TODO: type vs. inst.
    probes = []
    optional_probes = []
    options = {}
    annotations = []

    def __init__(self, **kwargs):
        self.packets = []
        self.stream = -1

    def start(self, metadata):
        self.out_proto = []
        self.out_proto.append(self.add(srd.OUTPUT_PROTO, 'i2c-axp199'))
        self.out_proto.append(self.add(srd.OUTPUT_PROTO, 'i2c-h8563s'))
        self.out_proto.append(self.add(srd.OUTPUT_PROTO, 'i2c-accel'))
        # TODO: Annotations?

    def report(self):
        pass

    # Grab I2C packets into a local cache, until an I2C STOP condition
    # packet comes along. At some point before that STOP condition, there
    # will have been an ADDRESS READ or ADDRESS WRITE which contains the
    # I2C address of the slave that the master wants to talk to.
    # We use this slave address to figure out which output stream should
    # get the whole chunk of packets (from START to STOP).
    def decode(self, ss, es, data):

        cmd, databyte, ack_bit = data

        # Add the I2C packet to our local cache.
        self.packets += [[ss, es, data]]

        if cmd in ('ADDRESS READ', 'ADDRESS WRITE'):
            # print(hex(databyte))
            if databyte == 0x34:
                self.stream = AXP199
            elif databyte == 0x51:
                self.stream = H8563S
            elif databyte == 0x15:
                self.stream = ACCEL
            else:
                pass # TODO: Error?
            # TODO: Can there be two ADDRESS READ/WRITE with two different
            #       slave addresses before any STOP occurs?
        elif cmd == 'STOP':
            if self.stream != -1:
                # Send the whole chunk of I2C packets to the correct stream.
                for p in self.packets:
                    # print(self.out_proto[self.stream], p)
                    self.put(p[0], p[1], self.out_proto[self.stream], p[2])
            else:
                print('Error: Could not determine correct stream!') # FIXME
            self.packets = []
            self.stream = -1
        else:
            pass # Do nothing, only add the I2C packet to our cache.

