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

# JTAG protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'jtag'
    name = 'JTAG'
    longname = 'Joint Test Action Group'
    desc = 'TODO.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['jtag']
    probes = [
        {'id': 'tdi',  'name': 'TDI',  'desc': 'Test data input'},
        {'id': 'tdo',  'name': 'TDO',  'desc': 'Test data output'},
        {'id': 'tck',  'name': 'TCK',  'desc': 'Test clock'},
        {'id': 'tms',  'name': 'TMS',  'desc': 'Test mode select'},
        {'id': 'trst', 'name': 'TRST', 'desc': 'Test reset'},
    ]
    optional_probes = [] # TODO? SRST?
    options = {}
    annotations = [
        ['ASCII', 'TODO: description'],
    ]

    def __init__(self, **kwargs):
        self.state = 'TEST-LOGIC-RESET'
        self.oldpins = (-1, -1, -1, -1, -1)
        self.oldtck = -1
        self.bits_tdi = []
        self.bits_tdo = []

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'jtag')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'jtag')

    def report(self):
        pass

    def advance_state_machine(self, tms):
        # Intro "tree"
        if self.state == 'TEST-LOGIC-RESET':
            self.state = 'TEST-LOGIC-RESET' if (tms) else 'RUN-TEST/IDLE'
        elif self.state == 'RUN-TEST/IDLE':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'

        # DR "tree"
        elif self.state == 'SELECT-DR-SCAN':
            self.state = 'SELECT-IR-SCAN' if (tms) else 'CAPTURE-DR'
        elif self.state == 'CAPTURE-DR':
            self.state = 'EXIT1-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'SHIFT-DR':
            self.state = 'EXIT1-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'EXIT1-DR':
            self.state = 'UPDATE-DR' if (tms) else 'PAUSE-DR'
        elif self.state == 'PAUSE-DR':
            self.state = 'EXIT2-DR' if (tms) else 'PAUSE-DR'
        elif self.state == 'EXIT2-DR':
            self.state = 'UPDATE-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'UPDATE-DR':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'

        # IR "tree"
        elif self.state == 'SELECT-IR-SCAN':
            self.state = 'TEST-LOGIC-RESET' if (tms) else 'CAPTURE-IR'
        elif self.state == 'CAPTURE-IR':
            self.state = 'EXIT1-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'SHIFT-IR':
            self.state = 'EXIT1-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'EXIT1-IR':
            self.state = 'UPDATE-IR' if (tms) else 'PAUSE-IR'
        elif self.state == 'PAUSE-IR':
            self.state = 'EXIT2-IR' if (tms) else 'PAUSE-IR'
        elif self.state == 'EXIT2-IR':
            self.state = 'UPDATE-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'UPDATE-IR':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'

        else:
            raise Exception('Invalid state: %s' % self.state)

    def handle_rising_tck_edge(self, tdi, tdo, tck, tms, trst):
        # In SHIFT-DR/SHIFT-IR (on rising TCK edges) we collect TDI values.
        if self.state in ('SHIFT-DR', 'SHIFT-IR'):
            self.bits_tdi.append(tdi)

        # Output all TDI bits.
        elif self.state in ('EXIT1-DR', 'EXIT1-IR'):
            s = self.state[-2:] + ' TDI: ' + ''.join(map(str, self.bits_tdi))
            s += ', ' + str(len(self.bits_tdi)) + ' bits'
            self.put(self.ss, self.es, self.out_ann, [0, [s]])
            self.bits_tdi = []

        # Rising TCK edges always advance the state machine.
        self.advance_state_machine(tms)

        # Output the state we just switched to.
        self.put(self.ss, self.es, self.out_ann,
                 [0, ['New state: %s' % self.state]])

    def handle_falling_tck_edge(self, tdi, tdo, tck, tms, trst):
        # In SHIFT-DR/SHIFT-IR (on falling TCK edges) we collect TDO values.
        if self.state in ('SHIFT-DR', 'SHIFT-IR'):
            self.bits_tdo.append(tdo)

        # Output all TDO bits.
        if self.state in ('EXIT1-DR', 'EXIT1-IR'):
            s = self.state[-2:] + ' TDO: ' + ''.join(map(str, self.bits_tdo))
            s += ', ' + str(len(self.bits_tdo)) + ' bits'
            self.put(self.ss, self.es, self.out_ann, [0, [s]])
            self.bits_tdo = []

    def decode(self, ss, es, data):
        for (samplenum, pins) in data:

            # If none of the pins changed, there's nothing to do.
            if self.oldpins == pins:
                continue

            # Store current pin values for the next round.
            self.oldpins = pins

            # Get individual pin values into local variables.
            # TODO: Handle optional pins.
            (tdi, tdo, tck, tms, trst) = pins

            # We only care about TCK edges (either rising or falling).
            if (self.oldtck == tck):
                continue

            # Store start/end sample for later usage.
            self.ss, self.es = ss, es

            if (self.oldtck == 0 and tck == 1):
                self.handle_rising_tck_edge(tdi, tdo, tck, tms, trst)
            elif (self.oldtck == 1 and tck == 0):
                self.handle_falling_tck_edge(tdi, tdo, tck, tms, trst)

            self.oldtck = tck

