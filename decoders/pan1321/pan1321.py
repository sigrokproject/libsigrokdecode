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
# Panasonic PAN1321 Bluetooth module protocol decoder
#
# TODO
#

import sigrokdecode as srd

# Annotation feed formats
ANN_ASCII = 0

# UART 'data' packet type.
T_DATA = 1

# ...
RX = 0
TX = 1

class Decoder(srd.Decoder):
    api_version = 1
    id = 'pan1321'
    name = 'PAN1321'
    longname = 'Panasonic PAN1321'
    desc = 'TODO.'
    longdesc = 'TODO.'
    license = 'gplv2+'
    inputs = ['uart']
    outputs = ['pan1321']
    probes = []
    options = {}
    annotations = [
        ['ASCII', 'TODO: description'],
    ]

    def __init__(self, **kwargs):
        self.cmd = ['', '']

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'pan1321')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'pan1321')

    def report(self):
        pass

    def handle_host_command(self, ss, es, rxtx, s):
        if s.startswith('AT+JSEC'):
            pin = s[s.find('\r\n') - 4:len(s) - 2]
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Host set the Bluetooth PIN to ' + pin]])
        elif s.startswith('AT+JSLN'):
            name = s[s.find(',') + 1:-2]
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Host set the Bluetooth name to ' + name]])
        else:
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Host sent unsupported command']])
        self.cmd[rxtx] = ''

    def handle_device_reply(self, ss, es, rxtx, s):
        if s == 'ROK\r\n':
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Device initialized correctly']])
        elif s == 'OK\r\n':
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Device acknowledged last command']])
        elif s.startswith('ERR'):
            error = s[s.find('=') + 1:]
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Device sent error code ' + error]])
        else:
            self.put(ss, es, self.out_ann,
                     [ANN_ASCII, ['Device sent an unknown reply']])
        self.cmd[rxtx] = ''

    def decode(self, ss, es, data):
        ptype, rxtx, pdata = data

        # For now, ignore all UART packets except the actual data packets.
        if ptype != T_DATA:
            return

        # Append a new (ASCII) byte to the currently built/parsed command.
        self.cmd[rxtx] += chr(pdata)

        # Get packets/bytes until an \r\n sequence is found (end of command).
        if self.cmd[rxtx][-1:] != '\n':
            return

        # Handle host commands and device replies.
        if rxtx == RX:
            self.handle_device_reply(ss, es, rxtx, self.cmd[rxtx])
        elif rxtx == TX:
            self.handle_host_command(ss, es, rxtx, self.cmd[rxtx])
        else:
            pass # TODO: Error.

