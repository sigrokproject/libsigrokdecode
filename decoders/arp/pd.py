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
    id       = 'arp'
    name     = 'ARP'
    longname = 'Address Resolution Protocol'
    desc     = 'arp'
    license  = 'gplv2+'
    inputs   = ['ethernet']
    outputs  = ['']
    tags     = ['Networking', 'PC']
    annotations = (
        ('data', 'Decoded data'),
        ('msg', 'Message')
    )
    annotation_rows = (
        ('data', 'Data', (0,)),
        ('msg', 'Message', (1,))
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

        self.sha = None     # Source MAC
        self.spa = None     # Source IP
        self.tha = None     # Destination MAC
        self.tpa = None     # Destination IP
        self.oper = None    # Operation
        self.msg_start = None
        self.msg_end = None

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
        # Loop through bytes
        for i, b in enumerate(data):
            # Hardware type
            if i == 1:
                hw_type = (data[i-1]["data"] << 8) | data[i]["data"]

                # More than two types exist
                if hw_type == 1:
                    hw_type = "Ethernet"
                elif hw_type == 3:
                    hw_type = "AX.25"

                self.ss_block = data[i-1]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Hardware Type:    {}".format(hw_type),
                        "HW Type:    {}".format(hw_type),
                        "HW Type",
                        "HW"
                    ]
                ])

            # Protocol Type (Ethertype)
            elif i == 3:
                proto = (data[i-1]["data"] << 8) | data[i]["data"]

                # Known EtherType
                if proto in ethertype:
                    # Add EtherType annotation
                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([
                        0,
                        [
                            "Protocol:    {} (0x{:04X})".format(ethertype[proto][0], proto),
                            "Protocol:    {} (0x{:04X})".format(ethertype[proto][1], proto),
                            "Protocol:    {}".format(ethertype[proto][1]),
                            "Protocol"
                        ]
                    ])

                # Unknown EtherType
                else:
                    self.ss_block = data[i-1]["start"]
                    self.es_block = data[i]["end"]
                    self.putx([0, ["Protocol:    UNKNOWN", "Protocol"]])

            # Hardware Address Length
            elif i == 4:
                self.ss_block = data[i]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Hardware Address Length:    {}".format(data[i]["data"]),
                        "Hardware Length:    {}".format(data[i]["data"]),
                        "Hardware Length"
                    ]
                ])

            # Protocol Address Length
            elif i == 5:
                self.ss_block = data[i]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Protocol Address Length:    {}".format(data[i]["data"]),
                        "Protocol Length:    {}".format(data[i]["data"]),
                        "Protocol Length",
                    ]
                ])

            # Operation
            elif i == 7:
                ops = ["", "Request", "Reply"]
                self.oper = ops[(data[i-1]["data"] << 8) | data[i]["data"]]

                self.ss_block = data[i-1]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Operation:    {}".format(self.oper),
                        "OP:    {}".format(self.oper),
                        "OP"
                    ]
                ])

            # Sender Hardware Address (SHA) MAC
            elif i == 13:
                self.sha = "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}".format(
                    data[i-5]["data"],
                    data[i-4]["data"],
                    data[i-3]["data"],
                    data[i-2]["data"],
                    data[i-1]["data"],
                    data[i]["data"]
                )

                self.ss_block = data[i-5]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Source MAC Address:    {}".format(self.sha),
                        "Source MAC:    {}".format(self.sha),
                        "Source MAC"
                    ]
                ])
                self.msg_start = data[i-5]["start"]

            # Sender Protocol Address (SPA) IP
            elif i == 17:
                self.spa = "{}.{}.{}.{}".format(
                    data[i-3]["data"],
                    data[i-2]["data"],
                    data[i-1]["data"],
                    data[i]["data"]
                )

                self.ss_block = data[i-3]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Source IP Address:    {}".format(self.spa),
                        "Source IP:    {}".format(self.spa),
                        "Source IP"
                    ]
                ])

            # Target Hardware Address (THA) MAC
            elif i == 23:
                self.tha = "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}".format(
                    data[i-5]["data"],
                    data[i-4]["data"],
                    data[i-3]["data"],
                    data[i-2]["data"],
                    data[i-1]["data"],
                    data[i]["data"]
                )

                self.ss_block = data[i-5]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Destination MAC Address:    {}".format(self.tha),
                        "Destination MAC:    {}".format(self.tha),
                        "Destination MAC"
                    ]
                ])

            # Target Protocol Address (TPA) IP
            elif i == 27:
                self.tpa = "{}.{}.{}.{}".format(
                    data[i-3]["data"],
                    data[i-2]["data"],
                    data[i-1]["data"],
                    data[i]["data"]
                )

                self.ss_block = data[i-3]["start"]
                self.es_block = data[i]["end"]
                self.putx([
                    0,
                    [
                        "Destination IP Address:    {}".format(self.tpa),
                        "Destination IP:    {}".format(self.tpa),
                        "Destination IP"
                    ]
                ])
                self.msg_end = data[i]["end"]

        # Add message annotation
        self.ss_block = self.msg_start
        self.es_block = self.msg_end

        if self.oper == "Request":
            self.putx([1, ["Who has {}? Tell {} ({})".format(self.tpa, self.spa, self.sha)]])
        elif self.oper == "Reply":
            self.putx([1, ["{} is at {}".format(self.spa, self.sha)]])
