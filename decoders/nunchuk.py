##
## This file is part of the sigrok project.
##
## Copyright (C) 2010-2012 Uwe Hermann <uwe@hermann-uwe.de>
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
# Nintendo Wii Nunchuk decoder
#

#
# TODO: Description
#
# http://wiibrew.org/wiki/Wiimote/Extension_Controllers/Nunchuck
# http://todbot.com/blog/2008/02/18/wiichuck-wii-nunchuck-adapter-available/
# https://www.sparkfun.com/products/9281
#

import sigrokdecode as srd

# States
IDLE = 0
START = 1
NUNCHUK_SLAVE = 2
INIT = 3
INITIALIZED = 4

class Decoder(srd.Decoder):
    id = 'nunchuk'
    name = 'Nunchuk'
    longname = 'Nintendo Wii Nunchuk decoder'
    desc = 'Decodes the Nintendo Wii Nunchuk I2C-based protocol.'
    longdesc = '...'
    author = 'Uwe Hermann'
    email = 'uwe@hermann-uwe.de'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['nunchuck']
    probes = [] # TODO
    options = {}
    annotations = [
        ['TODO', 'TODO'], 
    ]

    def __init__(self, **kwargs):
        self.state = IDLE # TODO: Can we assume a certain initial state?
        self.sx = self.sy = self.ax = self.ay = self.az = self.bz = self.bc = 0
        self.databytecount = 0

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'nunchuk')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'nunchuk')

    def report(self):
        pass

    def decode(self, ss, es, data):

        cmd, databyte, ack_bit = data

        if cmd == 'START': # TODO: Handle 'Sr' here, too?
            self.state = START

        elif cmd == 'START_REPEAT':
            pass # FIXME

        elif cmd == 'ADDRESS_READ':
            # TODO: Error/Warning, not supported, I think.
            pass

        elif cmd == 'ADDRESS_WRITE':
            # The Wii Nunchuk always has slave address 0x54.
            # TODO: Handle this stuff more correctly.
            if databyte == 0x54:
                pass # TODO
            else:
                pass # TODO: What to do here? Ignore? Error?

        elif cmd == 'DATA_READ' and self.state == INITIALIZED:
            if self.databytecount == 0:
                self.sx = databyte
            elif self.databytecount == 1:
                self.sy = databyte
            elif self.databytecount == 2:
                self.ax = databyte << 2
            elif self.databytecount == 3:
                self.ay = databyte << 2
            elif self.databytecount == 4:
                self.az = databyte << 2
            elif self.databytecount == 5:
                self.bz =  (databyte & (1 << 0)) >> 0
                self.bc =  (databyte & (1 << 1)) >> 1
                self.ax |= (databyte & (3 << 2)) >> 2
                self.ay |= (databyte & (3 << 4)) >> 4
                self.az |= (databyte & (3 << 6)) >> 6

                d = 'sx = 0x%02x, sy = 0x%02x, ax = 0x%02x, ay = 0x%02x, ' \
                    'az = 0x%02x, bz = 0x%02x, bc = 0x%02x' % (self.sx, \
                    self.sy, self.ax, self.ay, self.az, self.bz, self.bc)
                self.put(ss, es, self.out_ann, [0, [d]])

                self.sx = self.sy = self.ax = self.ay = self.az = 0
                self.bz = self.bc = 0
            else:
                pass # TODO

            if 0 <= self.databytecount <= 5:
                self.databytecount += 1

            # TODO: If 6 bytes read -> save and reset

        # TODO
        elif cmd == 'DATA_READ' and self.state != INITIALIZED:
            pass

        elif cmd == 'DATA_WRITE':
            if self.state == IDLE:
                self.state = INITIALIZED
            return
    
            if databyte == 0x40 and self.state == START:
                self.state = INIT
            elif databyte == 0x00 and self.state == INIT:
                self.put(ss, es, self.out_ann, [0, ['Initialize nunchuk']])
                self.state = INITIALIZED
            else:
                pass # TODO

        elif cmd == 'STOP':
            self.state = INITIALIZED
            self.databytecount = 0

