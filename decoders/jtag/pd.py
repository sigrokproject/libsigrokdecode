##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
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

import sigrokdecode as srd

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>:
 - 'NEW STATE': <pdata> is the new state of the JTAG state machine.
   Valid values: 'TEST-LOGIC-RESET', 'RUN-TEST/IDLE', 'SELECT-DR-SCAN',
   'CAPTURE-DR', 'SHIFT-DR', 'EXIT1-DR', 'PAUSE-DR', 'EXIT2-DR', 'UPDATE-DR',
   'SELECT-IR-SCAN', 'CAPTURE-IR', 'SHIFT-IR', 'EXIT1-IR', 'PAUSE-IR',
   'EXIT2-IR', 'UPDATE-IR'.
 - 'IR TDI': Bitstring that was clocked into the IR register.
 - 'IR TDO': Bitstring that was clocked out of the IR register.
 - 'DR TDI': Bitstring that was clocked into the DR register.
 - 'DR TDO': Bitstring that was clocked out of the DR register.
 - ...

All bitstrings are a sequence of '1' and '0' characters. The right-most
character in the bitstring is the LSB. Example: '01110001' (1 is LSB).
'''

jtag_states = [
        # Intro "tree"
        'TEST-LOGIC-RESET', 'RUN-TEST/IDLE',
        # DR "tree"
        'SELECT-DR-SCAN', 'CAPTURE-DR', 'UPDATE-DR', 'PAUSE-DR',
        'SHIFT-DR', 'EXIT1-DR', 'EXIT2-DR',
        # IR "tree"
        'SELECT-IR-SCAN', 'CAPTURE-IR', 'UPDATE-IR', 'PAUSE-IR',
        'SHIFT-IR', 'EXIT1-IR', 'EXIT2-IR',
]

class Decoder(srd.Decoder):
    api_version = 2
    id = 'jtag'
    name = 'JTAG'
    longname = 'Joint Test Action Group (IEEE 1149.1)'
    desc = 'Protocol for testing, debugging, and flashing ICs.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['jtag']
    channels = (
        {'id': 'tdi',  'name': 'TDI',  'desc': 'Test data input'},
        {'id': 'tdo',  'name': 'TDO',  'desc': 'Test data output'},
        {'id': 'tck',  'name': 'TCK',  'desc': 'Test clock'},
        {'id': 'tms',  'name': 'TMS',  'desc': 'Test mode select'},
    )
    optional_channels = (
        {'id': 'trst', 'name': 'TRST#', 'desc': 'Test reset'},
        {'id': 'srst', 'name': 'SRST#', 'desc': 'System reset'},
        {'id': 'rtck', 'name': 'RTCK',  'desc': 'Return clock signal'},
    )
    annotations = tuple([tuple([s.lower(), s]) for s in jtag_states])

    def __init__(self, **kwargs):
        # self.state = 'TEST-LOGIC-RESET'
        self.state = 'RUN-TEST/IDLE'
        self.oldstate = None
        self.oldpins = (-1, -1, -1, -1)
        self.oldtck = -1
        self.bits_tdi = []
        self.bits_tdo = []
        self.samplenum = 0
        self.ss_item = self.es_item = None
        self.saved_item = None
        self.first = True

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, data):
        self.put(self.ss_item, self.es_item, self.out_ann, data)

    def putp(self, data):
        self.put(self.ss_item, self.es_item, self.out_python, data)

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

    def handle_rising_tck_edge(self, tdi, tdo, tck, tms):
        # Rising TCK edges always advance the state machine.
        self.advance_state_machine(tms)

        if self.first:
            # Save the start sample and item for later (no output yet).
            self.ss_item = self.samplenum
            self.first = False
            self.saved_item = self.state
        else:
            # Output the saved item (from the last CLK edge to the current).
            self.es_item = self.samplenum
            # Output the state we just switched to.
            self.putx([jtag_states.index(self.state), [self.state]])
            self.putp(['NEW STATE', self.state])
            self.ss_item = self.samplenum
            self.saved_item = self.state

        # If we went from SHIFT-IR to SHIFT-IR, or SHIFT-DR to SHIFT-DR,
        # collect the current TDI/TDO values (upon rising TCK edge).
        if self.state.startswith('SHIFT-') and self.oldstate == self.state:
            self.bits_tdi.insert(0, tdi)
            self.bits_tdo.insert(0, tdo)
            # TODO: ANN/PROTO output.
            # self.putx([0, ['TDI add: ' + str(tdi)]])
            # self.putp([0, ['TDO add: ' + str(tdo)]])

        # Output all TDI/TDO bits if we just switched from SHIFT-* to EXIT1-*.
        if self.oldstate.startswith('SHIFT-') and \
           self.state.startswith('EXIT1-'):

            t = self.state[-2:] + ' TDI'
            b = ''.join(map(str, self.bits_tdi))
            h = ' (0x%x' % int('0b' + b, 2) + ')'
            s = t + ': ' + b + h + ', ' + str(len(self.bits_tdi)) + ' bits'
            # self.putx([0, [s]])
            # self.putp([t, b])
            self.bits_tdi = []

            t = self.state[-2:] + ' TDO'
            b = ''.join(map(str, self.bits_tdo))
            h = ' (0x%x' % int('0b' + b, 2) + ')'
            s = t + ': ' + b + h + ', ' + str(len(self.bits_tdo)) + ' bits'
            # self.putx([0, [s]])
            # self.putp([t, b])
            self.bits_tdo = []

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # If none of the pins changed, there's nothing to do.
            if self.oldpins == pins:
                continue

            # Store current pin values for the next round.
            self.oldpins = pins

            # Get individual pin values into local variables.
            # Unused channels will have a value of > 1.
            (tdi, tdo, tck, tms, trst, srst, rtck) = pins

            # We only care about TCK edges (either rising or falling).
            if (self.oldtck == tck):
                continue

            # Store start/end sample for later usage.
            self.ss, self.es = ss, es

            # self.putx([0, ['tdi:%s, tdo:%s, tck:%s, tms:%s' \
            #                % (tdi, tdo, tck, tms)]])

            if (self.oldtck == 0 and tck == 1):
                self.handle_rising_tck_edge(tdi, tdo, tck, tms)

            self.oldtck = tck
