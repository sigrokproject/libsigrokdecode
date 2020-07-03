##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Torsten Duwe <duwe@suse.de>
## Copyright (C) 2014 Sebastien Bourdelin <sebastien.bourdelin@savoirfairelinux.com>
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

def normalize_time(t):
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

class Pin:
    (DATA,) = range(1)

class Ann:
    (TIME, AVG, DELTA,) = range(3)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'timing'
    name = 'Timing'
    longname = 'Timing calculation with frequency and averaging'
    desc = 'Calculate time between edges.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Clock/timing', 'Util']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('time', 'Time'),
        ('average', 'Average'),
        ('delta', 'Delta'),
    )
    annotation_rows = (
        ('times', 'Times', (Ann.TIME,)),
        ('averages', 'Averages', (Ann.AVG,)),
        ('deltas', 'Deltas', (Ann.DELTA,)),
    )
    options = (
        { 'id': 'avg_period', 'desc': 'Averaging period', 'default': 100 },
        { 'id': 'edge', 'desc': 'Edges to check', 'default': 'any', 'values': ('any', 'rising', 'falling') },
        { 'id': 'delta', 'desc': 'Show delta from last', 'default': 'no', 'values': ('yes', 'no') },
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
        edge = self.options['edge']
        avg_period = self.options['avg_period']
        last_samplenum = None
        last_n = deque()
        last_t = None
        while True:
            if edge == 'rising':
                pin = self.wait({Pin.DATA: 'r'})
            elif edge == 'falling':
                pin = self.wait({Pin.DATA: 'f'})
            else:
                pin = self.wait({Pin.DATA: 'e'})

            if not last_samplenum:
                last_samplenum = self.samplenum
                continue
            samples = self.samplenum - last_samplenum
            t = samples / self.samplerate

            if t > 0:
                last_n.append(t)
            if len(last_n) > avg_period:
                last_n.popleft()

            self.put(last_samplenum, self.samplenum, self.out_ann,
                     [Ann.TIME, [normalize_time(t)]])
            if avg_period > 0:
                self.put(last_samplenum, self.samplenum, self.out_ann,
                         [Ann.AVG, [normalize_time(sum(last_n) / len(last_n))]])
            if last_t and self.options['delta'] == 'yes':
                self.put(last_samplenum, self.samplenum, self.out_ann,
                         [Ann.DELTA, [normalize_time(t - last_t)]])

            last_t = t
            last_samplenum = self.samplenum
