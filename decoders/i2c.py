##
## This file is part of the sigrok project.
##
## Copyright (C) 2010-2011 Uwe Hermann <uwe@hermann-uwe.de>
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
# I2C protocol decoder
#

#
# The Inter-Integrated Circuit (I2C) bus is a bidirectional, multi-master
# bus using two signals (SCL = serial clock line, SDA = serial data line).
#
# There can be many devices on the same bus. Each device can potentially be
# master or slave (and that can change during runtime). Both slave and master
# can potentially play the transmitter or receiver role (this can also
# change at runtime).
#
# Possible maximum data rates:
#  - Standard mode: 100 kbit/s
#  - Fast mode: 400 kbit/s
#  - Fast-mode Plus: 1 Mbit/s
#  - High-speed mode: 3.4 Mbit/s
#
# START condition (S): SDA = falling, SCL = high
# Repeated START condition (Sr): same as S
# Data bit sampling: SCL = rising
# STOP condition (P): SDA = rising, SCL = high
#
# All data bytes on SDA are exactly 8 bits long (transmitted MSB-first).
# Each byte has to be followed by a 9th ACK/NACK bit. If that bit is low,
# that indicates an ACK, if it's high that indicates a NACK.
#
# After the first START condition, a master sends the device address of the
# slave it wants to talk to. Slave addresses are 7 bits long (MSB-first).
# After those 7 bits, a data direction bit is sent. If the bit is low that
# indicates a WRITE operation, if it's high that indicates a READ operation.
#
# Later an optional 10bit slave addressing scheme was added.
#
# Documentation:
# http://www.nxp.com/acrobat/literature/9398/39340011.pdf (v2.1 spec)
# http://www.nxp.com/acrobat/usermanuals/UM10204_3.pdf (v3 spec)
# http://en.wikipedia.org/wiki/I2C
#

# TODO: Look into arbitration, collision detection, clock synchronisation, etc.
# TODO: Handle clock stretching.
# TODO: Handle combined messages / repeated START.
# TODO: Implement support for 7bit and 10bit slave addresses.
# TODO: Implement support for inverting SDA/SCL levels (0->1 and 1->0).
# TODO: Implement support for detecting various bus errors.

#
# I2C output format:
#
# The output consists of a (Python) list of I2C "packets", each of which
# has an (implicit) index number (its index in the list).
# Each packet consists of a Python dict with certain key/value pairs.
#
# TODO: Make this a list later instead of a dict?
#
# 'type': (string)
#   - 'S' (START condition)
#   - 'Sr' (Repeated START)
#   - 'AR' (Address, read)
#   - 'AW' (Address, write)
#   - 'DR' (Data, read)
#   - 'DW' (Data, write)
#   - 'P' (STOP condition)
# 'range': (tuple of 2 integers, the min/max samplenumber of this range)
#   - (min, max)
#   - min/max can also be identical.
# 'data': (actual data as integer ???) TODO: This can be very variable...
# 'ann': (string; additional annotations / comments)
#
# Example output:
# [{'type': 'S',  'range': (150, 160), 'data': None, 'ann': 'Foobar'},
#  {'type': 'AW', 'range': (200, 300), 'data': 0x50, 'ann': 'Slave 4'},
#  {'type': 'DW', 'range': (310, 370), 'data': 0x00, 'ann': 'Init cmd'},
#  {'type': 'AR', 'range': (500, 560), 'data': 0x50, 'ann': 'Get stat'},
#  {'type': 'DR', 'range': (580, 640), 'data': 0xfe, 'ann': 'OK'},
#  {'type': 'P',  'range': (650, 660), 'data': None, 'ann': None}]
#
# Possible other events:
#   - Error event in case protocol looks broken:
#     [{'type': 'ERROR', 'range': (min, max),
#      'data': TODO, 'ann': 'This is not a Microchip 24XX64 EEPROM'},
#     [{'type': 'ERROR', 'range': (min, max),
#      'data': TODO, 'ann': 'TODO'},
#   - TODO: Make list of possible errors accessible as metadata?
#
# TODO: I2C address of slaves.
# TODO: Handle multiple different I2C devices on same bus
#       -> we need to decode multiple protocols at the same time.
# TODO: range: Always contiguous? Splitted ranges? Multiple per event?
#

#
# I2C input format:
#
# signals:
# [[id, channel, description], ...] # TODO
#
# Example:
# {'id': 'SCL', 'ch': 5, 'desc': 'Serial clock line'}
# {'id': 'SDA', 'ch': 7, 'desc': 'Serial data line'}
# ...
#
# {'inbuf': [...],
#  'signals': [{'SCL': }]}
#

class Sample():
    def __init__(self, data):
        self.data = data
    def probe(self, probe):
        s = ord(self.data[probe / 8]) & (1 << (probe % 8))
        return True if s else False

def sampleiter(data, unitsize):
    for i in range(0, len(data), unitsize):
        yield(Sample(data[i:i+unitsize]))

