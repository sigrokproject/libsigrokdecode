##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Gump Yang <gump.yang@gmail.com>
## Copyright (C) 2019 Rene Staffen
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

from . import irmp_library
import sigrokdecode as srd

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ir_irmp'
    name = 'IR IRMP'
    longname = 'IR IRMP'
    desc = 'IRMP infrared remote control multi protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['IR']
    channels = (
        {'id': 'ir', 'name': 'IR', 'desc': 'Data line'},
    )
    options = (
        {'id': 'polarity', 'desc': 'Polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high')},
    )
    annotations = (
        ('packet', 'Packet'),
    )
    annotation_rows = (
        ('packets', 'IR Packets', (0,)),
    )

    def putframe(self, data):
        nr = data['proto_nr']
        name = data['proto_name']
        addr = data['address']
        cmd = data['command']
        repeat = data['repeat']
        rep = ['repeat', 'rep', 'r'] if repeat else ['', '', '']
        ss = data['start'] * self.rate_factor
        es = data['end'] * self.rate_factor
        self.put(ss, es, self.out_ann, [0, [
            'Protocol: {nr} ({name}), Address 0x{addr:04x}, Command: 0x{cmd:04x} {rep[0]}'.format(**locals()),
            'P: {name} ({nr}), Addr: 0x{addr:x}, Cmd: 0x{cmd:x} {rep[1]}'.format(**locals()),
            'P: {nr} A: 0x{addr:x} C: 0x{cmd:x} {rep[1]}'.format(**locals()),
            'C:{cmd:x} A:{addr:x} {rep[2]}'.format(**locals()),
            'C:{cmd:x}'.format(**locals()),
        ]])

    def __init__(self):
        self.irmp = irmp_library.IrmpLibrary()
        self.lib_rate = self.irmp.get_sample_rate()
        self.reset()

    def reset(self):
        self.irmp.reset_state()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        if self.samplerate % self.lib_rate:
            raise SamplerateError('capture samplerate must be multiple of library samplerate ({})'.format(self.lib_rate))
        self.rate_factor = int(self.samplerate / self.lib_rate)

        self.active = 0 if self.options['polarity'] == 'active-low' else 1
        ir, = self.wait()
        while True:
            if self.active == 1:
                ir = 1 - ir
            if self.irmp.add_one_sample(ir):
                data = self.irmp.get_result_data()
                self.putframe(data)
            ir, = self.wait([{'skip': self.rate_factor}])
