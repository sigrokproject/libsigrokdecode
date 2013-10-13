##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2013 Uwe Hermann <uwe@hermann-uwe.de>
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
import os
import sys

class Decoder(srd.Decoder):
    api_version = 1
    id = 'i2s_dump'
    name = 'I2S dump'
    longname = 'I2S dump'
    desc = 'Output decoded I2S data to a file.'
    license = 'gplv2+'
    inputs = ['i2s']
    outputs = []
    probes = []
    optional_probes = []
    options = {
        'format': ['File format for the output data', 'wav'],
        'filename': ['File name for the output data', '-'],
    }
    annotations = []

    def __init__(self, **kwargs):
        self.wrote_header = False
        self.f = None

    def file_open(self, filename):
        if filename == 'none':
            return None
        elif filename == '-':
            return sys.stdout
        else:
            return open(filename, 'wb')

    def start(self, metadata):
        # A filename of 'none' is not allowed (has special meaning). A filename
        # of '-' means 'stdout'.
        self.f = self.file_open(self.options['filename'])

    def report(self):
        pass

    # TODO: Lots of hard-coded fields in here.
    def write_wav_header(self):
        # Chunk descriptor
        self.f.write(b'RIFF')
        self.f.write(b'\x24\x80\x00\x00') # Chunk size (2084)
        self.f.write(b'WAVE')

        # Fmt subchunk
        self.f.write(b'fmt ')
        self.f.write(b'\x10\x00\x00\x00') # Subchunk size (16 bytes)
        self.f.write(b'\x01\x00')         # Audio format (0x0001 == PCM)
        self.f.write(b'\x02\x00')         # Number of channels (2)
        self.f.write(b'\x44\xac\x00\x00') # Samplerate (44100)
        self.f.write(b'\x88\x58\x01\x00') # Byterate (88200) TODO
        self.f.write(b'\x04\x00')         # Blockalign (4)
        self.f.write(b'\x10\x00')         # Bits per sample (16)

        # Data subchunk
        self.f.write(b'data')
        self.f.write(b'\xff\xff\x00\x00') # Subchunk size (65535 bytes) TODO

        self.f.flush()

    def decode(self, ss, es, data):
        ptype, pdata = data

        if ptype != 'DATA':
            return

        channel, sample = pdata

        if self.wrote_header == False:
            self.write_wav_header()
            self.wrote_header = True

        # Output the next sample to 'filename'.
        # TODO: Data: first left channel, then right channel.
        if self.f != None:
            # TODO: This currently assumes U32 samples, and converts to S16.
            s = sample >> 16
            if s >= 0x8000:
                s -= 0x10000
            lo, hi = s & 0xff, (s >> 8) & 0xff
            self.f.write(bytes('%02x%02x' % (lo, hi), 'utf-8'))
            self.f.flush()