class Decoder():
    name = 'I2C'
    longname = 'Inter-Integrated Circuit (I2C) bus'
    desc = 'I2C is a two-wire, multi-master, serial bus.'
    longdesc = '...'
    author = 'Uwe Hermann'
    email = 'uwe@hermann-uwe.de'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['i2c']
    probes = {
        'scl': {'ch': 0, 'name': 'SCL', 'desc': 'Serial clock line'},
        'sda': {'ch': 1, 'name': 'SDA', 'desc': 'Serial data line'},
    }
    options = {
        'address-space': ['Address space (in bits)', 7],
    }

    def __init__(self, **kwargs):
        self.probes = Decoder.probes.copy()

        # TODO: Don't hardcode the number of channels.
        self.channels = 8

        self.samplenum = 0
        self.bitcount = 0
        self.databyte = 0
        self.wr = -1
        self.startsample = -1
        self.is_repeat_start = 0

        self.FIND_START, self.FIND_ADDRESS, self.FIND_DATA = range(3)
        self.state = self.FIND_START

        # Get the channel/probe number of the SCL/SDA signals.
        self.scl_bit = self.probes['scl']['ch']
        self.sda_bit = self.probes['sda']['ch']

        self.oldscl = None
        self.oldsda = None

    def start(self, metadata):
        self.unitsize = metadata["unitsize"]

    def report(self):
        pass

    def is_start_condition(self, scl, sda):
        """START condition (S): SDA = falling, SCL = high"""
        if (self.oldsda == 1 and sda == 0) and scl == 1:
            return True
        return False

    def is_data_bit(self, scl, sda):
        """Data sampling of receiver: SCL = rising"""
        if self.oldscl == 0 and scl == 1:
            return True
        return False

    def is_stop_condition(self, scl, sda):
        """STOP condition (P): SDA = rising, SCL = high"""
        if (self.oldsda == 0 and sda == 1) and scl == 1:
            return True
        return False

    def find_start(self, scl, sda):
        out = []
        # o = {'type': 'S', 'range': (self.samplenum, self.samplenum),
        #      'data': None, 'ann': None},
        o = (self.is_repeat_start == 1) and 'Sr' or 'S'
        out.append(o)
        self.state = self.FIND_ADDRESS
        self.bitcount = self.databyte = 0
        self.is_repeat_start = 1
        self.wr = -1
        return out

    def find_address_or_data(self, scl, sda):
        """Gather 8 bits of data plus the ACK/NACK bit."""
        out = o = []

        if self.startsample == -1:
            self.startsample = self.samplenum
        self.bitcount += 1

        # Address and data are transmitted MSB-first.
        self.databyte <<= 1
        self.databyte |= sda

        # Return if we haven't collected all 8 + 1 bits, yet.
        if self.bitcount != 9:
            return []

        # We received 8 address/data bits and the ACK/NACK bit.
        self.databyte >>= 1 # Shift out unwanted ACK/NACK bit here.

        ack = (sda == 1) and 'N' or 'A'

        if self.state == self.FIND_ADDRESS:
            d = self.databyte & 0xfe
            # The READ/WRITE bit is only in address bytes, not data bytes.
            self.wr = (self.databyte & 1) and 1 or 0
        elif self.state == self.FIND_DATA:
            d = self.databyte
        else:
            # TODO: Error?
            pass

        # o = {'type': self.state,
        #      'range': (self.startsample, self.samplenum - 1),
        #      'data': d, 'ann': None}

        o = {'data': '0x%02x' % d}

        # TODO: Simplify.
        if self.state == self.FIND_ADDRESS and self.wr == 1:
            o['type'] = 'AW'
        elif self.state == self.FIND_ADDRESS and self.wr == 0:
            o['type'] = 'AR'
        elif self.state == self.FIND_DATA and self.wr == 1:
            o['type'] = 'DW'
        elif self.state == self.FIND_DATA and self.wr == 0:
            o['type'] = 'DR'

        out.append(o)

        # o = {'type': ack, 'range': (self.samplenum, self.samplenum),
        #      'data': None, 'ann': None}
        o = ack
        out.append(o)
        self.bitcount = self.databyte = 0
        self.startsample = -1

        if self.state == self.FIND_ADDRESS:
            self.state = self.FIND_DATA
        elif self.state == self.FIND_DATA:
            # There could be multiple data bytes in a row.
            # So, either find a STOP condition or another data byte next.
            pass

        return out

    def find_stop(self, scl, sda):
        out = o = []

        # o = {'type': 'P', 'range': (self.samplenum, self.samplenum),
        #      'data': None, 'ann': None},
        o = 'P'
        out.append(o)
        self.state = self.FIND_START
        self.is_repeat_start = 0
        self.wr = -1

        return out

    def decode(self, data):
        """I2C protocol decoder"""

        out = []
        o = ack = d = ''

        # We should accept a list of samples and iterate...
        for sample in sampleiter(data['data'], self.unitsize):

            # TODO: Eliminate the need for ord().
            s = ord(sample.data)

            # TODO: Start counting at 0 or 1?
            self.samplenum += 1

            # First sample: Save SCL/SDA value.
            if self.oldscl == None:
                # Get SCL/SDA bit values (0/1 for low/high) of the first sample.
                self.oldscl = (s & (1 << self.scl_bit)) >> self.scl_bit
                self.oldsda = (s & (1 << self.sda_bit)) >> self.sda_bit
                continue

            # Get SCL/SDA bit values (0/1 for low/high).
            scl = (s & (1 << self.scl_bit)) >> self.scl_bit
            sda = (s & (1 << self.sda_bit)) >> self.sda_bit

            # TODO: Wait until the bus is idle (SDA = SCL = 1) first?

            # State machine.
            if self.state == self.FIND_START:
                if self.is_start_condition(scl, sda):
                    out += self.find_start(scl, sda)
            elif self.state == self.FIND_ADDRESS:
                if self.is_data_bit(scl, sda):
                    out += self.find_address_or_data(scl, sda)
            elif self.state == self.FIND_DATA:
                if self.is_data_bit(scl, sda):
                    out += self.find_address_or_data(scl, sda)
                elif self.is_start_condition(scl, sda):
                    out += self.find_start(scl, sda)
                elif self.is_stop_condition(scl, sda):
                    out += self.find_stop(scl, sda)
            else:
                # TODO: Error?
                pass

            # Save current SDA/SCL values for the next round.
            self.oldscl = scl
            self.oldsda = sda

        if out != []:
            sigrok.put(out)

import sigrok

