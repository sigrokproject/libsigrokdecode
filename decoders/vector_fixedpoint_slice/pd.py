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
from decimal import *

class Decoder(srd.Decoder):
    api_version = 3
    id = 'vector_fixedpoint'
    name = 'vector fixedpoint slice'
    longname = 'vector fixedpoint slice'
    desc = 'Decoding a slice of a fixedpoint vector to an integer.'
    license = 'gplv2+'
    inputs = ['vector_slice']
    outputs = []
    tags = ['VectorSlicer']
    options = (
        {'id': 'pos', 'desc': 'point position', 'default': 3},
        {'id': 'Signum', 'desc': 'select signum', 'default': 'unsigned',
            'values': ('unsigned', 'signed')},
    )
    annotations = (
        ('fixedpoint-value', 'fixedpoint interpretation of vector'),
    )
    annotation_rows = (
        ('values', 'values', (0,)),
    )

    def reset(self):
        pass

    def __init__(self):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.fmt_str = "{{0:.0{}f}}"
        self.PosOfFixedPoint = self.options['pos']
        self.fmt_str = self.fmt_str.format(self.PosOfFixedPoint)
        self.signed = False
        if self.options['Signum'] == 'signed':
            self.signed = True

    def decode(self, ss, es, data):
        d, length = data
        integer = (d & (((2**(length-self.PosOfFixedPoint))-1)<<self.PosOfFixedPoint))>>self.PosOfFixedPoint
        fractional = (d & (2**(self.PosOfFixedPoint)-1))
        fractional_scaled = fractional/(2**self.PosOfFixedPoint)


        if  self.signed == True:
            sign_integer = 1 << (length-self.PosOfFixedPoint-1)
            sign_fractional = (1 << (self.PosOfFixedPoint))
            if integer & sign_integer:
                integer = integer - 2*sign_integer
            if fractional & sign_fractional:
                fractional_scaled = fractional_scaled - 2*sign_fractional

        decimal = integer + fractional_scaled


        self.put(ss, es, self.out_ann, [0, [self.fmt_str.format(decimal)]])
