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

class Ps2Packet:
    def __init__(self, val, host=False, pok=False, ack=False):
        self.val  = val     #byte value
        self.host = host    #Host transmissions
        self.pok  = pok     #Parity ok
        self.ack  = ack     #Acknowlege ok for host transmission.

class Decoder(srd.Decoder):
    api_version = 3
    id = 'mouse'
    name = 'PS/2 Mouse'
    longname = 'PS/2 Mouse'
    desc = 'PS/2 mouse interface.'
    license = 'gplv2+'
    inputs = ['ps2_packet']
    outputs = []
    tags = ['PC']
    binary = (
        ('bytes', 'Bytes without explanation'),
        ('movement', 'Explanation of mouse movement and clicks'),
    )
    annotations = (
        ('Movement', 'Mouse movement packets'),
    )
    annotation_rows = (
        ('mov', 'Mouse Movement',(0,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.packets = []
        self.es = 0
        self.ss = 0

    def start(self):
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self,key,value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def mouse_movement(self):
        if len(self.packets) >= 3:
            if not self.packets[0].host:
                msg = ''
                [flags,x,y] = [p.val for p in self.packets[:3]]
                if flags & 1:
                    msg += 'L'
                if flags & 2:
                    msg += 'M'
                if flags & 4:
                    msg += 'R'
                if flags & 0x10:
                    x = x-256
                if flags & 0x20:
                    y = y-256
                if x != 0:
                    msg += ' X%+d' % x
                if flags & 0x40:
                    msg += '!!'
                if y != 0:
                    msg += ' Y%+d' % y
                if flags & 0x80:
                    msg += '!!'
                if msg == '':
                    msg = 'No Movement'
                ustring = ('\n' + msg).encode('UTF-8')
                self.put(self.ss,self.es,self.out_binary, [1,ustring] )
                self.put(self.ss,self.es,self.out_ann, [0,[msg]] )


    def print_packets(self):
        self.mouse_movement()
        tag = "Host: " if self.packets[-1].host else "Mouse:"
        octets = ' '.join(["%02X" % x.val for x in self.packets])
        unicode_string = ("\n"+tag+" "+octets).encode('UTF-8')
        self.put(self.ss,self.es,self.out_binary, [0,unicode_string] )
        self.reset()

    def mouse_ack(self,ss,es):
        self.put(ss,es,self.out_binary, [0,b' ACK'] )

    def decode(self,startsample,endsample,data):
        if len(self.packets) == 0:
            self.ss = startsample
        elif data.host != self.packets[-1].host:
            self.print_packets() 
            self.ss = startsample #Packets were cleared, need to set startsample again
            if data.val == 0xFA and not data.host:
                #Special case: acknowledge byte from mouse
                self.mouse_ack(startsample,endsample)
                self.reset()
                return
                
        self.packets.append(data)
        self.es = endsample
        #Mouse streaming packets are in 3s
        #Timing is not guaranteed because host can hold the clock at any point
        if len(self.packets)>2:
            self.print_packets()
