##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 MaxWolf b8e06912cff61c7fc1f5df01ba2f43de51b04ce33fd4d351ce86a40c0cbf9abb
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


##
## Opentherm protocol decoder based on "The OpenTherm(TM) Communications Protocol. A Point-to-Point Communications System for HVAC Controls. Protocol Specification v2.2"
## OpenTherm+ Manchester/Bi-phase-L coding
##

import sigrokdecode as srd
from .lists import *
from .otdecoder import *

class SamplerateError(Exception):
    pass


class AnnIdx: # index to Decoder::annotations
    ann_bit = 0
    ann_startbit = 1
    ann_stopbit = 2
    ann_paritybit = 3
    ann_msgtype = 4
    ann_spare = 5
    ann_dataid = 6
    ann_datavalue = 7
    ann_master2slave = 8
    ann_slave2master = 9
    ann_frame = 10
    ann_timing = 11
    ann_warning = 12
    ann_descr = 13


class Decoder(srd.Decoder):
    api_version = 3
    id = 'opentherm'
    name = 'OpenTherm'
    longname = 'OpenTherm'
    desc = 'OpenTherm protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['OT']
    channels = (
        {'id': 'ot', 'name': 'OT', 'desc': 'OpenTherm line'},
    )

    # configuration options
    options = (
        {'id': 'polarity', 'desc': 'Polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high')},
        # various timings according to https://ihormelnyk.com/Content/Pages/opentherm_library/Opentherm%20Protocol%20v2-2.pdf
        {'id': 'bitlen', 'desc': 'Single bit period (us)', 'default': 1000 },                              # duration of a bit
        {'id': 'jitter_m', 'desc': 'Edge jitter minus (us)', 'default': 100 },                             # maximum allowed time advance of bit transition
        {'id': 'jitter_p', 'desc': 'Edge jitter plus (us)', 'default': 150 },                              # maximum allowed time latency of bit transition
        {'id': 'm2s_silence_min', 'desc': 'Master to Slave min silence (us)', 'default': 20000 },      # min period between master request and slave response
        {'id': 'm2s_silence_max', 'desc': 'Master to Slave max silence (us)', 'default': 800000 },     # max period between master request and slave response
        {'id': 's2m_silence_min', 'desc': 'Slave to Master min silence (us)', 'default': 100000 },     # min period between slave response and next master request
        {'id': 'm2m_act_max', 'desc': 'Master req to req max period (us)', 'default': 1150000 },       # max period between master requests
        {'id': 'ignore_glitches', 'desc': 'Ignore glitches up to (us)', 'default': 0 },       # ignore glitches/spikes of up to given us len
    )

    # predefined data annotation types (see also class AnnIdx)
    annotations = (
        ('bit', 'Bit'),                     # 0
        ('startbit', 'Startbit'),           # 1
        ('stopbit', 'Stopbit'),             # 2
        ('paritybit', 'Paritybit'),         # 3
        ('msgtype', 'MSG-TYPE'),            # 4
        ('spare', 'Spare'),                 # 5
        ('dataid', 'DATA-ID'),              # 6
        ('datavalue', 'DATA-VALUE'),		# 7
        ('m2s', 'MasterToSlave'),			# 8
        ('s2m', 'SlaveToMaster'),			# 9
        ('frame', 'OpenThermFrame'),		# 10
        ('timing', 'Timing error'),        	# 11
        ('warning', 'Warning'),             # 12
        ('otx', 'OpenThermExchange'),       # 13
    )

    # grouping of annotation types by annotation rows (streams) visible within pulseview
    annotation_rows = (
        ('bits', 'Bits', (0,)),
        ('fields', 'Fields', (1, 2, 3, 4, 5, 6, 7)),
        ('direction', 'Direction', (8, 9)),
        ('frame', 'Frame', (10,)),
        ('otx', 'Description', (13,)),
        ('warnings', 'Warnings', (12,)),
        ('timing', 'Timing errors', (11,)),
    )

    def __init__(self):
        self.reset()
        self.ot_decoder = OTDecoder()
		
    def reset_decoder_state(self):
        self.edges = []          # list of samples for every edge in the packed being decoded
        self.bits = []           # list of tuples for every decoded bit in a packet: [sample given bit is started from, bit value]
        self.ss_es_bits = []     # list of tuples for every decoded bit in a packet: [start sample, end sample]
        self.last_frame_edge = None
        self.state = 'IDLE'      # initial 

    def reset(self):
        self.samplerate = None
        self.reset_decoder_state()
        self.silence = None
        self.glitchlen = 0
        self.prev_samplenum = None
        self.prev_lvl = None

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)


    # convert number of samples at current samplerate into time in us 
    def s2t(self, samples):
        return int((1000000.0 * samples) / self.samplerate)
        
    # convert time in us into number of samples at current samplerate
    def t2s(self, time):
        return int((self.samplerate * time) / 1000000.0)

    def setup_calc(self):
        for o in self.options:
            pass
        # halfbit - (duration of one bit)/2 in a number of samples
        self.halfbit = self.t2s(self.options['bitlen'] / 2.0)
        # short period
        self.s_range = range(self.halfbit - self.t2s(self.options['jitter_m']), self.halfbit + self.t2s(self.options['jitter_p']) + 1)
        # long period
        self.l_range = range(self.halfbit*2 - self.t2s(self.options['jitter_m']), self.halfbit*2 + self.t2s(self.options['jitter_p']) + 1)
        # min silence
        s = min(self.options['m2s_silence_min'], self.options['s2m_silence_min'])
        self.silence = self.t2s(s)
        self.glitchlen = self.t2s(self.options['ignore_glitches'])

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value # in Hz

    def putb(self, bit1, bit2, data):
        ss, es = self.ss_es_bits[bit1][0], self.ss_es_bits[bit2][1]
        self.put(ss, es, self.out_ann, data)

    def handle_bits(self):
        a, c, d, v, p, b = 0, 0, 0, 0, 0, self.bits
        wrn = ""

        if len(self.bits) < 1:
            # nothing to annotate
            return            
        
        # Individual raw bits.
        for i in range(len(self.bits)):
            ss = self.bits[i][0]
            es = self.bits[i + 1][0] if i < len(self.bits)-1 else self.bits[i][0] + self.halfbit*2
            self.ss_es_bits.append([ss, es])
            self.putb(i, i, [AnnIdx.ann_bit, ['%d' % self.bits[i][1]]])

        # Bitfields
        #
        # Bits[0:0]: Start bit
        s = ['Startbit: %d' % b[0][1], 'STRTB: %d' % b[0][1], 'STRB', 'S', 'S']
        self.putb(0, 0, [AnnIdx.ann_startbit, s])

        if len(self.bits) < 2:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame", "Frame error", "F"]])
            return            

        # Bits[1:1]: Parity bit
        s = ['Paritybit: %d' % b[1][1], 'PB: %d' % b[1][1], 'PB', 'P', 'P']
        self.putb(1, 1, [AnnIdx.ann_paritybit, s])
        if len(self.bits) == 34:
            for i in range(32):
                p ^= b[i + 1][1]
            if p == 1:
                wrn = wrn + ("; " if len(wrn) > 0 else "") + "ParityError"

        if len(self.bits) < 5:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame", "Frame error", "F"]])
            return

        # Bits[2:4]: MSG-TYPE (MSB-first)
        for i in range(3):
            a |= (b[2 + i][1] << (2 - i))
        x = msg_type.get(a, ['UNK','Unknown', 'Unk'])
        s = ['MSG-TYPE: %s (%d)' % (x[1], a), '%s (%d)' % (x[2], a), '%s' % x[2], '%s' % x[2], '%s' % x[2]]
        self.putb(2, 4, [AnnIdx.ann_msgtype, s])
        if (a == 2) | (a == 3) | (a == 6) | (a == 7):
        	wrn = wrn + ("; " if len(wrn) > 0 else "") + "MSG_TYPE==%s"%x[1]
        if x[0] == 'M2S':
             self.putb(0, len(self.bits)-1, [AnnIdx.ann_master2slave, ['MasterToSlave', x[0]]])
        elif x[0] == 'S2M':
             self.putb(0, len(self.bits)-1, [AnnIdx.ann_slave2master, ['SlaveToMaster', x[0]]])

        if len(self.bits) < 9:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame %s(%d)" % (x[1], a), "Frame error", "FE"]])
            return

        # Bits[5:8]: spare
        for i in range(4):
            c |= (b[5 + i][1] << (3 - i))
        s = ['SPARE: %d' % (c), 'SP: %d' % c, 'SP', 'SP', 'SP']
        self.putb(5, 8, [AnnIdx.ann_spare, s])

        if len(self.bits) < 17:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame %s(%d)" % (x[1], a), "Frame error", "FE"]])
            return
        
        # Bits[9:16]: DATA-ID
        for i in range(8):
            d |= (b[9 + i][1] << (7 - i))
        s = ['DATA-ID: %d / 0x%x' % (d, d), 'D-ID: %d' % d, 'ID', 'ID', 'ID']
        self.putb(9, 16, [AnnIdx.ann_dataid, s])

        if len(self.bits) < 33:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame %s(%d) %d/0x%x" % (x[1], a, d, d), "Frame error", "FE"]])
            return

        # Bits[17:32]: DATA-VALUE
        for i in range(16):
            v |= (b[17 + i][1] << (15 - i))
        s = ['DATA-VALUE: %d / 0x%x' % (v, v), 'D-VAL: %d' % v, 'V', 'V', 'V']
        self.putb(17, 32, [AnnIdx.ann_datavalue, s])

        if len(self.bits) < 34:
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_warning, ["Incomplete packet at %d-bit" % len(self.bits), "Pkt error", "I"]])
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Invalid frame %s(%d) %d/0x%x %d/0x%x" % (x[1], a, d, d, v, v), "Frame error", "FE"]])
            return

        # Bits[33:33]: Stop bit
        s = ['Stopbit: %d' % b[33][1], 'STPB: %d' % b[33][1], 'STPB', 'S', 'S']
        self.putb(33, 33, [AnnIdx.ann_stopbit, s])
        if b[33][1] != 1:
            wrn = wrn + ("; " if len(wrn) > 0 else "") + "Invalid stop bit"

        if len(wrn) > 0:
            self.putb(0, 33, [AnnIdx.ann_warning, [wrn, "!"]])

        self.putb(0, len(self.bits) - 1, [AnnIdx.ann_frame, ["Frame %s %s(%d) %d/0x%x %d/0x%x" % (x[0], x[1], a, d, d, v, v), "Frame %s" % x[1], "F"]])

        if a == 0: # READ-DATA
            s, c = self.ot_decoder.describe_param(d, "R", v, -1)
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_descr, ["Descr: " + s]])
        elif a == 1: # WRITE-DATA
            s, c = self.ot_decoder.describe_param(d, "W", v, -1)
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_descr, ["Descr: " + s]])
        elif a == 4: # READ-ACK
            s, c = self.ot_decoder.describe_param(d, "R", -1, v)
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_descr, ["Descr: " + s]])
        elif a == 1: # WRITE-ACK
            s, c = self.ot_decoder.describe_param(d, "W", -1, v)
            self.putb(0, len(self.bits) - 1, [AnnIdx.ann_descr, ["Descr: " + s]])


    def edge_type(self, ss, es):
        # Categorize according to distance from last edge (short/long).
        distance = es - ss
        if distance in self.l_range:
            ret = 'l'
        elif distance in self.s_range:
            ret = 's'
        else:
            ret = 'e' # Error, invalid edge distance.
        return ret

    def handle_timing_error(self, type, tss, tes):
        self.put(tss, tes, self.out_ann, [AnnIdx.ann_timing, ["Timing error (%d us)" % self.s2t(tes - tss), "Timing", "T"]])
        self.reset_decoder_state()
        self.last_frame_edge = tes
        

    def decode(self):
        if self.samplerate is None:
            raise SamplerateError('Cannot decode without samplerate.')

        bit = None

        while True:
            if self.silence is None:
                self.setup_calc() # it was not properly called in time

            (self.lvl,) = self.wait({0: 'e'}) # either raising or falling edge

            pass

            if self.prev_samplenum is None:
                self.prev_samplenum = self.samplenum
                self.prev_lvl = self.lvl
                continue

            if self.glitchlen != 0:
                if (self.samplenum - self.prev_samplenum <= self.glitchlen):
                    self.put(self.prev_samplenum, self.samplenum, self.out_ann, [AnnIdx.ann_warning, ["Glitch (%d us)" % self.s2t(self.samplenum - self.prev_samplenum), "Glitch", "G"]])
                    self.prev_samplenum = None
                    self.prev_lvl = self.lvl
                    continue

            self.c_samplenum = self.prev_samplenum
            self.c_lvl = self.prev_lvl
            self.prev_samplenum = self.samplenum
            self.prev_lvl = self.lvl

            if len(self.edges) > 0:
                pass
            else:
                pass

            self.edges.append(self.c_samplenum)
            # from now self.edges[-1] == self.c_samplenum and previous edge (if exists) is self.edges[-2]

            # FSM

            if self.state == 'IDLE':
                if self.last_frame_edge is not None and (self.c_samplenum - self.last_frame_edge) < self.halfbit * 4:
                    self.put(self.last_frame_edge, self.c_samplenum, self.out_ann, [AnnIdx.ann_warning, ["Sync error: silence too short", "Sync err", "S"]])
                    self.last_frame_edge= self.c_samplenum
                    continue
                    
                if self.options['polarity'] == 'active-low':
                    if self.c_lvl == 1: # it is a rising edge -> possible active-low start bit 
                        self.state = 'SYNC'
                else:
                    if self.c_lvl == 0: # there was a rising edge -> possible active-high start bit 
                        self.state = 'SYNC'
                continue

            edge = self.edge_type(self.edges[-2], self.edges[-1])


            if self.state == 'SYNC':
                if edge == 's':
                    self.state = 'MID1'
                    bit = 1
                    bitpos = self.edges[-2]
                else:
                    self.put(self.edges[-2], self.edges[-1], self.out_ann, [AnnIdx.ann_warning, ["Sync error: start bit len error", "Sync err", "S"]])
                    self.handle_timing_error("SYNC/" + edge, self.edges[-2], self.edges[-1])
                    bit = None
            elif self.state == 'MID1':
                if edge == 's':
                    self.state = 'START1'
                    bit = None
                elif edge == 'l':
                    self.state = 'MID0'
                    bit = 0
                    bitpos = self.c_samplenum - self.halfbit
                else:
                    if self.edges[-1] - self.edges[-2] >= self.silence:
                        self.handle_bits()
                        self.handle_timing_error("MID1/" + edge + "/slnc+", self.edges[-2], self.edges[-1])
                        self.edges.append(self.c_samplenum)
                        self.state = 'SYNC'
                    else:
                        self.handle_bits()
                        self.handle_timing_error("MID1/" + edge + "/slnc-", self.edges[-2], self.edges[-1])
                    bit = None
            elif self.state == 'MID0':
                if edge == 's':
                    self.state = 'START0'
                    bit = None
                elif edge == 'l':
                    self.state = 'MID1'
                    bit = 1
                    bitpos = self.c_samplenum - self.halfbit
                else:
                    self.handle_bits()
                    self.handle_timing_error("MID0/" + edge, self.edges[-2], self.edges[-1])
                    bit = None
            elif self.state == 'START1':
                if edge == 's':
                    self.state = 'MID1'
                    bit = 1
                    bitpos = self.edges[-2]
                else:
                    self.handle_bits()
                    self.handle_timing_error("START1/" + edge, self.edges[-2], self.edges[-1])
                    bit = None
            elif self.state == 'START0':
                if edge == 's':
                    self.state = 'MID0'
                    bit = 0
                    bitpos = self.edges[-2]
                else:
                    if self.edges[-1] - self.edges[-2] >= self.silence:
                        self.handle_bits()
                        self.handle_timing_error("START0/" + edge + "/slnc+", self.edges[-2], self.edges[-1])
                        self.edges.append(self.c_samplenum)
                        self.state = 'SYNC'
                    else:
                        self.handle_bits()
                        self.handle_timing_error("START0/" + edge + "/slnc-", self.edges[-2], self.edges[-1])
                    bit = None


            if bit is not None:
                self.bits.append([bitpos, bit])

            if len(self.bits) == 34:
                self.handle_bits()
                self.reset_decoder_state()
                self.last_frame_edge = self.c_samplenum
