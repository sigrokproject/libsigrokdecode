##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021 Lars Rademacher <rademacher.lars@gmx.de>
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
from collections import deque

class SamplerateError(Exception):
    pass
        
class Pin:
    (DATA_START,DATA_END) = range(2)

class Ann:
    (TIME,AVG,) = range(2)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'edgediff'
    name = 'EdgeDiff'
    longname = 'Timing difference between edges of two signals'
    desc = 'Calculate time between edges of two signals.'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = []
    tags = ['Clock/timing', 'Util']
    channels = (
        {'id': 'dataStart', 'name': 'Start', 'desc': 'Channel which contains the start edge'},
        {'id': 'dataEnd', 'name': 'End', 'desc': 'Channel which contains the end edge'},
    )
    annotations = (
        ('time', 'Time'),
        ('average', 'Average'),
    )
    annotation_rows = (
        ('times', 'Times', (Ann.TIME,)),
        ('averages', 'Averages', (Ann.AVG,)),
    )
    options = (
        { 'id': 'edgeTypeStart', 'desc': 'Which edges are considered on Start',
          'default': 'any', 'values': ('any', 'rising', 'falling') },
        { 'id': 'edgeTypeEnd', 'desc': 'Which edges are considered on End',
          'default': 'any', 'values': ('any', 'rising', 'falling') },
        { 'id': 'avg_period', 'desc': 'Averaging period (<=1: Off)', 'default': 100 },
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        edgeTypeStart = self.options['edgeTypeStart']
        edgeTypeEnd = self.options['edgeTypeEnd']
        avg_period = self.options['avg_period']
        last_n = deque()
        while True:
            self.__waitForEdge(Pin.DATA_START, edgeTypeStart)
            
            ss = self.samplenum
            
            self.__waitForEdge(Pin.DATA_END, edgeTypeEnd)
            
            es = self.samplenum
            sa = es - ss
            t = sa / self.samplerate
            
            cls, txt = Ann.TIME, [self.__normalize_time(t)]
            
            if txt:
                self.put(ss, es, self.out_ann, [cls, txt])
            
            if avg_period > 1:
                if t > 0:
                    last_n.append(t)
                if len(last_n) > avg_period:
                    last_n.popleft()
                average = sum(last_n) / len(last_n)
                cls, txt = Ann.AVG, self.__normalize_time(average)
                self.put(ss, es, self.out_ann, [cls, [txt]])

    def __waitForEdge(self,pin,edgetype):
        if edgetype == 'rising':
            self.wait({pin: 'r'})
        elif edgetype == 'falling':
            self.wait({pin: 'f'})
        else:
            self.wait({pin: 'e'})

    def __normalize_time(self,t):
        if abs(t) >= 1.0:
            return '%.3f s  (%.3f Hz)' % (t, (1/t))
        elif abs(t) >= 0.001:
            if 1/t/1000 < 1:
                return '%.3f ms (%.3f Hz)' % (t * 1000.0, (1/t))
            else:
                return '%.3f ms (%.3f kHz)' % (t * 1000.0, (1/t)/1000)
        elif abs(t) >= 0.000001:
            if 1/t/1000/1000 < 1:
                return '%.3f μs (%.3f kHz)' % (t * 1000.0 * 1000.0, (1/t)/1000)
            else:
                return '%.3f μs (%.3f MHz)' % (t * 1000.0 * 1000.0, (1/t)/1000/1000)
        elif abs(t) >= 0.000000001:
            if 1/t/1000/1000/1000:
                return '%.3f ns (%.3f MHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000)
            else:
                return '%.3f ns (%.3f GHz)' % (t * 1000.0 * 1000.0 * 1000.0, (1/t)/1000/1000/1000)
        else:
            return '%f' % t