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
import zlib

from .dicts import *

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'ethernet'
    name     = 'Ethernet'
    longname = 'Ethernet II'
    desc     = 'Ethernet II networking protocol'
    license  = 'gplv2+'
    inputs   = ['4b5b']
    outputs  = ['ethernet']
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

        self.state = "WAITING"
        self.buffer = bytearray(b'')
        self.frame_start = None
        self.header_start = None
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

    # Reverse integer bits
    def reverse_bits(self, n, width):
        b = '{:0{width}b}'.format(n, width=width)
        return int(b[::-1], 2)

    # Decode signal
    def decode(self, startsample, endsample, data):
        # Handle control character
        if data["control"] != None:
            if data["control"] == "T":  # TERMINATE
                # Get FCS
                fcs = int.from_bytes(self.buffer[-4:], byteorder="big")
                #fcs = self.reverse_bits(fcs, 32)

                # Calculate FCS CRC-32
                #payload = self.buffer[:-4]
                #fcs_calc = zlib.crc32(payload) & 0xFFFFFFFF
                #TODO: Fix CRC

                # Add FCS annotation
                self.ss_block = startsample - int((endsample - startsample) * 8)
                self.es_block = endsample - (endsample - startsample)
                self.putx([
                    0,
                    [
                        "Frame Check Sequence:    0x{:08X}".format(fcs),
                        "Frame Check Sequence",
                        "FCS"
                    ]
                ])

                # Trim FCS from payload
                self.payload = self.payload[:-4]

                # Push payload to stacked decoders
                self.ss_block = self.payload_start
                self.es_block = startsample - int((endsample - startsample) * 8)
                self.putp(self.payload)

            #TODO: Handle RESET control character
            return
        
        # Add byte to buffer
        elif data["data"] != None: self.buffer.append(data["data"])

        # Waiting for start of frame
        if self.state == "WAITING":
            # Get start position of frame
            if len(self.buffer) == 1: self.frame_start = startsample
            
            # Frame Preamble and Start Frame Delimiter
            if self.buffer[-1] == 0xD5:
                # Add preamble annotation
                self.ss_block = self.frame_start
                self.es_block = int(endsample - ((endsample - self.frame_start) / len(self.buffer)))
                self.putx([0, ["Preamble"]])

                # Add SFD annotation
                self.ss_block = int(endsample - ((endsample - self.frame_start) / len(self.buffer)))
                self.es_block = endsample
                self.putx([0, ["Start Frame Delimiter", "SFD"]])

                # Switch to Destination MAC Address state
                self.buffer.clear()
                self.header_start = endsample
                self.ss_block = endsample
                self.state = "DST_MAC"
        
        # Destination MAC address
        elif self.state == "DST_MAC":
            if len(self.buffer) == 6:
                # Create MAC string
                dst_mac = ""
                for octet in self.buffer:
                    dst_mac += "{:X}:".format(octet)
                dst_mac = dst_mac[:-1]

                # Broadcast MAC
                if bytes(self.buffer) == b'\xFF\xFF\xFF\xFF\xFF\xFF':
                    dst_mac += " (Broadcast)"

                # Add preamble annotation
                self.es_block = endsample
                self.putx([0, ["Destination MAC:    {}".format(dst_mac), "Dst MAC"]])

                # Switch to Source MAC Address state
                self.buffer.clear()
                self.ss_block = endsample
                self.state = "SRC_MAC"

        # Source MAC address
        elif self.state == "SRC_MAC":
            if len(self.buffer) == 6:
                # Create MAC string
                src_mac = ""
                for octet in self.buffer:
                    src_mac += "{:X}:".format(octet)
                src_mac = src_mac[:-1]

                # Add preamble annotation
                self.es_block = endsample
                self.putx([0, ["Source MAC:    {}".format(src_mac), "Src MAC"]])

                # Switch to EtherType state
                self.buffer.clear()
                self.ss_block = endsample
                self.state = "ETH_TYPE"

        # EtherType
        elif self.state == "ETH_TYPE":
            if len(self.buffer) == 2:
                # Get EtherType
                et = int.from_bytes(self.buffer, byteorder="big")

                # Known EtherType
                if et in ethertype:
                    # Add EtherType annotation
                    self.es_block = endsample
                    self.putx([
                        0,
                        [
                            "EtherType:    {} (0x{:04X})".format(ethertype[et][0], et),
                            "EtherType:    {} (0x{:04X})".format(ethertype[et][1], et),
                            "EtherType:    {}".format(ethertype[et][1]),
                            "EtherType"
                        ]
                    ])

                # Unknown EtherType
                else:
                    self.es_block = endsample
                    self.putx([0, ["EtherType:    UNKNOWN", "EtherType"]])
                
                # Switch to Payload state
                self.buffer.clear()
                self.payload_start = endsample
                self.ss_block = endsample
                self.state = "PAYLOAD"

        # Frame payload
        elif self.state == "PAYLOAD":
            # Add byte to payload
            self.payload.append({
                "start": startsample,
                "end":   endsample,
                "data":  data["data"]
            })

            # Add payload annotation
            self.ss_block = startsample
            self.es_block = endsample
            self.putx([1, ["0x{:02X}".format(data["data"])]])
