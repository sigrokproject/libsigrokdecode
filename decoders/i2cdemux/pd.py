##
## This file is part of the sigrok project.
##
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

# Generic I2C demultiplexing protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'i2cdemux'
    name = 'I2C demux'
    longname = 'I2C demultiplexer'
    desc = 'Demux I2C packets into per-slave-address streams.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = [] # TODO: Only known at run-time.
    probes = []
    optional_probes = []
    options = {}
    annotations = []

    def __init__(self, **kwargs):
        self.packets = [] # Local cache of I2C packets
        self.slaves = [] # List of known slave addresses
        self.stream = -1 # Current output stream
        self.streamcount = 0 # Number of created output streams

    def start(self, metadata):
        self.out_proto = []

    def report(self):
        pass

    # Grab I2C packets into a local cache, until an I2C STOP condition
    # packet comes along. At some point before that STOP condition, there
    # will have been an ADDRESS READ or ADDRESS WRITE which contains the
    # I2C address of the slave that the master wants to talk to.
    # We use this slave address to figure out which output stream should
    # get the whole chunk of packets (from START to STOP).
    def decode(self, ss, es, data):

        cmd, databyte = data

        # Add the I2C packet to our local cache.
        self.packets.append([ss, es, data])

        if cmd in ('ADDRESS READ', 'ADDRESS WRITE'):
            if databyte in self.slaves:
                self.stream = self.slaves.index(databyte)
                return

            # We're never seen this slave, add a new stream.
            self.slaves.append(databyte)
            self.out_proto.append(self.add(srd.OUTPUT_PROTO,
                                  'i2c-%s' % hex(databyte)))
            self.stream = self.streamcount
            self.streamcount += 1
        elif cmd == 'STOP':
            if self.stream == -1:
                raise Exception('Invalid stream!') # FIXME?

            # Send the whole chunk of I2C packets to the correct stream.
            for p in self.packets:
                self.put(p[0], p[1], self.out_proto[self.stream], p[2])

            self.packets = []
            self.stream = -1
        else:
            pass # Do nothing, only add the I2C packet to our cache.

