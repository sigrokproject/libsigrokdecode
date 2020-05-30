##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Tomas Mudrunka <harvie@github>
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included in all
## copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 3
    id = 'caliper'
    name = 'Caliper'
    longname = 'Digital calipers'
    desc = 'Protocol of cheap generic digital calipers'
    license = 'mit'
    inputs = ['logic']
    outputs = []
    channels = (
         {'id': 'clk', 'name': 'CLK', 'desc': 'Serial clock line'},
         {'id': 'data', 'name': 'DATA', 'desc': 'Serial data line'},
    )
    options = (
         {'id': 'timeout_ms', 'desc': 'Timeout packet after X ms, 0 to disable', 'default': 10},
         {'id': 'unit', 'desc': 'Convert units', 'default': 'keep', 'values': ('keep', 'mm', 'inch')},
         {'id': 'changes', 'desc': 'Changes only', 'default': 'no', 'values': ('no', 'yes')},
    )
    tags = ['Analog/digital', 'IC', 'Sensor']
    annotations = (
        ('measurements', 'Measurements'),
        ('warning', 'Warnings'),
    )
    annotation_rows = (
        ('measurements', 'Measurements', (0,)),
        ('warnings', 'Warnings', (1,)),
    )

    def reset_data(self):
        self.bits = 0
        self.number = 0
        self.flags = 0

    def metadata(self, key, value):
       if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def __init__(self):
        self.reset()

    def reset(self):
        self.ss_cmd, self.es_cmd = 0, 0
        self.reset_data()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    #Switch bit order of variable x, which is l bit long
    def bitr(self,x,l):
        return int(bin(x)[2:].zfill(l)[::-1], 2)

    def decode(self):
        self.last_measurement = None
        while True:
            clk, data = self.wait([{0: 'r'},{'skip': round(self.samplerate/1000)}])
            #print([clk,data])

            #Timeout after inactivity
            if(self.options['timeout_ms'] > 0):
                if self.samplenum > self.es_cmd + (self.samplerate/(1000/self.options['timeout_ms'])):
                    if self.bits > 0:
                        self.put(self.ss_cmd, self.samplenum, self.out_ann, [1, ['timeout with %s bits in buffer'%(self.bits),'timeout']])
                    self.reset()

            #Do nothing if there was timeout without rising clock edge
            if self.matched == (False, True):
                continue

            #Store position of last activity
            self.es_cmd = self.samplenum

            #Store position of first bit
            if self.ss_cmd == 0:
                self.ss_cmd = self.samplenum

            #Shift in measured number
            if self.bits < 16:
                self.number = (self.number << 1) | (data & 0b1)
                self.bits+=1
                continue

            #Shift in flag bits
            if self.bits < 24:
                self.flags = (self.flags << 1) | (data & 0b1)
                self.bits+=1
                if self.bits < 24:
                    continue
                #Hooray! We got last bit of data
                self.es_cmd = self.samplenum

            #Do actual decoding

            #print(format(self.flags, '08b'));

            negative = ((self.flags & 0b00001000) >> 3)
            inch = (self.flags & 0b00000001)

            number = self.bitr(self.number, 16)

            #print(format(number, '016b'))

            if negative > 0:
                number = -number

            inchmm = 25.4 #how many mms in inch

            if inch:
                number = number/2000
                if self.options['unit'] == 'mm':
                    number *= inchmm
                    inch = 0
            else:
                number = number/100
                if self.options['unit'] == 'inch':
                    number = round(number/inchmm,4)
                    inch = 1

            units = "in" if inch else "mm"

            measurement = (str(number)+units)
            #print(measurement)

            if ((self.options['changes'] == 'no') or (self.last_measurement != measurement)):
                self.put(self.ss_cmd, self.es_cmd, self.out_ann, [0, [measurement, str(number)]])
                self.last_measurement = measurement

            #Prepare for next packet
            self.reset()
