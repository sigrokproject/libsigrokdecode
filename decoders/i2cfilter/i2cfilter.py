##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Bert Vermeulen <bert@biot.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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

# Generic I2C filtering protocol decoder

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'i2cfilter'
    name = 'I2C filter'
    longname = 'I2C filter'
    desc = 'Filter out specific addresses/directions in an I2C stream.'
    license = 'gplv3+'
    inputs = ['i2c']
    outputs = []
    options = {
        'address': ['Address to filter out of the I2C stream', 0],
        'direction': ['Direction to filter (read/write)', '']
    }

    def __init__(self, **kwargs):
        self.state = None

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'i2cdata')
        if self.options['direction'] not in ('', 'read', 'write'):
            raise Exception('Invalid direction: expected "read" or "write"')

    def report(self):
        pass

    def decode(self, ss, es, data):
        try:
            cmd, data = data
        except Exception as e:
            raise Exception('Malformed I2C input: %s' % str(e)) from e

        # Whichever state we're in, these always reset the state machine.
        # This should make it easier to deal with corrupt data etc.
        if cmd in ('START', 'START REPEAT'):
            self.state = 'start'
            return
        if cmd == 'STOP':
            self.state = None
            return
        if cmd in ('ACK', 'NACK'):
            # Don't care, we just want data.
            return

        if self.state == 'start':
            # Start of a transfer, see if we want this one.
            if cmd == 'ADDRESS READ' and self.options['direction'] == 'write':
                return
            elif cmd == 'ADDRESS WRITE' and self.options['direction'] == 'read':
                return
            elif cmd in ('ADDRESS READ', 'ADDRESS WRITE'):
                if self.options['address'] in (0, data):
                    # We want this tranfer.
                    self.state = 'transfer'
        elif self.state == 'transfer':
            if cmd in ('DATA READ', 'DATA WRITE'):
                self.put(ss, es, self.out_proto, data)
        else:
            raise Exception('Invalid state: %s' % self.state)

