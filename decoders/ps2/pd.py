##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Daniel Schulte <trilader@schroedingers-bit.net>
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

class Ann:
    BIT, START, WORD, PARITY_OK, PARITY_ERR, STOP, ACK, NACK, HREQ, HSTART, HWORD, HPARITY_OK, HPARITY_ERR, HSTOP = range(14)

class Bit:
    def __init__(self, val, ss, es):
        self.val = val
        self.ss = ss
        self.es = es

class Ps2Packet:
    def __init__(self, val, host=False, pok=False, ack=False):
        self.val  = val     #byte value
        self.host = host    #Host transmissions
        self.pok  = pok     #Parity ok
        self.ack  = ack     #Acknowlege ok for host transmission.


class Decoder(srd.Decoder):
    api_version = 3
    id = 'ps2'
    name = 'PS/2'
    longname = 'PS/2'
    desc = 'PS/2 packet interface used by PC keyboards and mice'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['ps2']
    tags = ['PC']
    channels = (
        {'id': 'clk', 'name': 'Clock', 'desc': 'Clock line'},
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('bit', 'Bit'),
        ('start-bit', 'Start bit'),
        ('word', 'Word'),
        ('parity-ok', 'Parity OK bit'),
        ('parity-err', 'Parity error bit'),
        ('stop-bit', 'Stop bit'),
        ('ack', 'Acknowledge'),
        ('nack', 'Not Acknowledge'),
        ('req', 'Host request to send'),
        ('start-bit', 'Start bit'),
        ('word', 'Word'),
        ('parity-ok', 'Parity OK bit'),
        ('parity-err', 'Parity error bit'),
        ('stop-bit', 'Stop bit'),
    )
    annotation_rows = (
        ('bits', 'Bits', (0,)),
        ('fields', 'Device', (1,2,3,4,5,6,7,)),
        ('host', 'Host', (8,9,10,11,12,13)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.bits = []
        self.bitcount = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

    def metadata(self,key,value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def get_bits(self, n, edge:'r', timeout=110e-6):
        max_period = int(timeout * self.samplerate) + 1
        _, dat = self.wait([{0:edge},{1:'l'}]) #No timeout for start bit
        if not self.matched[1]:
            return #No start bit
        elif not self.matched[0]:
            _, dat = self.wait({0:edge}) #Wait for clock edge
        self.bits.append(Bit(dat, self.samplenum, self.samplenum+max_period))
        for i in range(1,n):
            _, dat = self.wait([{0:edge},{'skip':max_period}])
            if not self.matched[0]:
                break #Timed out
            self.bits.append(Bit(dat, self.samplenum, self.samplenum+max_period))
            #Fix the ending period
            self.bits[i-1].es = self.samplenum
        if len(self.bits) == n:
            self.wait([{0:'r'},{'skip':max_period}])
            self.bits[-1].es = self.samplenum
        self.bitcount = len(self.bits)

    def putx(self, bit, ann):
        self.put(self.bits[bit].ss, self.bits[bit].es, self.out_ann, ann)

    def handle_bits(self, host=False):
        packet = None
        if self.bitcount > 8:
            # Annotate individual bits
            for b in self.bits:
                self.put(b.ss, b.es, self.out_ann, [Ann.BIT, [str(b.val)]])
            # Annotate start bit
            self.putx(0, [Ann.HSTART if host else Ann.START, ['Start bit', 'Start', 'S']])
            # Annotate the data word
            word = 0 
            for i in range(8):
                word |= (self.bits[i + 1].val << i)
            self.put(self.bits[1].ss, self.bits[8].es, self.out_ann, 
                [Ann.HWORD if host else Ann.WORD, 
                ['Data: %02x' % word, 'D: %02x' % word, '%02x' % word]])
            packet = Ps2Packet(val = word, host = host)

        # Calculate parity.
        if self.bitcount > 9:
            parity_ok = 0
            for bit in self.bits[1:10]:
                parity_ok ^= bit.val
            if bool(parity_ok):
                self.putx(9, [Ann.HPARITY_OK if host else Ann.PARITY_OK, ['Parity OK', 'Par OK', 'P']])
                packet.pok = True #Defaults to false in case packet was interrupted
            else:
                self.putx(9, [Ann.HPARITY_ERR if host else Ann.PARITY_ERR, ['Parity error', 'Par err', 'PE']])

        # Annotate stop bit
        if self.bitcount > 10:
            self.putx(10, [Ann.HSTOP if host  else Ann.STOP, ['Stop bit', 'Stop', 'St', 'T']])
        # Annotate ACK
        if host and self.bitcount > 11:
            if self.bits[11].val == 0:
                self.putx(11, [Ann.ACK, ['Acknowledge', 'Ack', 'A']])
            else:
                self.putx(11, [Ann.NACK, ['Not Acknowledge', 'Nack', 'N']])
            packet.ack = not bool(self.bits[11].val)

        if(packet):
            self.put(self.bits[0].ss, self.bits[-1].ss, self.out_py,packet)
        self.reset()


    def decode(self):
        if not self.samplerate:
            raise SamplerateError("Cannot decode without samplerate")
        max_period = int(100e-6 * self.samplerate)
        while True:
            # Falling edge of data indicates start condition
            # Clock held for 100us indicates host "request to send"
            self.wait([{1: 'f'},{0:'l'}])
            ss = self.samplenum
            host = self.matched[1]
            if host:
                # Make sure the clock is held low for at least 100 microseconds
                self.wait([{0:'h'},{'skip': max_period}])
                if self.matched[0]:
                    continue #Probably the trailing edge of a transfer
                # Host emits bits on rising clk edge
                self.get_bits(12, 'r')
                if self.bitcount > 0:
                    self.put(ss,self.bits[0].ss,self.out_ann, [Ann.HREQ,['Host RTS', 'HRTS', 'H']])
            else:
                # Client emits data on falling edge
                self.get_bits(11, 'f')
            self.handle_bits(host=host)
