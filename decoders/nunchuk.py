##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

import sigrok

# FIXME: This is just some example input for testing purposes...
example_packets = [
    # START condition.
    {'type': 'S',  'range': (10, 11), 'data': None, 'ann': ''},

    # Nunchuk init: Write 0x40,0x00 to slave address 0x54.
    {'type': 'AW', 'range': (12, 13), 'data': 0x54, 'ann': ''},
    {'type': 'DW', 'range': (14, 15), 'data': 0x40, 'ann': ''},
    {'type': 'AW', 'range': (16, 17), 'data': 0x54, 'ann': ''},
    {'type': 'DW', 'range': (18, 19), 'data': 0x00, 'ann': ''},

    # Get data: Read 6 bytes of data.
    {'type': 'DR', 'range': (20, 21), 'data': 0x11, 'ann': ''},
    {'type': 'DR', 'range': (22, 23), 'data': 0x22, 'ann': ''},
    {'type': 'DR', 'range': (24, 25), 'data': 0x33, 'ann': ''},
    {'type': 'DR', 'range': (26, 27), 'data': 0x44, 'ann': ''},
    {'type': 'DR', 'range': (28, 29), 'data': 0x55, 'ann': ''},
    {'type': 'DR', 'range': (30, 31), 'data': 0x66, 'ann': ''},

    # STOP condition.
    {'type': 'P',  'range': (32, 33), 'data': None, 'ann': ''},
]

class Sample():
    def __init__(self, data):
        self.data = data
    def probe(self, probe):
        s = ord(self.data[probe / 8]) & (1 << (probe % 8))
        return True if s else False

def sampleiter(data, unitsize):
    for i in range(0, len(data), unitsize):
        yield(Sample(data[i:i+unitsize]))

class Decoder(sigrok.Decoder):
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
    probes = {}
    options = {}

    def __init__(self, **kwargs):
        self.probes = Decoder.probes.copy()

        # TODO: Don't hardcode the number of channels.
        self.channels = 8

        self.IDLE, self.START, self.NUNCHUK_SLAVE, self.INIT, \
        self.INITIALIZED = range(5)

        self.state = self.IDLE # TODO: Can we assume a certain initial state?

        self.sx = self.sy = self.ax = self.ay = self.az = self.bz = self.bc = 0

        self.databytecount = 0

    def start(self, metadata):
        self.unitsize = metadata['unitsize']

    def report(self):
        pass

    def decode(self, data):
        """Nintendo Wii Nunchuk decoder"""

        out = []
        o = {}

        # We should accept a list of samples and iterate...
        # for sample in sampleiter(data['data'], self.unitsize):
        for p in example_packets:

            # TODO: Eliminate the need for ord().
            # s = ord(sample.data)

            if p['type'] == 'S': # TODO: Handle 'Sr' here, too?
                self.state = self.START

            elif p['type'] == 'Sr':
                pass # FIXME

            elif p['type'] == 'AR':
                # TODO: Error/Warning, not supported, I think.
                pass

            elif p['type'] == 'AW':
                # The Wii Nunchuk always has slave address 0x54.
                # TODO: Handle this stuff more correctly.
                if p['data'] == 0x54:
                    pass # TODO
                else:
                    pass # TODO: What to do here? Ignore? Error?

            elif p['type'] == 'DR' and self.state == self.INITIALIZED:
                if self.databytecount == 0:
                    self.sx = p['data']
                elif self.databytecount == 1:
                    self.sy = p['data']
                elif self.databytecount == 2:
                    self.ax = p['data'] << 2
                elif self.databytecount == 3:
                    self.ay = p['data'] << 2
                elif self.databytecount == 4:
                    self.az = p['data'] << 2
                elif self.databytecount == 5:
                    self.bz =  (p['data'] & (1 << 0)) >> 0
                    self.bc =  (p['data'] & (1 << 1)) >> 1
                    self.ax |= (p['data'] & (3 << 2)) >> 2
                    self.ay |= (p['data'] & (3 << 4)) >> 4
                    self.az |= (p['data'] & (3 << 6)) >> 6
                    # del o
                    o = {'type': 'D', 'range': (0, 0), 'data': []}
                    o['data'] = [self.sx, self.sy, self.ax, self.ay, \
                                 self.az, self.bz, self.bc]
                    # sx = sy = ax = ay = az = bz = bc = 0
                else:
                    pass # TODO

                if 0 <= self.databytecount <= 5:
                    self.databytecount += 1

                # TODO: If 6 bytes read -> save and reset

            # TODO
            elif p['type'] == 'DR' and self.state != self.INITIALIZED:
                pass

            elif p['type'] == 'DW':
                if p['data'] == 0x40 and self.state == self.START:
                    self.state = self.INIT
                elif p['data'] == 0x00 and self.state == self.INIT:
                    o = {'type': 'I', 'range': (0, 0), 'data': []}
                    o['data'] = [0x40, 0x00]
                    out.append(o)
                    self.state = self.INITIALIZED
                else:
                    pass # TODO

            elif p['type'] == 'P':
                out.append(o)
                self.state = self.INITIALIZED
                self.databytecount = 0

        self.put(out)

