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

from .symbols import *

class Decoder(srd.Decoder):
    api_version = 3
    id       = '4b5b'
    name     = '4B5B'
    longname = '4B5B Line Code'
    desc     = 'Maps 4 bits of data to 5 bits for transmission.'
    license  = 'gplv2+'
    inputs   = ['nrzi']
    outputs  = ['4b5b']
    tags     = ['Encoding']
    options = (
        {
            'id':      'bit_offset',
            'desc':    'Bit offset',
            'default': '0',
            'values':  ('0', '1', '2', '3', '4')
        },
    )
    annotations = (
        ('symbol_data', 'Data symbol'),
        ('symbol_ctrl', 'Control symbol'),
        ('bits', 'Decoded bits'),
        ('bytes', 'Decoded bytes'),
    )
    annotation_rows = (
        ('symbol', 'Symbols', (0,1)),
        ('bits', 'Bits', (2,)),
        ('bytes', 'Bytes', (3,)),
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
        self.ss_block = None
        self.es_block = None
        self.bit_offset = None
        
        self.symbol_start = None
        self.symbol = 0
        self.bits = 0
        
        self.data_start = None
        self.last_nibble = None

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.bit_offset = int(self.options['bit_offset'])

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
    def decode(self, startsample, endsample, data):
        # Offset symbol starting point
        if self.bit_offset > 0:
            self.bit_offset -= 1
            return

        # If first bit of symbol, set symbol start sample
        if self.bits == 0: self.symbol_start = startsample
        
        # If first nibble of data byte, set data byte start sample
        if self.bits == 0 and self.last_nibble == None: self.data_start = startsample

        # Shift bit into symbol
        self.symbol = (self.symbol << 1) | data
        self.bits += 1

        # If all bits for symbol received
        if self.bits == 5:
            # Set symbol annotation start/end
            self.ss_block = self.symbol_start
            self.es_block = endsample

            # Control symbol
            if self.symbol in sym_ctrl:
                # Add control symbol annotation
                self.putx([1, sym_ctrl[self.symbol]])

                # Push control symbol to stacked decoders
                self.putp({"data": None, "control": sym_ctrl[self.symbol][1]})
            
            # Data symbol
            elif self.symbol in sym_data:
                # Add data symbol annotations
                self.putx([0, ["{:05b}".format(self.symbol)]])
                self.putx([2, ["{:04b}".format(sym_data[self.symbol])]])

                # Second nibble of data byte
                if self.last_nibble != None:
                    # Shift nibble into data byte
                    data_byte = (sym_data[self.symbol] << 4) | self.last_nibble

                    # Add data byte annotation
                    self.ss_block = self.data_start
                    self.es_block = endsample
                    self.putx([3, ["0x{:02X}".format(data_byte)]])

                    # Push byte to stacked decoders
                    self.putp({"data": data_byte, "control": None})

                    # Reset data byte value
                    self.data_start = endsample
                    self.last_nibble = None
                
                # First nibble of data byte
                else:
                    self.last_nibble = sym_data[self.symbol]

            # Reset symbol value
            self.symbol_start = endsample
            self.symbol = 0
            self.bits = 0
