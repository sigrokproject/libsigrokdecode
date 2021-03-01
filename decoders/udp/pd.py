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
import struct
from collections import namedtuple

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'udp'
    name     = 'UDP'
    longname = 'User Datagram Protocol'
    desc     = 'UDP'
    license  = 'gplv2+'
    inputs   = ['ipv4']
    outputs  = ['udp']
    tags     = ['Networking', 'PC']
    options = (
        {
            'id': 'format',
            'desc': 'Data format',
            'default': 'hex',
            'values': ('ascii', 'dec', 'hex', 'oct', 'bin')
        },
    )
    annotations = (
        ('header', 'Decoded header'),
        ('data', 'Decoded data'),
    )
    annotation_rows = (
        ('header', 'Header', (0,)),
        ('data', 'Data', (1,)),
    )

    # Initialise decoder
    def __init__(self):
        self.reset()

    # Reset decoder variables
    def reset(self):
        self.samplerate = None          # Session sample rate
        self.ss_block = None            # Annotation start sample
        self.es_block = None            # Annotation end sample
        self.format = None              # Payload format option

        self.payload_start = None       # Payload start sample

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.format = self.options["format"]

    # Put annotation for PulseView
    def putx(self, data):
        self.put(self.ss_block, self.es_block, self.out_ann, data)

    # Put Python object for stacked decoders
    def putp(self, data):
        self.put(self.ss_block, self.es_block, self.out_python, data)

    # Decode signal
    def decode(self, startsample, endsample, data):
        """
        data = (
            payload (bytearray),
            blocks (list) = [
                {"ss": start_sample, "es": end_sample},
                {"ss": start_sample, "es": end_sample},
                ....
                {"ss": start_sample, "es": end_sample},
            ]
        )
        """

        payload = data[0]
        blocks = data[1]


        # Unpack UDP packet header
        udp_tuple = namedtuple("udp", "source destination length checksum")
        fields = struct.unpack(">4H", payload[:8])
        udp = udp_tuple(*fields)


        # Source port
        self.ss_block = blocks[0]["ss"]
        self.es_block = blocks[1]["es"]
        self.putx([0, [
            "Source Port:    {}".format(udp.source),
            "Source Port",
            "Src"
        ]])


        # Destination port
        self.ss_block = blocks[2]["ss"]
        self.es_block = blocks[3]["es"]
        self.putx([0, [
            "Destination Port:    {}".format(udp.destination),
            "Destination Port",
            "Dst"
        ]])


        # Destination port
        self.ss_block = blocks[4]["ss"]
        self.es_block = blocks[5]["es"]
        self.putx([0, [
            "Length:    {} bytes".format(udp.length),
            "Length"
        ]])


        # Checksum
        self.ss_block = blocks[6]["ss"]
        self.es_block = blocks[7]["es"]
        self.putx([0, [
            "Checksum:    0x{:04X}".format(udp.checksum),
            "Checksum"
        ]])
        #TODO: Verify checksum
        self.payload_start = self.es_block


        # UDP Payload
        for i, b in enumerate(payload[8:udp.length]):
            # Add payload annotation
            self.ss_block = blocks[i + 8]["ss"]
            self.es_block = blocks[i + 8]["es"]

            # Format string as ASCII, decimal, hexadecimal, octal or binary
            data_str = None
            if self.format == "ascii":
                try:
                    data_str = "\"{}\"".format(bytes([b]).decode('utf-8'))
                except Exception:
                    data_str == "[0x{:02X}]".format(b)
            elif self.format == "dec": data_str = "{:d}".format(b)
            elif self.format == "hex": data_str = "0x{:02X}".format(b)
            elif self.format == "oct": data_str = "{:o}".format(b)
            elif self.format == "bin": data_str = "0b{:08b}".format(b)
            self.putx([1, [data_str]])


        # Push payload to stacked decoders
        self.ss_block = blocks[8]["ss"]
        self.es_block = blocks[udp.length]["es"]
        self.putp((payload[8:udp.length], blocks[8:udp.length]))
