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

from .dicts import *

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'ipv4'
    name     = 'IPv4'
    longname = 'Internet Protocol Version 4'
    desc     = 'IPv4'
    license  = 'gplv2+'
    inputs   = ['ethernet']
    outputs  = ['ipv4']
    tags     = ['Networking', 'PC']
    #options = ()
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
        ihl = None

        # Loop through bytes
        for i, b in enumerate(data):
            # Version and IHL
            if i == 0:
                ver = b["data"] >> 4            # IP Version (always 4)
                ihl = (b["data"] & 0x0F) * 4    # Header Length (usually 5)

                # Add payload annotation
                self.ss_block = b["start"]
                self.es_block = b["end"]
                self.putx([
                    0,
                    [
                        "Version: {}    Header Length: {} bytes".format(ver, ihl),
                        "Version and Header Length",
                        "Version and IHL",
                        "IHL"
                    ]
                ])
            
            # IP Header
            elif 0 < i < ihl:
                # DSCP and ECN
                if i == 1:
                    self.ss_block = b["start"]
                    self.es_block = b["end"]
                    self.putx([
                        0,
                        [
                            "Differentiated Services Code Point (DSCP) and Explicit Congestion Notification (ECN)",
                            "DSCP and ECN",
                            "DSCP"
                        ]
                    ])

                # Total packet length
                elif i == 3:
                    length = (data[i-1]["data"] << 8) | data[i]["data"]

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Packet Length:    {} bytes".format(length),
                            "Packet Length",
                            "Length"
                        ]
                    ])
                
                # Identification
                elif i == 5:
                    ident = (data[i-1]["data"] << 8) | data[i]["data"]

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Identification:    {}".format(ident),
                            "Identification",
                            "ID"
                        ]
                    ])
                
                # Flags
                elif i == 6:
                    df = (b["data"] & 0b010 ) >> 1
                    mf = (b["data"] & 0b100 ) >> 2

                    self.ss_block = b["start"]
                    self.es_block = b["start"] + int(((b["end"] - b["start"]) / 8) * 3)
                    self.putx([
                        0,
                        [
                            "Don't Fragment: {}    More Fragments: {}".format(bool(df), bool(mf)),
                            "DF: {}    MF: {}".format(bool(df), bool(mf)),
                            "DF and MF",
                            "Flags"
                        ]
                    ])
                
                # Fragment offset
                elif i == 7:
                    offset = (((data[i-1]["data"] & 0b00011111) << 8) | data[i]["data"]) * 8

                    self.ss_block = data[i-1]["start"] + int(((data[i]["end"] - data[i]["start"]) / 8) * 3)
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Fragment Offset:    {} bytes".format(offset),
                            "Fragment Offset",
                            "Offset"
                        ]
                    ])
                
                # Time to live (TTL)
                elif i == 8:
                    ttl = b["data"]

                    self.ss_block = b["start"]
                    self.es_block = b["end"]
                    self.putx([
                        0,
                        [
                            "Time To Live:    {}".format(ttl),
                            "Time To Live",
                            "TTL"
                        ]
                    ])

                # Protocol
                elif i == 9:
                    protocol = b["data"]

                    # Known protocol
                    if protocol in ip_protocol:
                        self.ss_block = b["start"]
                        self.es_block = b["end"]
                        self.putx([
                            0,
                            [
                                "Protocol:    {} ({})".format(ip_protocol[protocol][1], ip_protocol[protocol][0]),
                                "Protocol:    {}".format(ip_protocol[protocol][1]),
                                "Protocol:    {}".format(ip_protocol[protocol][0]),
                                ip_protocol[protocol][0]
                            ]
                        ])

                    # Unknown protocol
                    else:
                        self.ss_block = b["start"]
                        self.es_block = b["end"]
                        self.putx([0, ["Protocol:    UNKNOWN", "Protocol"]])

                # Header checksum
                elif i == 11:
                    checksum = (data[i-1]["data"] << 8) | data[i]["data"]

                    #TODO: Calculate checksum and compare

                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Header Checksum:    0x{:04X}".format(checksum),
                            "Checksum:    0x{:04X}".format(checksum),
                            "Checksum"
                        ]
                    ])

                # Source IP
                elif i == 15:
                    octets = [
                        data[i-3]["data"],
                        data[i-2]["data"],
                        data[i-1]["data"],
                        data[i]["data"],
                    ]

                    self.ss_block = data[i-3]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Source IP Address:    {}.{}.{}.{}".format(octets[0], octets[1], octets[2], octets[3]),
                            "Source IP:    {}.{}.{}.{}".format(octets[0], octets[1], octets[2], octets[3]),
                            "Source IP"
                        ]
                    ])

                # Destination IP
                elif i == 19:
                    octets = [
                        data[i-3]["data"],
                        data[i-2]["data"],
                        data[i-1]["data"],
                        data[i]["data"],
                    ]

                    self.ss_block = data[i-3]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Destination IP Address:    {}.{}.{}.{}".format(octets[0], octets[1], octets[2], octets[3]),
                            "Destination IP:    {}.{}.{}.{}".format(octets[0], octets[1], octets[2], octets[3]),
                            "Destination IP"
                        ]
                    ])

                    # Payload start sample for stacked decoders
                    self.payload_start = data[i]["end"]

            # IP Payload
            elif i >= ihl:
                # Add byte to payload
                self.payload.append({
                    "start": b["start"],
                    "end":   b["end"],
                    "data":  b["data"]
                })

                # Add payload annotation
                self.ss_block = b["start"]
                self.es_block = b["end"]
                self.putx([1, ["0x{:02X}".format(b["data"])]])

        # Push payload to stacked decoders
        self.ss_block = self.payload_start
        self.es_block = data[-1]["end"]
        self.putp(self.payload)
