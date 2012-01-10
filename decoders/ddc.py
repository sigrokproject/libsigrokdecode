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
## along with this program; if not, If not, see <http://www.gnu.org/licenses/>.
##

#
# DDC protocol decoder
#
# This decoder extracts a DDC stream from an I2C session between a computer
# and a display device. The stream is output as plain bytes.
#

import sigrokdecode


class Decoder(sigrokdecode.Decoder):
    id = 'ddc'
    name = 'DDC'
    longname = 'Display Data Channel'
    desc = 'DDC is a protocol for communication between computers and displays.'
    longdesc = ''
    author = 'Bert Vermeulen <bert@biot.com>'
    license = 'gplv3+'
    inputs = ['i2c']
    outputs = ['ddc']
    annotation = [
        ["Byte stream", "DDC byte stream as read from display."],
    ]

    def __init__(self, **kwargs):
        self.state = None

    def start(self, metadata):
        self.out_ann = self.add(sigrokdecode.SRD_OUTPUT_ANN, 'ddc')

    def decode(self, start_sample, end_sample, i2c_data):
        try:
            cmd, data, ack_bit = i2c_data
        except Exception as e:
            raise Exception("malformed I2C input: %s" % str(e)) from e

        if self.state is None:
            # waiting for the DDC session to start
            if cmd in ('START', 'START_REPEAT'):
                self.state = 'start'
        elif self.state == 'start':
            if cmd == 'ADDRESS_READ' and data == 80:
                # 80 is the I2C slave address of a connected display,
                # so this marks the start of the DDC data transfer.
                self.state = 'transfer'
            elif cmd == 'STOP':
                # back to idle
                self.state = None
        elif self.state == 'transfer':
            if cmd == 'DATA_READ':
                # there shouldn't be anything but data reads on this
                # address, so ignore everything else
                self.put(start_sample, end_sample, self.out_ann,
                         [0, ["0x%.2x" % data]])

