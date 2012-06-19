##
## This file is part of the sigrok project.
##
## Copyright (C) 2011 Gareth McMullin <gareth@blacksphere.co.nz>
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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
        return 'SYNC INVALID: %s' % sync

    return pid + ' ' + data

class Decoder(srd.Decoder):
    api_version = 1
    id = 'usb_protocol'
    name = 'USB protocol'
    longname = 'Universal Serial Bus (LS/FS) protocol'
    desc = 'USB 1.x (low-speed and full-speed) serial protocol.'
    license = 'gplv2+'
    inputs = ['usb_signalling']
    outputs = ['usb_protocol']
    probes = []
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
        self.state = 'IDLE'

    def start(self, metadata):
        self.samplerate = metadata['samplerate']
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'usb_protocol')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'usb_protocol')

    def report(self):
        pass

    def decode(self, ss, es, data):
        (ptype, pdata) = data

        if ptype == 'PACKET':
            self.put(0, 0, self.out_ann, [0, [packet_decode(pdata)]])

        # TODO.

