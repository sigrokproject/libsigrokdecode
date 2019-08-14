##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Comlab AG
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
import math

class Decoder(srd.Decoder):
    api_version = 3
    id = 'vector_unsigned'
    name = 'vector unsigned slice'
    longname = 'vector unsigned slice'
    desc = 'Decoding a slice of a vector to an unsigned integer.'
    license = 'gplv2+'
    inputs = ['vector_slice']
    outputs = []
    tags = ['VectorSlicer']
    options = (
        {'id': 'format', 'desc': 'select format', 'default': 'decimal',
            'values': ('dec', 'hex', 'oct', 'bin')},
    )
    annotations = (
        ('value', 'value'),
    )
    annotation_rows = (
        ('value', 'value', (0,)),
    )

    def reset(self):
        pass

    def __init__(self):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

        fmt_opt = self.options['format']
        self.fmt_str = "{0:d}"
        if fmt_opt == 'hex':
            self.fmt_str = "0x{{0:0{}x}}"
        elif fmt_opt == 'oct':
            self.fmt_str = "0o{{0:0{}o}}"
        elif fmt_opt == 'bin':
            self.fmt_str = "b{{0:0{}b}}"

        self.fmt_opt = fmt_opt
        self.first = True

    def decode(self, ss, es, data):
        d, length = data
        if self.first:
            if self.fmt_opt == 'bin':
                self.fmt_str = self.fmt_str.format(length)
            elif self.fmt_opt == 'hex':
                l = math.floor((length + 3)/4)
                self.fmt_str = self.fmt_str.format(l)
            elif self.fmt_opt == 'oct':
                l = math.floor((length + 2)/3)
                self.fmt_str = self.fmt_str.format(l)
        self.first = False
        self.put(ss, es, self.out_ann, [0, [self.fmt_str.format(d)]])
