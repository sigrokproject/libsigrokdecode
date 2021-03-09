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

# EtherType
ethertype = {
    0x0800: ["Internet Protocol Version 4", "IPv4"],
    0x0806: ["Address Resolution Protocol", "ARP"],
    0x0842: ["Wake-on-LAN", "WoL"],
    0x22F0: ["Audio Video Transport Protocol", "AVTP"],
    0x22F3: ["IETF TRILL Protocol", "TRILL"],
    0x22EA: ["Stream Reservation Protocol", "SRP"],
    0x6002: ["DEC MOP", "DEC MOP RC"],
    0x6003: ["DECnet Phase IV", "DECnet"],
    0x6004: ["DEC LAT", "DEC LAT"],
    0x8035: ["Reverse Address Resolution Protocol", "RARP"],
    0x809B: ["AppleTalk (Ethertalk)", "AppleTalk"],
    0x80F3: ["AppleTalk Address Resolution Protocol", "AARP"],
    0x8100: ["VLAN-tagged Frame", "VLAN"],
    0x8102: ["Simple Loop Prevention Protocol", "SLPP"],
    0x8103: ["Virtual Link Aggregation Control Protocol", "VLACP"],
    0x8137: ["Internetwork Packet Exchange", "IPX"],
    0x8204: ["QNX Qnet", "QNX Qnet"],
    0x86DD: ["Internet Protocol Version 6", "IPv6"],
    0x8808: ["Ethernet flow control", "Flow"],
    0x8809: ["Link Aggregation Control Protocol", "LACP"],
    0x8819: ["CobraNet", "CobraNet"],
    0x8847: ["Multiprotocol Label Switching unicast", "MPLS"],
    0x8848: ["Multiprotocol Label Switching multicast", "MPLS"],
    0x8863: ["PPPoE Discovery Stage", "PPPoE"],
    0x8864: ["PPPoE Session Stage", "PPPoE"],
    0x887B: ["HomePlug 1.0 MME", "HomePlug"],
    0x888E: ["Extensible Authentication Protocol", "EAP"],
    0x8892: ["PROFINET Protocol", "PROFINET"],
    0x889A: ["HyperSCSI (SCSI over Ethernet)", "SCSI"],
    0x88A2: ["ATA over Ethernet", "ATA"],
    0x88A4: ["EtherCAT Protocol", "EtherCAT"],
    0x88A8: ["Service VLAN tag identifier", "VLAN"],
    0x88AB: ["Ethernet Powerlink", "Powerlink"],
    0x88B8: ["Generic Object Oriented Substation event", "GOOSE"],
    0x88B9: ["Generic Substation Events Management Services", "GSE"],
    0x88BA: ["Sampled Value Transmission", "SV"],
    0x88BF: ["MikroTik RoMON", "RoMON"],
    0x88CC: ["Link Layer Discovery Protocol", "LLDP"],
    0x88CD: ["SERCOS III", "SERCOS"],
    0x88E3: ["Media Redundancy Protocol", "MRP"],
    0x88E5: ["IEEE 802.1AE MAC security", "MACsec"],
    0x88E7: ["Provider Backbone Bridges", "PBB"],
    0x88F7: ["Precision Time Protocol", "PTP"],
    0x88F8: ["Network Controller Sideband Interface", "NC-SI"],
    0x88FB: ["Parallel Redundancy Protocol", "PRP"],
    0x8902: ["Connectivity Fault Management", "CFM"],
    0x8906: ["Fibre Channel over Ethernet", "FCoE"],
    0x8914: ["FCoE Initialization Protocol", "FCoE"],
    0x8915: ["Remote Direct Memory Access", "RDMA"],
    0x891D: ["TTEthernet Protocol Control Frame", "TTE"],
    0x893a: ["IEEE 1905.1 Protocol", "1905.1"],
    0x892F: ["High-availability Seamless Redundancy", "HSR"],
    0x9000: ["Ethernet Configuration Testing Protocol", "ECTP"],
    0x9100: ["VLAN-tagged Frame", "VLAN"],
    0xF1C1: ["Frame Replication and Elimination for Reliability", "FRER"],
}
