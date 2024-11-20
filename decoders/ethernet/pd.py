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
import zlib

from .dicts import *

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'ethernet'
    name     = 'Ethernet'
    longname = 'Ethernet II (IEEE 802.3)'
    desc     = 'Ethernet networking protocol'
    license  = 'gplv2+'
    inputs   = ['4b5b']
    outputs  = ['ethernet']
    tags     = ['Networking', 'PC']
    annotations = (
        ('header', 'Decoded header'),
        ('data', 'Decoded data'),
    )
    annotation_rows = (
        ('header', 'Header', (0,)),
        ('data', 'Data', (1,)),
    )
    binary = (
        ('pcapng', 'Wireshark packet capture (.pcapng)'),
    )

    # Initialise decoder
    def __init__(self):
        self.reset()

    # Reset decoder variables
    def reset(self):
        self.samplerate = None          # Session sample rate
        self.ss_block = None            # Annotation start sample
        self.es_block = None            # Annotation end sample

        self.state = "WAITING"          # Decoder state
        self.buffer = bytearray(b'')    # Decoder data buffer
        self.frame = bytearray(b'')     # Binary output buffer
        self.frame_start = None         # Frame start sample
        self.header_start = None        # Header start sample
        self.payload_start = None       # Payload start sample
        self.payload = bytearray()      # Ethernet payload bytes
        self.blocks = []                # Payload block start/stop samples

    # Get metadata from PulseView
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    # Register output types
    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.pcap_headers()

    # Put annotation for PulseView
    def putx(self, data):
        self.put(self.ss_block, self.es_block, self.out_ann, data)

    # Put binary data
    def putb(self, data):
        self.put(0, 0, self.out_binary, data)

    # Put Python object for stacked decoders
    def putp(self, data):
        self.put(self.ss_block, self.es_block, self.out_python, data)

    # Generate pcapng file headers
    def pcap_headers(self):
        # Section Header Block
        self.putb([0, struct.pack("<3I2HqI",
            0x0A0D0D0A,     # Block Type (SHB)
            28,             # Block Length (28)
            0x1A2B3C4D,     # Byte Order Magic
            1,              # Major Version
            0,              # Minor Version
            -1,             # Section Length
            28              # Block Length
        )])

        # Interface Description Block
        self.putb([0, struct.pack("<2I2H2I",
            1,              # Block Type (IDB)
            20,             # Block Length
            1,              # Link Type (Ethernet)
            0,              # Reserved
            1522,           # Snap Length (max packet lenth in bytes)
            20,             # Block Length
        )])

    # Add Ethernet frame to pcapng file
    def pcap_append(self):
        # Simple Packet Block
        pad_bytes = b''.join(b'\x00' for i in range(len(self.frame) % 4))
        block_len = 16 + len(self.frame) + len(pad_bytes)
        self.putb([0, struct.pack("<3I{}s{}sI".format(len(self.frame), len(pad_bytes)),
            3,                  # Block Type (SPB)
            block_len,          # Block Length
            len(self.frame),    # Original Packet Length
            bytes(self.frame),  # Packet Data
            pad_bytes,          # Padding
            block_len           # Block Length
        )])

        # Reset frame
        self.frame = bytearray(b'')

    # Decode signal
    def decode(self, startsample, endsample, data):
        # Tuple "data" contains ([str/byte] value, [boolean] is_control_symbol)

        # Handle control characters
        if data[1]:
            # START 2
            if data[0] == "K":
                # Set start sample of frame
                self.frame_start = endsample

            # TERMINATE
            elif data[0] == "T":
                # Add payload to frame
                self.frame.extend(self.payload)

                # Verify FCS
                fcs_ok = "OK" if zlib.crc32(self.frame) == 0x2144DF1C else "FAILED"

                # Add FCS annotation
                self.ss_block = startsample - int((endsample - startsample) * 8)
                self.es_block = endsample - (endsample - startsample)
                self.putx([0,
                    [
                        "Frame Check Sequence:    {}".format(fcs_ok),
                        "FCS:    {}".format(fcs_ok),
                        "FCS"
                    ]
                ])

                # Add frame to pcapng file
                self.pcap_append()

                # Push payload to stacked decoders
                self.es_block = self.ss_block                   # FCS start sample
                self.ss_block = self.payload_start
                self.putp((self.payload[:-4], self.blocks))     # Payload without FCS

            # RESET
            elif data[0] == "R":
                # Reset decoder state ready for next frame
                self.reset()

            return
        
        # Add byte to buffer
        self.buffer.append(data[0])

        # Waiting for start of frame
        if self.state == "WAITING":
            # Check for Start Frame Delimiter
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
                dst_mac = ":".join("{:02X}".format(octet) for octet in self.buffer)

                # Broadcast MAC
                if bytes(self.buffer) == b'\xFF\xFF\xFF\xFF\xFF\xFF':
                    dst_mac += " (Broadcast)"

                # Add preamble annotation
                self.es_block = endsample
                self.putx([0, ["Destination MAC:    {}".format(dst_mac), "Dst MAC"]])

                # Switch to Source MAC Address state
                self.frame.extend(self.buffer)
                self.buffer.clear()
                self.ss_block = endsample
                self.state = "SRC_MAC"

        # Source MAC address
        elif self.state == "SRC_MAC":
            if len(self.buffer) == 6:
                # Create MAC string
                src_mac = ":".join("{:02X}".format(octet) for octet in self.buffer)

                # Add preamble annotation
                self.es_block = endsample
                self.putx([0, ["Source MAC:    {}".format(src_mac), "Src MAC"]])

                # Switch to EtherType state
                self.frame.extend(self.buffer)
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
                    self.putx([0,
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
                self.frame.extend(self.buffer)
                self.buffer.clear()
                self.payload_start = endsample
                self.ss_block = endsample
                self.state = "PAYLOAD"

        # Frame payload
        elif self.state == "PAYLOAD":
            # Add tuple to payload
            self.payload.append(data[0])
            self.blocks.append({"ss": startsample, "es": endsample})

            # Add payload annotation
            self.ss_block = startsample
            self.es_block = endsample
            self.putx([1, ["0x{:02X}".format(data[0])]])
