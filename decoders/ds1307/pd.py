##
## This file is part of the libsigrokdecode project.
## 
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
## Copyright (C) 2013 Matt Ranostay <mranostay@gmail.com>
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

# Dallas DS1307 RTC protocol decoder

import sigrokdecode as srd

days_of_week = [
    'Sunday',
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
]

# Return the specified BCD number (max. 8 bits) as integer.
def bcd2int(b):
    return (b & 0x0f) + ((b >> 4) * 10)

class Decoder(srd.Decoder):
    api_version = 1
    id = 'ds1307'
    name = 'DS1307'
    longname = 'Dallas DS1307'
    desc = 'Realtime clock module protocol.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['ds1307']
    probes = []
    optional_probes = []
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
    ]

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.hours = -1
        self.minutes = -1
        self.seconds = -1
        self.days = -1
        self.date = -1
        self.months = -1
        self.years = -1

    def start(self, metadata):
        self.out_ann = self.add(srd.OUTPUT_ANN, 'ds1307')

    def report(self):
        pass

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def handle_reg_0x00(self, b): # Seconds
        self.seconds = bcd2int(b & 0x7f)
        self.putx([0, ['Seconds: %d' % self.seconds]])

    def handle_reg_0x01(self, b): # Minutes
        self.minutes = bcd2int(b & 0x7f)
        self.putx([0, ['Minutes: %d' % self.minutes]])

    def handle_reg_0x02(self, b): # Hours
        self.hours = bcd2int(b & 0x3f)
        self.putx([0, ['Hours: %d' % self.hours]])

    def handle_reg_0x03(self, b): # Day of week
        self.days = bcd2int(b & 0x7)
        self.putx([0, ['Day of Week: %s' % days_of_week[self.days - 1]]])

    def handle_reg_0x04(self, b): # Date
        self.date =  bcd2int(b & 0x3f)
        self.putx([0, ['Days: %d' % self.date]])

    def handle_reg_0x05(self, b): # Month
        self.months = bcd2int(b & 0x1f)
        self.putx([0, ['Months: %d' % self.months]])

    def handle_reg_0x06(self, b): # Year
        self.years = bcd2int(b & 0xff) + 2000;
        self.putx([0, ['Years: %d' % self.years]])

    def handle_reg_0x07(self, b): # Control Register
        pass

    def decode(self, ss, es, data):
        cmd, databyte = data

        # Store the start/end samples of this I2C packet.
        self.ss, self.es = ss, es

        # State machine.
        if self.state == 'IDLE':
            # Wait for an I2C START condition.
            if cmd != 'START':
                return
            self.state = 'GET SLAVE ADDR'
            self.block_start_sample = ss
        elif self.state == 'GET SLAVE ADDR':
            # Wait for an address write operation.
            # TODO: We should only handle packets to the RTC slave (0x68).
            if cmd != 'ADDRESS WRITE':
                return
            self.state = 'GET REG ADDR'
        elif self.state == 'GET REG ADDR':
            # Wait for a data write (master selects the slave register).
            if cmd != 'DATA WRITE':
                return
            self.reg = databyte
            self.state = 'WRITE RTC REGS'
        elif self.state == 'WRITE RTC REGS':
            # If we see a Repeated Start here, it's probably an RTC read.
            if cmd == 'START REPEAT':
                self.state = 'READ RTC REGS'
                return
            # Otherwise: Get data bytes until a STOP condition occurs.
            if cmd == 'DATA WRITE':
                handle_reg = getattr(self, 'handle_reg_0x%02x' % self.reg)
                handle_reg(databyte)
                self.reg += 1
                # TODO: Check for NACK!
            elif cmd == 'STOP':
                # TODO: Handle read/write of only parts of these items.
                d = '%s, %02d.%02d.%02d %02d:%02d:%02d' % (
                    days_of_week[self.days - 1], self.date, self.months,
                    self.years, self.hours, self.minutes, self.seconds)
                self.put(self.block_start_sample, es, self.out_ann,
                         [0, ['Written date/time: %s' % d]])
                self.state = 'IDLE'
            else:
                pass # TODO
        elif self.state == 'READ RTC REGS':
            # Wait for an address read operation.
            # TODO: We should only handle packets to the RTC slave (0x68).
            if cmd == 'ADDRESS READ':
                self.state = 'READ RTC REGS2'
                return
            else:
                pass # TODO
        elif self.state == 'READ RTC REGS2':
            if cmd == 'DATA READ':
                handle_reg = getattr(self, 'handle_reg_0x%02x' % self.reg)
                handle_reg(databyte)
                self.reg += 1
                # TODO: Check for NACK!
            elif cmd == 'STOP':
                d = '%s, %02d.%02d.%02d %02d:%02d:%02d' % (
                    days_of_week[self.days - 1], self.date, self.months,
                    self.years, self.hours, self.minutes, self.seconds)
                self.put(self.block_start_sample, es, self.out_ann,
                         [0, ['Read date/time: %s' % d]])
                self.state = 'IDLE'
            else:
                pass # TODO?
        else:
            raise Exception('Invalid state: %s' % self.state)

