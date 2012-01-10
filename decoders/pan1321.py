##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

#
# TODO
#

import sigrokdecode as srd

# Annotation feed formats
ANN_ASCII = 0

# UART 'data' packet type.
T_DATA = 1

class Decoder(srd.Decoder):
    id = 'pan1321'
    name = 'Panasonic PAN1321'
    longname = 'TODO.'
    desc = 'TODO.'
    longdesc = 'TODO.'
    author = 'Uwe Hermann'
    email = 'uwe@hermann-uwe.de'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = ['pan1321']
    # probes = [
    # ]
    options = {
    }
    annotations = [
        # ANN_ASCII
        ["ASCII", "TODO: description"],
    ]

    def __init__(self, **kwargs):
        # self.out_proto = None
        self.out_ann = None
        self.cmd = ''

    def start(self, metadata):
        # self.out_proto = self.add(srd.SRD_OUTPUT_PROTO, 'pan1321')
        self.out_ann = self.add(srd.SRD_OUTPUT_ANN, 'pan1321')

    def report(self):
        pass

    def decode(self, ss, es, data):
        ptype, pdata = data

        # For now, ignore all UART packets except the actual data packets.
        if ptype != T_DATA:
            return

        # Append new (ASCII) byte to the current command.
        self.cmd += chr(pdata)

        # Get packets/bytes until an \r\n sequence is found (end of command).
        if chr(pdata) != '\n':
            return

        s = self.cmd

        # FIXME: This is just a quick hack.
        if s.startswith('AT+JSEC'):
            pin = s[s.find('\r\n') - 4:len(s) - 2]
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Setting Bluetooth PIN to ' + pin]])
        elif s.startswith('AT+JSLN'):
            name = s[s.find(',') + 1:-2]
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Setting Bluetooth name to ' + name]])
        else:
            self.put(ss, es, self.out_ann, [ANN_ASCII, ['Unsupported command']])

        self.cmd = ''

