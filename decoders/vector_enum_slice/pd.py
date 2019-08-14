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
import json

class Decoder(srd.Decoder):
    api_version = 3
    id = 'vector_enum'
    name = 'vector enum slice'
    longname = 'vector enum slice'
    desc = 'Decoding a slice of a vector to an enum.'
    license = 'gplv2+'
    inputs = ['vector_slice']
    outputs = []
    tags = ['VectorSlicer']
    options = (
        {'id': 'jsonfile', 'desc': '.json path', 'default': ''},
    )
    annotations = (
        ('a', 'a'),
        ('b', 'b'),
        ('c', 'c'),
        ('d', 'd'),
        ('e', 'e'),
        ('f', 'f'),
        ('u', 'u'), # used for undefined state
    )
    annotation_rows = (
        ('enum', 'enum', tuple([i for i in range(0, len(annotations))])),
    )

    def reset(self):
        pass

    def __init__(self):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.enums = {}
        with open(self.options['jsonfile'], 'r') as myfile:
            data = json.loads(myfile.read())
            ann = 0
            for key in data:
                self.enums[data[key]] = [key, ann]
                ann = (ann + 1) % (len(self.annotations) - 1)
        self.u_ann = len(self.annotations)-1

    def decode(self, ss, es, data):
        d, length = data
        if d in self.enums:
            item, ann = self.enums[d]
        else:
            item = "undefined"
            ann = self.u_ann
        self.put(ss, es, self.out_ann, [ann, [item]])
