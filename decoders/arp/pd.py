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
            bytearray payload,
            list blocks = [
                {"ss": int start_sample, "es": int end_sample},
                {"ss": int start_sample, "es": int end_sample},
                ...
                {"ss": int start_sample, "es": int end_sample},
            ],
            bytes src_ip,
            bytes dst_ip
        )
        """

        payload = data[0]
        blocks = data[1]


        # Unpack ARP packet
        arp_tuple = namedtuple("arp", "htype ptype hlen plen oper sha spa tha tpa")
        fields = struct.unpack(">2H2BH6s4s6s4s", payload[:28])
        arp = arp_tuple(*fields)


        # Hardware type
        self.ss_block = blocks[0]["ss"]
        self.es_block = blocks[1]["es"]
        self.putx([0, [
            "Hardware Type:    {}".format(arp.htype),
            "HW Type:    {}".format(arp.htype),
            "HW Type",
            "HW"
        ]])


        # EtherType
        self.ss_block = blocks[2]["ss"]
        self.es_block = blocks[3]["es"]
        if arp.ptype in ethertype:
            # Add known EtherType annotation
            self.putx([0, [
                "Protocol:    {} (0x{:04X})".format(ethertype[arp.ptype][0], arp.ptype),
                "Protocol:    {} (0x{:04X})".format(ethertype[arp.ptype][1], arp.ptype),
                "Protocol:    {}".format(ethertype[arp.ptype][1]),
                "Protocol"
            ]])
        else:
            # Add unknown EtherType annotation
            self.putx([0, ["Protocol:    UNKNOWN", "Protocol"]])


        # Hardware Address Length
        self.ss_block = blocks[4]["ss"]
        self.es_block = blocks[4]["es"]
        self.putx([0, [
            "Hardware Address Length:    {}".format(arp.hlen),
            "Hardware Length:    {}".format(arp.hlen),
            "Hardware Length"
        ]])


        # Protocol Address Length
        self.ss_block = blocks[5]["ss"]
        self.es_block = blocks[5]["es"]
        self.putx([0, [
            "Protocol Address Length:    {}".format(arp.plen),
            "Protocol Length:    {}".format(arp.plen),
            "Protocol Length",
        ]])


        # Operation
        ops = ["", "Request", "Reply"]
        self.oper = ops[arp.oper]
        self.ss_block = blocks[6]["ss"]
        self.es_block = blocks[7]["es"]
        self.putx([0, [
            "Operation:    {}".format(self.oper),
            "OP:    {}".format(self.oper),
            "OP"
        ]])


        # Sender Hardware Address (SHA) MAC
        self.sha = ":".join("{:02X}".format(octet) for octet in arp.sha)
        self.ss_block = blocks[8]["ss"]
        self.es_block = blocks[13]["es"]
        self.putx([0, [
            "Source MAC Address:    {}".format(self.sha),
            "Source MAC:    {}".format(self.sha),
            "Source MAC"
        ]])
        self.msg_start = self.ss_block


        # Sender Protocol Address (SPA) IP
        self.spa = ".".join(str(octet) for octet in arp.spa)
        self.ss_block = blocks[14]["ss"]
        self.es_block = blocks[17]["es"]
        self.putx([0, [
            "Source IP Address:    {}".format(self.spa),
            "Source IP:    {}".format(self.spa),
            "Source IP"
        ]])


        # Target Hardware Address (THA) MAC
        self.tha = ":".join("{:02X}".format(octet) for octet in arp.tha)
        self.ss_block = blocks[18]["ss"]
        self.es_block = blocks[23]["es"]
        self.putx([0, [
            "Destination MAC Address:    {}".format(self.tha),
            "Destination MAC:    {}".format(self.tha),
            "Destination MAC"
        ]])


        # Target Protocol Address (TPA) IP
        self.tpa = ".".join(str(octet) for octet in arp.tpa)
        self.ss_block = blocks[24]["ss"]
        self.es_block = blocks[27]["es"]
        self.putx([0, [
            "Destination IP Address:    {}".format(self.tpa),
            "Destination IP:    {}".format(self.tpa),
            "Destination IP"
        ]])
        self.msg_end = self.es_block


        # Add message annotation
        self.ss_block = self.msg_start
        self.es_block = self.msg_end

        if self.oper == "Request":
            if self.spa == self.tpa:    # Announcement
                self.putx([1, ["ARP Announcement for {} ({})".format(self.spa, self.sha)]])
            elif self.spa == "0.0.0.0": # Probe
                self.putx([1, ["ARP Probe for {} ({})".format(self.tpa, self.sha)]])
            else:                       # Request
                self.putx([1, ["Who has {}? Tell {} ({})".format(self.tpa, self.spa, self.sha)]])
        elif self.oper == "Reply":
            self.putx([1, ["{} is at {}".format(self.spa, self.sha)]])
