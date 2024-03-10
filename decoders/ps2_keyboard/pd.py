##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2023 Marshal Horn <kamocat@gmail.com>
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
from .sc import key_decode

class Ps2Packet:
    def __init__(self, val, host=False, pok=False, ack=False):
        self.val  = val     #byte value
        self.host = host    #Host transmissions
        self.pok  = pok     #Parity ok
        self.ack  = ack     #Acknowlege ok for host transmission.

class Ann:
    PRESS,RELEASE,ACK = range(3)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ps2_keyboard'
    name = 'PS/2 Keyboard'
    longname = 'PS/2 Keyboard'
    desc = 'PS/2 keyboard interface.'
    license = 'gplv2+'
    inputs = ['ps2']
    outputs = []
    tags = ['PC']
    binary = (
        ('Keys', 'Key presses'),
    )
    annotations = (
        ('Press', 'Key pressed'),
        ('Release', 'Key released'),
        ('Ack', 'Acknowledge'),
    )
    annotation_rows = (
        ('keys', 'key presses and releases',(0,1,2)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.sw = 0 #for switch statement
        self.ann = Ann.PRESS #defualt to keypress
        self.extended = False

    def start(self):
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self,startsample,endsample,data):
        if data.host:
            # Ignore host commands or interrupted keycodes
            self.reset()
            return
        if self.sw < 1:
            self.ss = startsample
            self.sw = 1
        if self.sw < 2:
            if data.val == 0xF0: #Break code
                self.ann = Ann.RELEASE
                return
            elif data.val == 0xE0: #Extended character
                self.extended = True
                return
            elif data.val == 0xFA: #Acknowledge code
                c = ['Acknowledge','ACK']
                self.ann = Ann.ACK
                self.sw = 4
        if self.sw < 3:
            c = key_decode(data.val, self.extended)

        self.put(self.ss,endsample,self.out_ann,[self.ann,c])
        if self.ann == Ann.PRESS:
            self.put(self.ss,endsample,self.out_binary,[0,c[-1].encode('UTF-8')])
        self.reset()

