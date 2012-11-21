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

# Epson RTC-8564 JE/NB protocol decoder

import sigrokdecode as srd

# Return the specified BCD number (max. 8 bits) as integer.
def bcd2int(b):
    return (b & 0x0f) + ((b >> 4) * 10)

class Decoder(srd.Decoder):
    api_version = 1
    id = 'rtc8564'
    name = 'RTC-8564'
    longname = 'Epson RTC-8564 JE/NB'
    desc = 'Realtime clock module protocol.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['rtc8564']
    probes = []
    optional_probes = [
        {'id': 'clkout', 'name': 'CLKOUT', 'desc': 'TODO.'},
        {'id': 'clkoe', 'name': 'CLKOE', 'desc': 'TODO.'},
        {'id': 'int', 'name': 'INT#', 'desc': 'TODO.'},
    ]
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
        self.months = -1
        self.years = -1

    def start(self, metadata):
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'rtc8564')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'rtc8564')

    def report(self):
        pass

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def handle_reg_0x00(self, b): # Control register 1
        pass

    def handle_reg_0x01(self, b): # Control register 2
        ti_tp = 1 if (b & (1 << 4)) else 0
        af = 1 if (b & (1 << 3)) else 0
        tf = 1 if (b & (1 << 2)) else 0
        aie = 1 if (b & (1 << 1)) else 0
        tie = 1 if (b & (1 << 0)) else 0

        ann = ''

        s = 'repeated' if ti_tp else 'single-shot'
        ann += 'TI/TP = %d: %s operation upon fixed-cycle timer interrupt '\
               'events\n' % (ti_tp, s)
        s = '' if af else 'no '
        ann += 'AF = %d: %salarm interrupt detected\n' % (af, s)
        s = '' if tf else 'no '
        ann += 'TF = %d: %sfixed-cycle timer interrupt detected\n' % (tf, s)
        s = 'enabled' if aie else 'prohibited'
        ann += 'AIE = %d: INT# pin output %s when an alarm interrupt '\
               'occurs\n' % (aie, s)
        s = 'enabled' if tie else 'prohibited'
        ann += 'TIE = %d: INT# pin output %s when a fixed-cycle interrupt '\
               'event occurs\n' % (tie, s)

        self.putx([0, [ann]])

    def handle_reg_0x02(self, b): # Seconds / Voltage-low flag
        self.seconds = bcd2int(b & 0x7f)
        self.putx([0, ['Seconds: %d' % self.seconds]])
        vl = 1 if (b & (1 << 7)) else 0
        self.putx([0, ['Voltage low (VL) bit: %d' % vl]])

    def handle_reg_0x03(self, b): # Minutes
        self.minutes = bcd2int(b & 0x7f)
        self.putx([0, ['Minutes: %d' % self.minutes]])

    def handle_reg_0x04(self, b): # Hours
        self.hours = bcd2int(b & 0x3f)
        self.putx([0, ['Hours: %d' % self.hours]])

    def handle_reg_0x05(self, b): # Days
        self.days = bcd2int(b & 0x3f)
        self.putx([0, ['Days: %d' % self.days]])

    def handle_reg_0x06(self, b): # Day counter
        pass

    def handle_reg_0x07(self, b): # Months / century
        # TODO: Handle century bit.
        self.months = bcd2int(b & 0x1f)
        self.putx([0, ['Months: %d' % self.months]])

    def handle_reg_0x08(self, b): # Years
        self.years = bcd2int(b & 0xff)
        self.putx([0, ['Years: %d' % self.years]])

    def handle_reg_0x09(self, b): # Alarm, minute
        pass

    def handle_reg_0x0a(self, b): # Alarm, hour
        pass

    def handle_reg_0x0b(self, b): # Alarm, day
        pass

    def handle_reg_0x0c(self, b): # Alarm, weekday
        pass

    def handle_reg_0x0d(self, b): # CLKOUT output
        pass

    def handle_reg_0x0e(self, b): # Timer setting
        pass

    def handle_reg_0x0f(self, b): # Down counter for fixed-cycle timer
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
            # TODO: We should only handle packets to the RTC slave (0xa2/0xa3).
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
                d = '%02d.%02d.%02d %02d:%02d:%02d' % (self.days, self.months,
                    self.years, self.hours, self.minutes, self.seconds)
                self.put(self.block_start_sample, es, self.out_ann,
                         [0, ['Written date/time: %s' % d]])
                self.state = 'IDLE'
            else:
                pass # TODO
        elif self.state == 'READ RTC REGS':
            # Wait for an address read operation.
            # TODO: We should only handle packets to the RTC slave (0xa2/0xa3).
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
                d = '%02d.%02d.%02d %02d:%02d:%02d' % (self.days, self.months,
                    self.years, self.hours, self.minutes, self.seconds)
                self.put(self.block_start_sample, es, self.out_ann,
                         [0, ['Read date/time: %s' % d]])
                self.state = 'IDLE'
            else:
                pass # TODO?
        else:
            raise Exception('Invalid state: %d' % self.state)

