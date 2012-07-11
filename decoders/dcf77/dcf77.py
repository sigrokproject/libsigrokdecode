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

# DCF77 protocol decoder

import sigrokdecode as srd
import calendar

# Return the specified BCD number (max. 8 bits) as integer.
def bcd2int(b):
    return (b & 0x0f) + ((b >> 4) * 10)

class Decoder(srd.Decoder):
    api_version = 1
    id = 'dcf77'
    name = 'DCF77'
    longname = 'DCF77 time protocol'
    desc = 'European longwave time signal (77.5kHz carrier signal).'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['dcf77']
    probes = [
        {'id': 'data', 'name': 'DATA', 'desc': 'DATA line'},
    ]
    optional_probes = [
        {'id': 'pon', 'name': 'PON', 'desc': 'Power on'},
    ]
    options = {}
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.state = 'WAIT FOR RISING EDGE'
        self.oldpins = None
        self.oldval = None
        self.oldpon = None
        self.samplenum = 0
        self.bit_start = 0
        self.bit_start_old = 0
        self.bitcount = 0 # Counter for the DCF77 bits (0..58)
        self.dcf77_bitnumber_is_known = 0

    def start(self, metadata):
        self.samplerate = metadata['samplerate']
        # self.out_proto = self.add(srd.OUTPUT_PROTO, 'dcf77')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'dcf77')

    def report(self):
        pass

    # TODO: Which range to use? Only the 100ms/200ms or full second?
    def handle_dcf77_bit(self, bit):
        c = self.bitcount
        a = self.out_ann
        ss = es = 0 # FIXME

        # Create one annotation for each DCF77 bit (containing the 0/1 value).
        # Use 'Unknown DCF77 bit x: val' if we're not sure yet which of the
        # 0..58 bits it is (because we haven't seen a 'new minute' marker yet).
        # Otherwise, use 'DCF77 bit x: val'.
        s = '' if self.dcf77_bitnumber_is_known else 'Unknown '
        self.put(ss, es, a, [0, ['%sDCF77 bit %d: %d' % (s, c, bit)]])

        # If we're not sure yet which of the 0..58 DCF77 bits we have, return.
        # We don't want to decode bogus data.
        if not self.dcf77_bitnumber_is_known:
            return

        # Output specific "decoded" annotations for the respective DCF77 bits.
        if c == 0:
            # Start of minute: DCF bit 0.
            if bit == 0:
                self.put(ss, es, a, [0, ['Start of minute (always 0)']])
            else:
                self.put(ss, es, a, [0, ['ERROR: Start of minute != 0']])
        elif c in range(1, 14 + 1):
            # Special bits (civil warnings, weather forecast): DCF77 bits 1-14.
            if c == 1:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 1))
            if c == 14:
                self.put(ss, es, a, [0, ['Special bits: %s' % bin(self.tmp)]])
        elif c == 15:
            s = '' if (bit == 1) else 'not '
            self.put(ss, es, a, [0, ['Call bit is %sset' % s]])
            # TODO: Previously this bit indicated use of the backup antenna.
        elif c == 16:
            s = '' if (bit == 1) else 'not '
            self.put(ss, es, a, [0, ['Summer time announcement %sactive' % s]])
        elif c == 17:
            s = '' if (bit == 1) else 'not '
            self.put(ss, es, a, [0, ['CEST is %sin effect' % s]])
        elif c == 18:
            s = '' if (bit == 1) else 'not '
            self.put(ss, es, a, [0, ['CET is %sin effect' % s]])
        elif c == 19:
            s = '' if (bit == 1) else 'not '
            self.put(ss, es, a, [0, ['Leap second announcement %sactive' % s]])
        elif c == 20:
            # Start of encoded time: DCF bit 20.
            if bit == 1:
                self.put(ss, es, a, [0, ['Start of encoded time (always 1)']])
            else:
                self.put(ss, es, a,
                         [0, ['ERROR: Start of encoded time != 1']])
        elif c in range(21, 27 + 1):
            # Minutes (0-59): DCF77 bits 21-27 (BCD format).
            if c == 21:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 21))
            if c == 27:
                self.put(ss, es, a, [0, ['Minutes: %d' % bcd2int(self.tmp)]])
        elif c == 28:
            # Even parity over minute bits (21-28): DCF77 bit 28.
            self.tmp |= (bit << (c - 21))
            parity = bin(self.tmp).count('1')
            s = 'OK' if ((parity % 2) == 0) else 'INVALID!'
            self.put(ss, es, a, [0, ['Minute parity: %s' % s]])
        elif c in range(29, 34 + 1):
            # Hours (0-23): DCF77 bits 29-34 (BCD format).
            if c == 29:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 29))
            if c == 34:
                self.put(ss, es, a, [0, ['Hours: %d' % bcd2int(self.tmp)]])
        elif c == 35:
            # Even parity over hour bits (29-35): DCF77 bit 35.
            self.tmp |= (bit << (c - 29))
            parity = bin(self.tmp).count('1')
            s = 'OK' if ((parity % 2) == 0) else 'INVALID!'
            self.put(ss, es, a, [0, ['Hour parity: %s' % s]])
        elif c in range(36, 41 + 1):
            # Day of month (1-31): DCF77 bits 36-41 (BCD format).
            if c == 36:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 36))
            if c == 41:
                self.put(ss, es, a, [0, ['Day: %d' % bcd2int(self.tmp)]])
        elif c in range(42, 44 + 1):
            # Day of week (1-7): DCF77 bits 42-44 (BCD format).
            # A value of 1 means Monday, 7 means Sunday.
            if c == 42:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 42))
            if c == 44:
                d = bcd2int(self.tmp)
                dn = calendar.day_name[d - 1] # day_name[0] == Monday
                self.put(ss, es, a, [0, ['Day of week: %d (%s)' % (d, dn)]])
        elif c in range(45, 49 + 1):
            # Month (1-12): DCF77 bits 45-49 (BCD format).
            if c == 45:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 45))
            if c == 49:
                m = bcd2int(self.tmp)
                mn = calendar.month_name[m] # month_name[1] == January
                self.put(ss, es, a, [0, ['Month: %d (%s)' % (m, mn)]])
        elif c in range(50, 57 + 1):
            # Year (0-99): DCF77 bits 50-57 (BCD format).
            if c == 50:
                self.tmp = bit
            else:
                self.tmp |= (bit << (c - 50))
            if c == 57:
                self.put(ss, es, a, [0, ['Year: %d' % bcd2int(self.tmp)]])
        elif c == 58:
            # Even parity over date bits (36-58): DCF77 bit 58.
            self.tmp |= (bit << (c - 50))
            parity = bin(self.tmp).count('1')
            s = 'OK' if ((parity % 2) == 0) else 'INVALID!'
            self.put(ss, es, a, [0, ['Date parity: %s' % s]])
        else:
            raise Exception('Invalid DCF77 bit: %d' % c)

    def decode(self, ss, es, data):
        for (self.samplenum, pins) in data:

            # Ignore identical samples early on (for performance reasons).
            if self.oldpins == pins:
                continue
            self.oldpins, (val, pon) = pins, pins

            # Always remember the old PON state.
            if self.oldpon != pon:
                self.oldpon = pon

            # Warn if PON goes low.
            if self.oldpon == 1 and pon == 0:
                self.pon_ss = self.samplenum
                self.put(self.samplenum, self.samplenum, self.out_ann,
                         [1, ['Warning: PON goes low, DCF77 reception '
                         'no longer possible']])
            elif self.oldpon == 0 and pon == 1:
                self.put(self.samplenum, self.samplenum, self.out_ann,
                         [0, ['PON goes high, DCF77 reception now possible']])
                self.put(self.pon_ss, self.samplenum, self.out_ann,
                         [1, ['Warning: PON low, DCF77 reception disabled']])

            # Ignore samples where PON == 0, they can't contain DCF77 signals.
            if pon == 0:
                continue

            if self.state == 'WAIT FOR RISING EDGE':
                # Wait until the next rising edge occurs.
                if not (self.oldval == 0 and val == 1):
                    self.oldval = val
                    continue

                # Save the sample number where the DCF77 bit begins.
                self.bit_start = self.samplenum

                # Calculate the length (in ms) between two rising edges.
                len_edges = self.bit_start - self.bit_start_old
                len_edges_ms = int((len_edges / self.samplerate) * 1000)

                # The time between two rising edges is usually around 1000ms.
                # For DCF77 bit 59, there is no rising edge at all, i.e. the
                # time between DCF77 bit 59 and DCF77 bit 0 (of the next
                # minute) is around 2000ms. Thus, if we see an edge with a
                # 2000ms distance to the last one, this edge marks the
                # beginning of a new minute (and DCF77 bit 0 of that minute).
                if len_edges_ms in range(1600, 2400 + 1):
                    self.put(ss, es, self.out_ann, [0, ['New minute starts']])
                    self.bitcount = 0
                    self.bit_start_old = self.bit_start
                    self.dcf77_bitnumber_is_known = 1
                    # Don't switch to 'GET BIT' state this time.
                    continue

                self.bit_start_old = self.bit_start
                self.state = 'GET BIT'

            elif self.state == 'GET BIT':
                # Wait until the next falling edge occurs.
                if not (self.oldval == 1 and val == 0):
                    self.oldval = val
                    continue

                # Calculate the length (in ms) of the current high period.
                len_high = self.samplenum - self.bit_start
                len_high_ms = int((len_high / self.samplerate) * 1000)

                # If the high signal was 100ms long, that encodes a 0 bit.
                # If it was 200ms long, that encodes a 1 bit.
                if len_high_ms in range(40, 160 + 1):
                    bit = 0
                elif len_high_ms in range(161, 260 + 1):
                    bit = 1
                else:
                    bit = -1 # TODO: Error?

                # There's no bit 59, make sure none is decoded.
                if bit in (0, 1) and self.bitcount in range(0, 58 + 1):
                    self.handle_dcf77_bit(bit)
                    self.bitcount += 1

                self.state = 'WAIT FOR RISING EDGE'

            else:
                raise Exception('Invalid state: %d' % self.state)

            self.oldval = val

