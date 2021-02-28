##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021
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

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'nrzi'
    name     = 'NRZ-I'
    longname = 'Non-return-to-zero Inverted'
    desc     = 'Bits encoded as presence or absence of a transition.'
    license  = 'gplv2+'
    inputs   = ['logic']
    outputs  = ['nrzi']
    tags     = ['Encoding']
    channels = (
        {
            'id':   'data',
            'name': 'Data',
            'desc': 'Data line'
        },
    )
    options = (
        {
            'id':      'preamble_len',
            'desc':    'Preamble Length',
            'default': '16',
            'values':  ('4', '8', '16', '32', '64')
        },
    )
    annotations = (
        ('preamble', 'Preamble'),
        ('bit', 'Decoded bits'),
    )
    annotation_rows = (
        ('bits', 'Bits', (0,1)),
    )
    binary = (
        ('data', 'Decoded data'),
    )

    # Initialise decoder
    def __init__(self):
        self.reset()

    # Reset decoder variables
    def reset(self):
        self.samplerate = None
        self.state = "SYNC"
        self.ss_block = None
        self.es_block = None
        self.preamble_len = None
        self.sync_cycles = []

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.preamble_len = int(self.options['preamble_len'])

    # Put annotation for PulseView
    def putx(self, data):
        self.put(self.ss_block, self.es_block, self.out_ann, data)

    # Put binary data for stacked decoders
    def putb(self, data):
        self.put(self.ss_block, self.es_block, self.out_binary, data)

    # Put Python object for stacked decoders
    def putp(self, data):
        self.put(self.ss_block, self.es_block, self.out_python, data)

    # Decode signal
    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        # Wait for first rising edge
        self.wait({0: 'r'})
        preamble_start = self.samplenum

        while True:
            # Calculate clock period using preamble
            if self.state == "SYNC":
                # Previous edge
                start = self.samplenum

                # Next edge
                self.wait({0: 'r'})
                end = self.samplenum

                # Add cycle length to list
                self.sync_cycles.append(end - start)

                # Calculate clock rate
                if len(self.sync_cycles) == self.preamble_len:
                    # Calculate average preamble cycle duration in samples
                    self.symbol_len = round((sum(self.sync_cycles) / len(self.sync_cycles)) / 2)

                    # Convert average cycle duration to frequency
                    self.clock_rate = self.samplerate / (self.symbol_len * 2)

                    # Preamble frequency string
                    frequency = "{} Hz".format(self.clock_rate)
                    if 1e3 <= self.clock_rate < 1e6:
                        frequency = "{} kHz".format(self.clock_rate / 1e3)
                    elif self.clock_rate >= 1e6:
                        frequency = "{} MHz".format(self.clock_rate / 1e6)

                    # Preamble annotation
                    self.ss_block = preamble_start
                    self.es_block = self.samplenum
                    self.putx([0, ["Preamble ({})".format(frequency)]])

                    # Skip to start of next symbol after preamble
                    self.wait({'skip': int(self.symbol_len / 2)})

                    # Set state machine to DECODE state
                    self.state = "DECODE"

            # Decode NRZ-I waveform into bits
            elif self.state == "DECODE":
                # Start of bit
                start_samp = self.samplenum

                # Skip forward to next edge or one symbol len
                self.wait([{0: 'e'}, {'skip': self.symbol_len}])

                # Check if transition was detected
                if self.matched == (True, False):
                    # Adjust symbol length to transition is at mid-point
                    edge_samp = self.samplenum - start_samp             # Edge position within symbol
                    offset = int(self.symbol_len / 2) - edge_samp       # Edge offset from mid-point of symbol
                    remaining = self.symbol_len - edge_samp - offset    # Number of samples remaining in symbol

                    # Skip forward to end of symbol
                    self.wait({'skip': remaining})

                    bit = 1
                else:
                    bit = 0

                # Add bit annotation
                self.ss_block = start_samp
                self.es_block = self.samplenum
                self.putx([1, [str(bit)]])

                # Push bit to stacked decoders
                self.putp(bit)
