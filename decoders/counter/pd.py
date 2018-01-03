##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2018 Stefan Brüns <stefan.bruens@rwth-aachen.de>
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

class Decoder(srd.Decoder):
    api_version = 3
    id = 'counter'
    name = 'Counter'
    longname = 'Edge counter'
    desc = 'Count number of edges.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    optional_channels = (
        {'id': 'reset', 'name': 'Reset', 'desc': 'Reset line'},
    )
    annotations = (
        ('edge_count', 'Edge count'),
        ('word_count', 'Word count'),
        ('word_reset', 'Word reset'),
    )
    annotation_rows = (
        ('edge_counts', 'Edges', (0,)),
        ('word_counts', 'Words', (1,)),
        ('word_resets', 'Word resets', (2,)),
    )
    options = (
        {'id': 'data_edge', 'desc': 'Edges to count (data)', 'default': 'any',
            'values': ('any', 'rising', 'falling')},
        {'id': 'divider', 'desc': 'Count divider (word width)', 'default': 0},
        {'id': 'reset_edge', 'desc': 'Edge which clears counters (reset)',
            'default': 'falling', 'values': ('rising', 'falling')},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.edge_count = 0
        self.word_count = 0
        self.have_reset = None

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.edge = self.options['data_edge']
        self.divider = self.options['divider']
        if self.divider < 0:
            self.divider = 0

    def putc(self, cls, annlist):
        self.put(self.samplenum, self.samplenum, self.out_ann, [cls, annlist])

    def decode(self):
        condition = [{'rising':  {0: 'r'},
                      'falling': {0: 'f'},
                      'any':     {0: 'e'},}[self.edge]]

        if self.has_channel(1):
            self.have_reset = True
            condition.append({1: self.options['reset_edge'][0]})

        while True:
            self.wait(condition)
            if self.have_reset and self.matched[1]:
                self.edge_count = 0
                self.word_count = 0
                self.putc(2, ['Word reset', 'Reset', 'Rst', 'R'])
                continue

            self.edge_count += 1

            self.putc(0, [str(self.edge_count)])
            if self.divider > 0 and (self.edge_count % self.divider) == 0:
                self.word_count += 1
                self.putc(1, [str(self.word_count)])
