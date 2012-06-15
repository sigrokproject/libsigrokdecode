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

# USB (low-speed and full-speed) protocol decoder

import sigrokdecode as srd

# Full-speed symbols (used as states of our state machine, too).
# Note: Low-speed J and K are inverted compared to the full-speed J and K!
syms = {
        # (<dp>, <dm>): <symbol/state>
        (0, 0): 'SE0',
        (1, 0): 'J',
        (0, 1): 'K',
        (1, 1): 'SE1',
}

# Packet IDs (PIDs).
# The first 4 bits are the 'packet type' field, the last 4 bits are the
# 'check field' (each bit in the check field must be the inverse of the resp.
# bit in the 'packet type' field; if not, that's a 'PID error').
# For the 4-bit strings, the left-most '1' or '0' is the LSB, i.e. it's sent
# to the bus first.
pids = {
    # Tokens
    '10000111': ['OUT', 'Address & EP number in host-to-function transaction'],
    '10010110': ['IN', 'Address & EP number in function-to-host transaction'],
    '10100101': ['SOF', 'Start-Of-Frame marker & frame number'],
    '10110100': ['SETUP', 'Address & EP number in host-to-function transaction for SETUP to a control pipe'],

    # Data
    # Note: DATA2 and MDATA are HS-only.
    '11000011': ['DATA0', 'Data packet PID even'],
    '11010010': ['DATA1', 'Data packet PID odd'],
    '11100001': ['DATA2', 'Data packet PID HS, high bandwidth isosynchronous transaction in a microframe'],
    '11110000': ['MDATA', 'Data packet PID HS for split and high-bandwidth isosynchronous transactions'],

    # Handshake
    '01001011': ['ACK', 'Receiver accepts error-free packet'],
    '01011010': ['NAK', 'Receiver cannot accept or transmitter cannot send'],
    '01111000': ['STALL', 'EP halted or control pipe request unsupported'],
    '01101001': ['NYET', 'No response yet from receiver'],

    # Special
    '00111100': ['PRE', 'Host-issued preamble; enables downstream bus traffic to low-speed devices'],
    '00111100': ['ERR', 'Split transaction error handshake'],
    '00011110': ['SPLIT', 'HS split transaction token'],
    '00101101': ['PING', 'HS flow control probe for a bulk/control EP'],
    '00001111': ['Reserved', 'Reserved PID'],
}

def get_sym(signalling, dp, dm):
    # Note: Low-speed J and K are inverted compared to the full-speed J and K!
    if signalling == 'low-speed':
        s = syms[dp, dm]
        if s == 'J':
            return 'K'
        elif s == 'K':
            return 'J'
        else:
            return s
    elif signalling == 'full-speed':
       return syms[dp, dm]

def bitstr_to_num(bitstr):
    if not bitstr:
        return 0
    l = list(bitstr)
    l.reverse()
    return int(''.join(l), 2)

def packet_decode(packet):
    sync = packet[:8]
    pid = packet[8:16]
    pid = pids.get(pid, (pid, ''))[0]

    # Remove CRC.
    if pid in ('OUT', 'IN', 'SOF', 'SETUP'):
        data = packet[16:-5]
        if pid == 'SOF':
            data = str(bitstr_to_num(data))
        else:
            dev = bitstr_to_num(data[:7])
            ep = bitstr_to_num(data[7:])
            data = 'DEV %d EP %d' % (dev, ep)
    elif pid in ('DATA0', 'DATA1'):
        data = packet[16:-16]
        tmp = ''
        while data:
            tmp += '%02x ' % bitstr_to_num(data[:8])
            data = data[8:]
        data = tmp
    else:
        data = packet[16:]

    # The SYNC pattern for low-speed/full-speed is KJKJKJKK (0001).
    if sync != '00000001':
        return 'SYNC INVALID!'

    return pid + ' ' + data

class Decoder(srd.Decoder):
    api_version = 1
    id = 'usb'
    name = 'USB'
    longname = 'Universal Serial Bus (LS/FS)'
    desc = 'USB 1.x (low-speed and full-speed) serial protocol.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['usb']
    probes = [
        {'id': 'dp', 'name': 'D+', 'desc': 'USB D+ signal'},
        {'id': 'dm', 'name': 'D-', 'desc': 'USB D- signal'},
    ]
    optional_probes = []
    options = {
        'signalling': ['Signalling', 'full-speed'],
    }
    annotations = [
        ['Text', 'Human-readable text']
    ]

    def __init__(self):
        self.sym = 'J'
        self.samplenum = 0
        self.scount = 0
        self.packet = ''

    def start(self, metadata):
        self.samplerate = metadata['samplerate']

        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'usb')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'usb')

    def report(self):
        pass

    def decode(self, ss, es, data):
        for (self.samplenum, (dp, dm)) in data:

            # Note: self.samplenum is the absolute sample number, whereas
            # self.scount only counts the number of samples since the
            # last change in the D+/D- lines.
            self.scount += 1

            sym = get_sym(self.options['signalling'], dp, dm)

            # Wait for a symbol change (i.e., change in D+/D- lines).
            if sym == self.sym:
                continue

            if self.scount == 1:
                # We ignore single sample width "pulses", i.e., symbol changes
                # (D+/D- line changes). I sometimes get these with the OLS.
                self.sym = sym
                self.scount = 0
                continue

            # How many bits since the last transition?
            if self.packet != '' or self.sym != 'J':
                if self.options['signalling'] == 'low-speed':
                    bitrate = 1500000 # 1.5Mb/s (+/- 1.5%)
                elif self.options['signalling'] == 'full-speed':
                    bitrate = 12000000 # 12Mb/s (+/- 0.25%)
                bitcount = int((self.scount - 1) * bitrate / self.samplerate)
            else:
                bitcount = 0

            if self.sym == 'SE0':
                if bitcount == 1:
                    # End-Of-Packet (EOP)
                    self.put(0, 0, self.out_ann,
                             [0, [packet_decode(self.packet), self.packet]])
                else:
                    # Longer than EOP, assume reset.
                    self.put(0, 0, self.out_ann, [0, ['RESET']])
                self.scount = 0
                self.sym = sym
                self.packet = ''
                continue

            # Add bits to the packet string.
            self.packet += '1' * bitcount

            # Handle bit stuffing.
            if bitcount < 6 and sym != 'SE0':
                self.packet += '0'
            elif bitcount > 6:
                self.put(0, 0, self.out_ann, [0, ['BIT STUFF ERROR']])

            self.scount = 0
            self.sym = sym

