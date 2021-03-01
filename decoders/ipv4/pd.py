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

        self.payload_start = None       # Payload start sample
        self.ihl = None                 # IP header length

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)

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


        # Get Internet Header Length (IHL)
        self.ihl = (payload[0] & 0x0F) * 4      # Header Length (typically 5 = 20 bytes)
        if self.ihl != 20: return               #TODO: Support optional fields


        # Add version/length annotation
        self.ss_block = blocks[0]["ss"]
        self.es_block = blocks[0]["es"]
        self.putx([0, [
            "Version: 4    Header Length: {} bytes".format(self.ihl),
            "Version and Header Length",
            "Version and IHL",
            "IHL"
        ]])


        # Unpack IP packet header
        ip_tuple = namedtuple("ip", "length ident fragment ttl protocol checksum source destination")
        fields = struct.unpack(">3H2BH4s4s", payload[2:20])
        ip = ip_tuple(*fields)


        # DSCP and ECN
        self.ss_block = blocks[1]["ss"]
        self.es_block = blocks[1]["es"]
        self.putx([0, [
            "Differentiated Services Code Point (DSCP) and Explicit Congestion Notification (ECN)",
            "DSCP and ECN",
            "DSCP"
        ]])


        # Total packet length
        self.ss_block = blocks[2]["ss"]
        self.es_block = blocks[3]["es"]
        self.putx([0, [
            "Packet Length:    {} bytes".format(ip.length),
            "Packet Length",
            "Length"
        ]])


        # Identification
        self.ss_block = blocks[4]["ss"]
        self.es_block = blocks[5]["es"]
        self.putx([0, [
            "Identification:    {}".format(ip.ident),
            "Identification",
            "ID"
        ]])


        # Flags
        df = (payload[6] & 0b010 ) >> 1
        mf = (payload[6] & 0b100 ) >> 2
        self.ss_block = blocks[6]["ss"]
        self.es_block = blocks[6]["ss"] + int(((blocks[6]["es"] - blocks[6]["ss"]) / 8) * 3)
        self.putx([0, [
            "Don't Fragment: {}    More Fragments: {}".format(bool(df), bool(mf)),
            "DF: {}    MF: {}".format(bool(df), bool(mf)),
            "DF and MF",
            "Flags"
        ]])


        # Fragment offset
        offset = (((payload[6] & 0b00011111) << 8) | payload[7]) * 8
        self.ss_block = blocks[6]["ss"] + int(((blocks[6]["es"] - blocks[6]["ss"]) / 8) * 3)
        self.es_block = blocks[7]["es"]
        self.putx([0, [
            "Fragment Offset:    {} bytes".format(offset),
            "Fragment Offset",
            "Offset"
        ]])


        # Time to live (TTL)
        self.ss_block = blocks[8]["ss"]
        self.es_block = blocks[8]["es"]
        self.putx([0, [
            "Time To Live:    {}".format(ip.ttl),
            "Time To Live",
            "TTL"
        ]])


        # Protocol
        self.ss_block = blocks[9]["ss"]
        self.es_block = blocks[9]["es"]
        if ip.protocol in ip_protocol:
            # Add known protocol annotation
            self.putx([0, [
                "Protocol:    {} ({})".format(ip_protocol[ip.protocol][1], ip_protocol[ip.protocol][0]),
                "Protocol:    {}".format(ip_protocol[ip.protocol][1]),
                "Protocol:    {}".format(ip_protocol[ip.protocol][0]),
                ip_protocol[ip.protocol][0]
            ]])
        else:
            # Add unknown protocol annotation
            self.putx([0, ["Protocol:    UNKNOWN", "Protocol"]])


        # Header checksum
        self.ss_block = blocks[10]["ss"]
        self.es_block = blocks[11]["es"]
        self.putx([0, [
            "Header Checksum:    0x{:04X}".format(ip.checksum),
            "Checksum:    0x{:04X}".format(ip.checksum),
            "Checksum"
        ]])
        #TODO: Verify checksum


        # Source IP
        ip_src = ".".join(str(octet) for octet in ip.source)
        self.ss_block = blocks[12]["ss"]
        self.es_block = blocks[15]["es"]
        self.putx([0, [
            "Source IP Address:    {}".format(ip_src),
            "Source IP:    {}".format(ip_src),
            "Source IP"
        ]])


        # Destination IP
        ip_dst = ".".join(str(octet) for octet in ip.destination)
        self.ss_block = blocks[16]["ss"]
        self.es_block = blocks[19]["es"]
        self.putx([0, [
            "Destination IP Address:    {}".format(ip_dst),
            "Destination IP:    {}".format(ip_dst),
            "Destination IP"
        ]])
        self.payload_start = self.es_block


        # IP Payload
        for i, b in enumerate(payload[20:]):
            # Add payload annotation
            self.ss_block = blocks[i + 20]["ss"]
            self.es_block = blocks[i + 20]["es"]
            self.putx([1, ["0x{:02X}".format(b)]])

        # Push payload to stacked decoders
        self.ss_block = blocks[20]["ss"]
        self.es_block = blocks[-1]["es"]
        self.putp((payload[20:], blocks[20:]))
