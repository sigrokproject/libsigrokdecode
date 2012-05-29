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
    longname = 'Joint Test Action Group (IEEE 1149.1)'
    desc = 'Protocol for testing, debugging, and flashing ICs.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['jtag']
    probes = [
        {'id': 'tdi',  'name': 'TDI',  'desc': 'Test data input'},
        {'id': 'tdo',  'name': 'TDO',  'desc': 'Test data output'},
        {'id': 'tck',  'name': 'TCK',  'desc': 'Test clock'},
        {'id': 'tms',  'name': 'TMS',  'desc': 'Test mode select'},
    ]
    optional_probes = [
        {'id': 'trst', 'name': 'TRST#', 'desc': 'Test reset'},
        {'id': 'srst', 'name': 'SRST#', 'desc': 'System reset'},
        {'id': 'rtck', 'name': 'RTCK',  'desc': 'Return clock signal'},
    ]
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
    ]

    def __init__(self, **kwargs):
        # self.state = 'TEST-LOGIC-RESET'
        self.state = 'RUN-TEST/IDLE'
        self.oldstate = None
        self.oldpins = (-1, -1, -1, -1)
        self.oldtck = -1
        self.bits_tdi = []
        self.bits_tdo = []

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'jtag')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'jtag')

    def report(self):
        pass

    def advance_state_machine(self, tms):
        self.oldstate = self.state

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

    def handle_rising_tck_edge(self, tdi, tdo, tck, tms):
        # Rising TCK edges always advance the state machine.
        self.advance_state_machine(tms)

        # Output the state we just switched to.
        self.put(self.ss, self.es, self.out_ann,
                 [0, ['New state: %s' % self.state]])
        self.put(self.ss, self.es, self.out_proto,
                 ['NEW STATE', self.state])

        # If we went from SHIFT-IR to SHIFT-IR, or SHIFT-DR to SHIFT-DR,
        # collect the current TDI/TDO values (upon rising TCK edge).
        if self.state.startswith('SHIFT-') and self.oldstate == self.state:
            self.bits_tdi.insert(0, tdi)
            self.bits_tdo.insert(0, tdo)
            # TODO: ANN/PROTO output.
            # self.put(self.ss, self.es, self.out_ann,
            #          [0, ['TDI add: ' + str(tdi)]])
            # self.put(self.ss, self.es, self.out_ann,
            #          [0, ['TDO add: ' + str(tdo)]])

        # Output all TDI/TDO bits if we just switched from SHIFT-* to EXIT1-*.
        if self.oldstate.startswith('SHIFT-') and \
           self.state.startswith('EXIT1-'):

            t = self.state[-2:] + ' TDI'
            b = ''.join(map(str, self.bits_tdi))
            h = ' (0x%x' % int('0b' + b, 2) + ')'
            s = t + ': ' + b + h + ', ' + str(len(self.bits_tdi)) + ' bits'
            self.put(self.ss, self.es, self.out_ann, [0, [s]])
            self.put(self.ss, self.es, self.out_proto, [t, b])
            self.bits_tdi = []

            t = self.state[-2:] + ' TDO'
            b = ''.join(map(str, self.bits_tdo))
            h = ' (0x%x' % int('0b' + b, 2) + ')'
            s = t + ': ' + b + h + ', ' + str(len(self.bits_tdo)) + ' bits'
            self.put(self.ss, self.es, self.out_ann, [0, [s]])
            self.put(self.ss, self.es, self.out_proto, [t, b])
            self.bits_tdo = []

    def decode(self, ss, es, data):
        for (samplenum, pins) in data:

            # If none of the pins changed, there's nothing to do.
            if self.oldpins == pins:
                continue

            # Store current pin values for the next round.
            self.oldpins = pins

            # Get individual pin values into local variables.
            # Unused probes will have a value of > 1.
            (tdi, tdo, tck, tms, trst, srst, rtck) = pins

            # We only care about TCK edges (either rising or falling).
            if (self.oldtck == tck):
                continue

            # Store start/end sample for later usage.
            self.ss, self.es = ss, es

            # self.put(self.ss, self.es, self.out_ann,
            #     [0, ['tdi:%s, tdo:%s, tck:%s, tms:%s' \
            #          % (tdi, tdo, tck, tms)]])

            if (self.oldtck == 0 and tck == 1):
                self.handle_rising_tck_edge(tdi, tdo, tck, tms)

            self.oldtck = tck

