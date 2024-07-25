##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Michael Stapelberg
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
    id = 'scs'
    name = 'SCS'
    longname = 'Sistema Cablaggio Semplificato (Simplified Cable Solution)'
    desc = 'fieldbus network protocol for home automation, used by bTicino and Legrand'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = []
    tags = ['Embedded/industrial', 'Networking']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('scs', 'SCS'),
    )
    options = ()

    def __init__(self):
        self.reset()

    def reset(self):
        self.telegram_idx = 0

    # called before beginning of decoding
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    # called to start decoding
    def decode(self, startsample, endsample, data):
        ptype, rxtx, pdata = data
        if ptype != 'DATA':
            return
        val = pdata[0]
        if self.telegram_idx == 0 and val == 0xa8:
            self.put(startsample, endsample, self.out_ann, [0, ['init']])
        elif self.telegram_idx == 1:
            self.crc = val
            self.put(startsample, endsample, self.out_ann, [0, ['addr']])
        elif self.telegram_idx == 2:
            self.crc ^= val
            self.put(startsample, endsample, self.out_ann, [0, ['??']])
        elif self.telegram_idx == 3:
            self.crc ^= val
            self.put(startsample, endsample, self.out_ann, [0, ['request']])
        elif self.telegram_idx == 4:
            self.crc ^= val
            self.put(startsample, endsample, self.out_ann, [0, ['??']])
        elif self.telegram_idx == 5:
            crc = 'good' if self.crc == val else 'bad'
            self.put(startsample, endsample, self.out_ann, [0, ['%s crc' % crc]])
        elif self.telegram_idx == 6:
            self.put(startsample, endsample, self.out_ann, [0, ['term']])
            self.telegram_idx = -1

        self.telegram_idx += 1
