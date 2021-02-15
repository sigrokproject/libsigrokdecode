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

        self.payload_start = None
        self.payload = []

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.format = self.options["format"]

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
        length = None

        # Loop through bytes
        for i, b in enumerate(data):
            # UDP Header
            if 0 < i < 8:
                # Source port
                if i == 1:
                    src_port = (data[i-1]["data"] << 8) | data[i]["data"]

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Source Port:    {}".format(src_port),
                            "Source Port",
                            "Src"
                        ]
                    ])

                # Destination port
                elif i == 3:
                    dst_port = (data[i-1]["data"] << 8) | data[i]["data"]

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Destination Port:    {}".format(dst_port),
                            "Destination Port",
                            "Dst"
                        ]
                    ])

                # Packet Length
                elif i == 5:
                    length = (data[i-1]["data"] << 8) | data[i]["data"]

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Length:    {} bytes".format(length),
                            "Length"
                        ]
                    ])

                # Checksum
                elif i == 7:
                    checksum = (data[i-1]["data"] << 8) | data[i]["data"]

                    #TODO: Calculate checksum and compare

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Checksum:    0x{:04X}".format(checksum),
                            "Checksum"
                        ]
                    ])

                    # Payload start sample for stacked decoders
                    self.payload_start = data[i]["end"]

            # UDP Payload
            elif 7 < i < length:
                # Add byte to payload
                self.payload.append({
                    "start": b["start"],
                    "end":   b["end"],
                    "data":  b["data"]
                })

                # Format string as ASCII, decimal, hexadecimal, octal or binary
                data_str = None
                if self.format == "ascii":
                    try:
                        data_str = "\"{}\"".format(bytes([b["data"]]).decode('utf-8'))
                    except Exception:
                        data_str == "[0x{:02X}]".format(b["data"])
                elif self.format == "dec": data_str = "{:d}".format(b["data"])
                elif self.format == "hex": data_str = "0x{:02X}".format(b["data"])
                elif self.format == "oct": data_str = "{:o}".format(b["data"])
                elif self.format == "bin": data_str = "0b{:08b}".format(b["data"])
                
                # Add payload annotation
                self.ss_block = b["start"]
                self.es_block = b["end"]
                self.putx([1, [data_str]])

        # Push payload to stacked decoders
        self.ss_block = self.payload_start
        self.es_block = data[-1]["end"]
        self.putp(self.payload)
