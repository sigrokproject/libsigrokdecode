##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012 Joel Holdsworth <joel@airwebreathe.org.uk>
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
import struct

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>, <pdata>:
 - 'DATA', [<channel>, <value>]

<channel>: 'L' or 'R'
<value>: integer
'''

class Decoder(srd.Decoder):
    api_version = 3
    id = 'i2s'
    name = 'I²S'
    longname = 'Integrated Interchip Sound'
    desc = 'Serial bus for connecting digital audio devices.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2s']
    tags = ['Audio', 'PC']
    channels = (
        {'id': 'sck', 'name': 'SCK', 'desc': 'Bit clock line'},
        {'id': 'ws', 'name': 'WS', 'desc': 'Word select line'},
        {'id': 'sd', 'name': 'SD', 'desc': 'Serial data line'},
    )
    annotations = (
        ('left', 'Left channel'),
        ('right', 'Right channel'),
        ('warnings', 'Warnings'),
    )
    binary = (
        ('wav', 'WAV file'),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.oldws = 1
        self.bitcount = 0
        self.data = 0
        self.saved_left_sample = 0
        self.samplesreceived = 0
        self.first_sample = None
        self.ss_block = None
        self.last_bitcount = -1
        self.wrote_wav_header = False

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putpb(self, data):
        self.put(self.ss_block, self.samplenum, self.out_python, data)

    def putbin(self, data):
        self.put(self.ss_block, self.samplenum, self.out_binary, data)

    def putb(self, data):
        self.put(self.ss_block, self.samplenum, self.out_ann, data)

    def report(self):
        # Calculate the sample rate.
        samplerate = '?'
        if self.ss_block is not None and \
            self.first_sample is not None and \
            self.ss_block > self.first_sample and \
            self.samplerate:
            samplerate = '%d' % (self.samplesreceived *
                self.samplerate / (self.ss_block -
                self.first_sample))

        return 'I²S: %d %d-bit samples received at %sHz' % \
            (self.samplesreceived, self.last_bitcount, samplerate)

    def wav_header(self):
        # Chunk descriptor
        h  = b'RIFF'
        h += b'\x24\x80\x00\x00' # Chunk size (2084)
        h += b'WAVE'
        # Fmt subchunk
        h += b'fmt '
        h += b'\x10\x00\x00\x00' # Subchunk size (16 bytes)
        h += b'\x01\x00'         # Audio format (0x0001 == PCM)
        h += b'\x02\x00'         # Number of channels (2)
        h += b'\x80\x3e\x00\x00' # Samplerate (16000)
        h += b'\x00\xfa\x00\x00' # Byterate (64000)
        h += b'\x04\x00'         # Blockalign (4)
        h += b'\x20\x00'         # Bits per sample (32)
        # Data subchunk
        h += b'data'
        h += b'\xff\xff\xff\xff' # Subchunk size (4G bytes) TODO
        return h

    def wav_sample(self, sample):
        # Left shift the data, so that the MSB is correct for less than 32-bit
        # samples.
        d = self.data << (32 - self.bitcount)
        return struct.pack('<I', d)

    def decode(self):
        while True:
            # Wait for a rising edge on the SCK pin.
            sck, ws, sd = self.wait({0: 'r'})

            self.data = (self.data << 1) | sd
            self.bitcount += 1

            # This was not the LSB unless WS has flipped.
            if ws == self.oldws:
                continue

            # Only submit the sample, if we received the beginning of it.
            if self.ss_block is not None:

                if not self.wrote_wav_header:
                    self.put(0, 0, self.out_binary, [0, self.wav_header()])
                    self.wrote_wav_header = True

                self.samplesreceived += 1

                sck = self.wait({0: 'f'})

                is_left = not self.oldws
                if is_left:
                    idx = 0
                    c1 = 'Left channel'
                    c2 = 'Left'
                    c3 = 'L'
                else:
                    idx = 1
                    c1 = 'Right channel'
                    c2 = 'Right'
                    c3 = 'R'
                v = '%08x' % self.data
                self.putpb(['DATA', [c3, self.data]])
                self.putb([idx, ['%s: %s' % (c1, v), '%s: %s' % (c2, v),
                                 '%s: %s' % (c3, v), c3]])

                # Save the left sample, and output both channels together when
                # the right channel is sampled. This avoids an issue when the
                # number of samples on the two channels are not equal.
                if is_left:
                    self.saved_left_sample = self.wav_sample(self.data)
                else:
                    self.putbin([0, self.saved_left_sample])
                    self.putbin([0, self.wav_sample(self.data)])

                # Check that the data word was the correct length.
                if self.last_bitcount != -1 and self.last_bitcount != self.bitcount:
                    self.putb([2, ['Received %d-bit word, expected %d-bit '
                                   'word' % (self.bitcount, self.last_bitcount)]])

                self.last_bitcount = self.bitcount
            else:
                sck = self.wait({0: 'f'})

            # Reset decoder state.
            self.data = 0
            self.bitcount = 0
            self.ss_block = self.samplenum

            # Save the first sample position.
            if self.first_sample is None:
                self.first_sample = self.samplenum

            self.oldws = ws
