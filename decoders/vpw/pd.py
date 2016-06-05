##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Anthony Symons <antus@pcmhacking.net>
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

import sigrokdecode as srd

class SamplerateError(Exception):
    pass

def timeuf(t):
    return int (t * 1000.0 * 1000.0)

def normalize_time(t):
    if t >= 1.0:
        return '%d s' % t
    elif t >= 0.001:
        return '%d ms' % (t * 1000.0)
    elif t >= 0.000001:
        return '%d μs' % (t * 1000.0 * 1000.0)
    elif t >= 0.000000001:
        return '%d ns' % (t * 1000.0 * 1000.0 * 1000.0)
    else:
        return '%f' % t

class Decoder(srd.Decoder):
    api_version = 2
    id = 'vpw'
    name = 'VPW'
    longname = 'J1850 VPW Decoder'
    desc = 'Decode J1850 VPW 1x and 4x'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['timing']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('time', 'Time'),
        ('raw', 'Raw'),
        ('sof', 'SOF'),
        ('ifs', 'EOF/IFS'),
        ('data', 'Data'),
        ('packet', 'Packet'),
    )
    annotation_rows = (
        ('packet', 'Packet', (5,)),
        ('byte', 'Byte', (4,)),
        ('raw', 'Raw', (1,2,3,)),
        ('time', 'Time', (0,)),
    )

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.samplerate = None
        self.oldpin = None
        self.last_samplenum = None
        self.byte = 0      # the byte offset in the packet
        self.mode = 0      # for by packet decode
        self.data = 0      # the current byte
        self.datastart = 0 # sample number this byte started at
        self.csa = 0       # track the last byte seperately to retrospectively add the CS marker
        self.csb = 0
        self.count = 0     # which bit number we are up to 
        self.active = 0    # which logic level is considered active
        
        # vpw timings. ideal, min and max tollerances. 
        # From SAE J1850 1995 rev section 23.406
        
        self.sof = 200
        self.sofl = 164
        self.sofh = 245  # 240 by the spec, 245 so a 60us 4x sample will pass
        self.long = 128
        self.longl = 97
        self.longh = 170 # 164 by the spec but 170 for low sample rate tolerance.
        self.short = 64
        self.shortl = 24 # 35 by the spec, 24 to allow down to 6us as measured in practice for 4x @ 1mhz sampling
        self.shorth = 97
        self.ifs = 240
        self.spd = 1     # set to 4 when a 4x SOF is detected (VPW high speed frame)
  
    def handle_bit(self, b):
        self.data |= (b << 7-self.count) # MSB-first
        self.put(self.last_samplenum, self.samplenum, self.out_ann, [1, ["%d" % b]])
        if self.count == 0:
            self.datastart = self.last_samplenum
        if self.count == 7:
            self.csa = self.datastart # for CS
            self.csb = self.samplenum # for CS
            self.put(self.datastart, self.samplenum, self.out_ann, [4, ["%02X" % self.data]])
            # add protocol parsing here
            if self.byte == 0:
                self.put(self.datastart, self.samplenum, self.out_ann, [5, ['Priority','Prio','P']])
            elif self.byte == 1:
                self.put(self.datastart, self.samplenum, self.out_ann, [5, ['Destination','Dest','D']])
            elif self.byte == 2:
                self.put(self.datastart, self.samplenum, self.out_ann, [5, ['Source','Src','S']])
            elif self.byte == 3:
                self.put(self.datastart, self.samplenum, self.out_ann, [5, ['Mode','M']])
                self.mode=self.data
            elif self.mode == 1 and self.byte == 4: # mode 1 payload
                self.put(self.datastart, self.samplenum, self.out_ann, [5, ['Pid','P']])
            
            # prepare for next byte
            self.count = -1
            self.data = 0
            self.byte = self.byte + 1 # track packet offset
        self.count = self.count + 1
    
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self, ss, es, data):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        for (self.samplenum, (pin,)) in data:
            # Ignore identical samples early on (for performance reasons).
            if self.oldpin == pin:
                continue

            if self.oldpin is None:
                self.oldpin = pin
                self.last_samplenum = self.samplenum
                continue

            if self.oldpin != pin:
                samples = self.samplenum - self.last_samplenum
                txt=normalize_time(samples / self.samplerate)
                self.put(self.last_samplenum, self.samplenum, self.out_ann, [0, [txt]])
                t=timeuf(samples / self.samplerate)
                if self.state == 'IDLE': # detect and set speed from the size of sof
                    if pin==self.active and t in range(self.sofl , self.sofh):
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [1, ['1X SOF', 'S1', 'S']])
                        self.spd = 1
                        self.data = 0
                        self.count = 0
                        self.state = 'DATA'
                    elif pin==self.active and t in range(int(self.sofl/4) , int(self.sofh/4)):
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [1, ['4X SOF', 'S4', '4']])
                        self.spd = 4
                        self.data = 0
                        self.count = 0
                        self.state = 'DATA'
                        
                elif self.state == 'DATA':
                    if t >= int(self.ifs/self.spd):
                        self.state = 'IDLE'
                        self.put(self.last_samplenum, self.samplenum, self.out_ann, [1, ["EOF/IFS", "E"]]) # EOF=239-280 IFS=281+
                        self.put(self.csa, self.csb, self.out_ann, [5, ['Checksum','CS','C']]) # retrospective print of CS
                        self.byte = 0 # reset packet offset
                    elif t in range(int(self.shortl/self.spd), int(self.shorth/self.spd)):
                        if pin==self.active:
                            self.handle_bit(1)
                        else:
                            self.handle_bit(0)
                    elif t in range(int(self.longl/self.spd), int(self.longh/self.spd)):
                        if pin==self.active:
                            self.handle_bit(0)
                        else:
                            self.handle_bit(1)

                # Store data for next round.
                self.last_samplenum = self.samplenum
                self.oldpin = pin
