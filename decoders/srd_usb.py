##
## This file is part of the sigrok project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

#
# USB Full-speed protocol decoder
#
# Full-speed USB signalling consists of two signal lines, both driven at 3.3V
# logic levels. The signals are DP (D+) and DM (D-), and normally operate in
# differential mode.
# The state where DP=1,DM=0 is J, the state DP=0,DM=1 is K.
# A state SE0 is defined where DP=DM=0. This common mode signal is used to
# signal a reset or end of packet.
#
# Data transmitted on the USB is encoded with NRZI. A transition from J to K
# or vice-versa indicates a logic 0, while no transition indicates a logic 1.
# If 6 ones are transmitted consecutively, a zero is inserted to force a
# transition. This is known as bit stuffing. Data is transferred at a rate
# of 12Mbit/s. The SE0 transmitted to signal an end-of-packet is two bit
# intervals long.
#
# Details:
# https://en.wikipedia.org/wiki/USB
# http://www.usb.org/developers/docs/
#

import sigrokdecode as srd

# States
SE0, J, K, SE1 = 0, 1, 2, 3
syms = {
        (0, 0): SE0,
        (1, 0): J,
        (0, 1): K,
        (1, 1): SE1,
}

def bitstr_to_num(bitstr):
    if not bitstr: return 0
    l = list(bitstr)
    l.reverse()
    return int(''.join(l), 2)

def packet_decode(packet):
    pids = {
        '10000111':'OUT',      # Tokens
        '10010110':'IN',
        '10100101':'SOF',
        '10110100':'SETUP',
        '11000011':'DATA0',    # Data
        '11010010':'DATA1',
        '01001011':'ACK',      # Handshake
        '01011010':'NAK',
        '01111000':'STALL',
        '01101001':'NYET',
    }

    sync = packet[:8]
    pid = packet[8:16]
    pid = pids.get(pid, pid)
    # Remove CRC.
    if pid in ('OUT', 'IN', 'SOF', 'SETUP'):
        data = packet[16:-5]
        if pid == 'SOF':
            data = str(bitstr_to_num(data))
        else:
            dev = bitstr_to_num(data[:7])
            ep = bitstr_to_num(data[7:])
            data = "DEV %d EP %d" % (dev, ep)

    elif pid in ('DATA0', 'DATA1'):
        data = packet[16:-16]
        tmp = ""
        while data:
            tmp += "%02X " % bitstr_to_num(data[:8])
            data = data[8:]
        data = tmp
    else:
        data = packet[16:]

    if sync != "00000001":
        return "SYNC INVALID!"

    return pid + ' ' + data

class Decoder(srd.Decoder):
    id = 'usb'
    name = 'USB'
    desc = 'Universal Serial Bus'
    longname = '...longname...'
    longdesc = '...longdesc...'
    author = 'Gareth McMullin'
    email = 'gareth@blacksphere.co.nz'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['usb']
    # Probe names with a set of defaults
    probes = [
        {'id': 'dp', 'name': 'D+', 'desc': 'USB D+ signal'},
        {'id': 'dm', 'name': 'D-', 'desc': 'USB D- signal'},
    ]
    options = {}

    def __init__(self):
        pass

    def start(self, metadata):
        self.rate = metadata['samplerate']
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'usb')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'usb')
        if self.rate < 48000000:
            raise Exception("Sample rate not sufficient for USB decoding")
        # Initialise decoder state.
        self.sym = J
        self.scount = 0
        self.packet = ''

    def decode(self, timeoffset, duration, data):
        out = []

        # FIXME
        for (samplenum, (dp, dm, x, y, z, a)) in data:

            self.scount += 1

            sym = syms[dp, dm]
            if sym == self.sym:
                continue

            if self.scount == 1:
                # We ignore single sample width pulses.
                # I sometimes get these with the OLS.
                self.sym = sym
                self.scount = 0
                continue

            # How many bits since the last transition?
            if self.packet or self.sym != J:
                bitcount = int((self.scount - 1) * 12000000 / self.rate)
            else:
                bitcount = 0

            if self.sym == SE0:
                if bitcount == 1:
                    # End-Of-Packet (EOP)
                    out += [{"type":"usb", "data":self.packet,
                              "display":packet_decode(self.packet)}]
                else:
                    # Longer than EOP, assume reset.
                    out += [{"type":"usb", "display":"RESET"}]
                self.scount = 0
                self.sym = sym
                self.packet = ''
                continue

            # Add bits to the packet string.
            self.packet += '1' * bitcount
            # Handle bit stuffing.
            if bitcount < 6 and sym != SE0:
                self.packet += '0'
            elif bitcount > 6:
                out += [{"type":"usb", "display":"BIT STUFF ERROR"}]

            self.scount = 0
            self.sym = sym

        if out != []:
            # self.put(0, 0, self.out_proto, out_proto)
            self.put(0, 0, self.out_ann, out)

