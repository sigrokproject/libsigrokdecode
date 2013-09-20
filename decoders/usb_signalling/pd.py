##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
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

# USB signalling (low-speed and full-speed) protocol decoder

import sigrokdecode as srd

# Low-/full-speed symbols (used as states of our state machine, too).
# Note: Low-speed J and K are inverted compared to the full-speed J and K!
symbols = {
    'low-speed': {
        # (<dp>, <dm>): <symbol/state>
        (0, 0): 'SE0',
        (1, 0): 'K',
        (0, 1): 'J',
        (1, 1): 'SE1',
    },
    'full-speed': {
        # (<dp>, <dm>): <symbol/state>
        (0, 0): 'SE0',
        (1, 0): 'J',
        (0, 1): 'K',
        (1, 1): 'SE1',
    },
}

bitrates = {
    'low-speed': 1500000,   # 1.5Mb/s (+/- 1.5%)
    'full-speed': 12000000, # 12Mb/s (+/- 0.25%)
}

class Decoder(srd.Decoder):
    api_version = 1
    id = 'usb_signalling'
    name = 'USB signalling'
    longname = 'Universal Serial Bus (LS/FS) signalling'
    desc = 'USB (low-speed and full-speed) signalling protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['usb_signalling']
    probes = [
        {'id': 'dp', 'name': 'D+', 'desc': 'USB D+ signal'},
        {'id': 'dm', 'name': 'D-', 'desc': 'USB D- signal'},
    ]
    optional_probes = []
    options = {
        'signalling': ['Signalling', 'full-speed'],
    }
    annotations = [
        ['Text', 'Human-readable text']
    ]

    def __init__(self):
        self.sym = 'J' # The "idle" state is J.
        self.samplenum = 0
        self.scount = 0
        self.packet = ''
        self.syms = []
        self.bitrate = None
        self.bitwidth = None
        self.oldpins = None

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'usb_signalling')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'usb_signalling')
        self.bitrate = bitrates[self.options['signalling']]
        self.bitwidth = float(metadata['samplerate']) / float(self.bitrate)

    def report(self):
        pass

    def putp(self, data):
        self.put(self.samplenum, self.samplenum, self.out_proto, data)

    def putx(self, data):
        self.put(self.samplenum, self.samplenum, self.out_ann, data)

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # Note: self.samplenum is the absolute sample number, whereas
            # self.scount only counts the number of samples since the
            # last change in the D+/D- lines.
            self.scount += 1

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (dp, dm) = pins, pins

            sym = symbols[self.options['signalling']][dp, dm]

            self.putx([0, [sym]])
            self.putp(['SYM', sym])

            # Wait for a symbol change (i.e., change in D+/D- lines).
            if sym == self.sym:
                continue

            ## # Debug code:
            ## self.syms.append(sym + ' ')
            ## if len(self.syms) == 16:
            ##     self.putx([0, [''.join(self.syms)]])
            ##     self.syms = []
            # continue

            # How many bits since the last transition?
            if self.packet != '' or self.sym != 'J':
                bitcount = int((self.scount - 1) / self.bitwidth)
            else:
                bitcount = 0

            if self.sym == 'SE0':
                if bitcount == 1:
                    # End-Of-Packet (EOP)
                    # self.putx([0, [packet_decode(self.packet), self.packet]])
                    if self.packet != '': # FIXME?
                        self.putx([0, ['PACKET: %s' % self.packet]])
                        self.putp(['PACKET', self.packet])
                else:
                    # Longer than EOP, assume reset.
                    self.putx([0, ['RESET']])
                    self.putp(['RESET', None])
                # self.putx([0, [self.packet]])
                self.scount = 0
                self.sym = sym
                self.packet = ''
                continue

            # Add bits to the packet string.
            self.packet += '1' * bitcount

            # Handle bit stuffing.
            if bitcount < 6 and sym != 'SE0':
                self.packet += '0'
            elif bitcount > 6:
                self.putx([0, ['BIT STUFF ERROR']])
                self.putp(['BIT STUFF ERROR', None])

            self.scount = 0
            self.sym = sym

