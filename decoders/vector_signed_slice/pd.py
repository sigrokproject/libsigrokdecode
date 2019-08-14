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

class Decoder(srd.Decoder):
    api_version = 3
    id = 'vector_signed'
    name = 'vector signed slice'
    longname = 'vector signed slice'
    desc = 'Decoding a slice of a vector to a signed integer.'
    license = 'gplv2+'
    inputs = ['vector_slice']
    outputs = []
    tags = ['VectorSlicer']
    options = ()
    annotations = (
        ('value', 'slice value'),
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

    def decode(self, ss, es, data):
        d, length = data
        sign = 1 << (length-1)
        if d & sign:
            d = d - 2*sign
        self.put(ss, es, self.out_ann, [0, ["{0:d}".format(d)]])

