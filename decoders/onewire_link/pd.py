##
## This file is part of the sigrok project.
##
## Copyright (C) 2012 Iztok Jeras <iztok.jeras@gmail.com>
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

# 1-Wire protocol decoder (link layer)

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire_link'
    name = '1-Wire link layer'
    longname = '1-Wire serial communication bus (link layer)'
    desc = 'Bidirectional, half-duplex, asynchronous serial bus.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['onewire_link']
    probes = [
        {'id': 'owr', 'name': 'OWR', 'desc': '1-Wire signal line'},
    ]
    optional_probes = [
        {'id': 'pwr', 'name': 'PWR', 'desc': '1-Wire power supply pin'},
    ]
    options = {
        'overdrive': ['Overdrive', 1],
        # Time options (specified in number of samplerate periods):
        'cnt_normal_bit': ['Normal mode sample bit time', 0],
        'cnt_normal_slot': ['Normal mode data slot time', 0],
        'cnt_normal_presence': ['Normal mode sample presence time', 0],
        'cnt_normal_reset': ['Normal mode reset time', 0],
        'cnt_overdrive_bit': ['Overdrive mode sample bit time', 0],
        'cnt_overdrive_slot': ['Overdrive mode data slot time', 0],
        'cnt_overdrive_presence': ['Overdrive mode sample presence time', 0],
        'cnt_overdrive_reset': ['Overdrive mode reset time', 0],
    }
    annotations = [
        ['Text', 'Human-readable text'],
        ['Warnings', 'Human-readable warnings'],
    ]

    def __init__(self, **kwargs):
        self.samplenum = 0
        self.state = 'WAIT FOR FALLING EDGE'
        self.present = 0
        self.bit = 0
        self.bit_cnt = 0
        self.command = 0
        self.overdrive = 0
        self.fall = 0
        self.rise = 0

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire_link')
        self.out_ann = self.add(srd.OUTPUT_ANN, 'onewire_link')

        self.samplerate = metadata['samplerate']

        # Check if samplerate is appropriate.
        if self.options['overdrive']:
            if self.samplerate < 2000000:
                self.put(0, 0, self.out_ann, [1,
                    ['ERROR: Sampling rate is too low. Must be above 2MHz ' +
                     'for proper overdrive mode decoding.']])
            elif self.samplerate < 5000000:
                self.put(0, 0, self.out_ann, [1,
                  ['WARNING: Sampling rate is suggested to be above 5MHz ' +
                   'for proper overdrive mode decoding.']])
        else:
            if self.samplerate < 400000:
                self.put(0, 0, self.out_ann, [1,
                    ['ERROR: Sampling rate is too low. Must be above ' +
                     '400kHz for proper normal mode decoding.']])
            elif (self.samplerate < 1000000):
                self.put(0, 0, self.out_ann, [1,
                    ['WARNING: Sampling rate is suggested to be above ' +
                     '1MHz for proper normal mode decoding.']])

        # The default 1-Wire time base is 30us. This is used to calculate
        # sampling times.
        samplerate = float(self.samplerate)
        if self.options['cnt_normal_bit']:
            self.cnt_normal_bit = self.options['cnt_normal_bit']
        else:
            self.cnt_normal_bit = int(samplerate * 0.000015) - 1 # 15ns
        if self.options['cnt_normal_slot']:
            self.cnt_normal_slot = self.options['cnt_normal_slot']
        else:
            self.cnt_normal_slot = int(samplerate * 0.000060) - 1 # 60ns
        if self.options['cnt_normal_presence']:
            self.cnt_normal_presence = self.options['cnt_normal_presence']
        else:
            self.cnt_normal_presence = int(samplerate * 0.000075) - 1 # 75ns
        if self.options['cnt_normal_reset']:
            self.cnt_normal_reset = self.options['cnt_normal_reset']
        else:
            self.cnt_normal_reset = int(samplerate * 0.000480) - 1 # 480ns
        if self.options['cnt_overdrive_bit']:
            self.cnt_overdrive_bit = self.options['cnt_overdrive_bit']
        else:
            self.cnt_overdrive_bit = int(samplerate * 0.000002) - 1 # 2ns
        if self.options['cnt_overdrive_slot']:
            self.cnt_overdrive_slot = self.options['cnt_overdrive_slot']
        else:
            self.cnt_overdrive_slot = int(samplerate * 0.0000073) - 1 # 6ns+1.3ns
        if self.options['cnt_overdrive_presence']:
            self.cnt_overdrive_presence = self.options['cnt_overdrive_presence']
        else:
            self.cnt_overdrive_presence = int(samplerate * 0.000010) - 1 # 10ns
        if self.options['cnt_overdrive_reset']:
            self.cnt_overdrive_reset = self.options['cnt_overdrive_reset']
        else:
            self.cnt_overdrive_reset = int(samplerate * 0.000048) - 1 # 48ns

        # Organize values into lists.
        self.cnt_bit = [self.cnt_normal_bit, self.cnt_overdrive_bit]
        self.cnt_presence = [self.cnt_normal_presence, self.cnt_overdrive_presence]
        self.cnt_reset = [self.cnt_normal_reset, self.cnt_overdrive_reset]
        self.cnt_slot = [self.cnt_normal_slot, self.cnt_overdrive_slot]

        # Check if sample times are in the allowed range.

        time_min = float(self.cnt_normal_bit) / self.samplerate
        time_max = float(self.cnt_normal_bit + 1) / self.samplerate
        if (time_min < 0.000005) or (time_max > 0.000015):
            self.put(0, 0, self.out_ann, [1,
                ['WARNING: The normal mode data sample time interval ' +
                 '(%2.1fus-%2.1fus) should be inside (5.0us, 15.0us).'
                 % (time_min * 1000000, time_max * 1000000)]])

        time_min = float(self.cnt_normal_presence) / self.samplerate
        time_max = float(self.cnt_normal_presence + 1) / self.samplerate
        if (time_min < 0.0000681) or (time_max > 0.000075):
            self.put(0, 0, self.out_ann, [1,
                ['WARNING: The normal mode presence sample time interval ' +
                 '(%2.1fus-%2.1fus) should be inside (68.1us, 75.0us).'
                 % (time_min * 1000000, time_max * 1000000)]])

        time_min = float(self.cnt_overdrive_bit) / self.samplerate
        time_max = float(self.cnt_overdrive_bit + 1) / self.samplerate
        if (time_min < 0.000001) or (time_max > 0.000002):
            self.put(0, 0, self.out_ann, [1,
                ['WARNING: The overdrive mode data sample time interval ' +
                 '(%2.1fus-%2.1fus) should be inside (1.0us, 2.0us).'
                 % (time_min * 1000000, time_max * 1000000)]])

        time_min = float(self.cnt_overdrive_presence) / self.samplerate
        time_max = float(self.cnt_overdrive_presence + 1) / self.samplerate
        if (time_min < 0.0000073) or (time_max > 0.000010):
            self.put(0, 0, self.out_ann, [1,
                ['WARNING: The overdrive mode presence sample time interval ' +
                 '(%2.1fus-%2.1fus) should be inside (7.3us, 10.0us).'
                 % (time_min*1000000, time_max*1000000)]])

    def report(self):
        pass

    def decode(self, ss, es, data):
        for (self.samplenum, (owr, pwr)) in data:
            # State machine.
            if self.state == 'WAIT FOR FALLING EDGE':
                # The start of a cycle is a falling edge.
                if owr != 0:
                    continue
                # Save the sample number for the falling edge.
                self.fall = self.samplenum
                # Go to waiting for sample time.
                self.state = 'WAIT FOR DATA SAMPLE'
            elif self.state == 'WAIT FOR DATA SAMPLE':
                # Sample data bit.
                t = self.samplenum - self.fall
                if t == self.cnt_bit[self.overdrive]:
                    self.bit = owr
                    self.state = 'WAIT FOR DATA SLOT END'
            elif self.state == 'WAIT FOR DATA SLOT END':
                # A data slot ends in a recovery period, otherwise, this is
                # probably a reset.
                t = self.samplenum - self.fall
                if t != self.cnt_slot[self.overdrive]:
                    continue

                if owr == 0:
                    # This seems to be a reset slot, wait for its end.
                    self.state = 'WAIT FOR RISING EDGE'
                    continue

                self.put(self.fall, self.samplenum, self.out_ann,
                         [0, ['Bit: %d' % self.bit]])
                self.put(self.fall, self.samplenum, self.out_proto,
                         ['BIT', self.bit])

                # Checking the first command to see if overdrive mode
                # should be entered.
                if self.bit_cnt <= 8:
                    self.command |= (self.bit << self.bit_cnt)
                elif self.bit_cnt == 8 and self.command in [0x3c, 0x69]:
                    self.put(self.fall, self.cnt_bit[self.overdrive],
                             self.out_ann, [0, ['Entering overdrive mode']])
                # Increment the bit counter.
                self.bit_cnt += 1
                # Wait for next slot.
                self.state = 'WAIT FOR FALLING EDGE'
            elif self.state == 'WAIT FOR RISING EDGE':
                # The end of a cycle is a rising edge.
                if owr != 1:
                    continue

                # Check if this was a reset cycle.
                t = self.samplenum - self.fall
                if t > self.cnt_normal_reset:
                    # Save the sample number for the falling edge.
                    self.rise = self.samplenum
                    self.state = 'WAIT FOR PRESENCE DETECT'
                    # Exit overdrive mode.
                    if self.overdrive:
                        self.put(self.fall, self.cnt_bit[self.overdrive],
                                 self.out_ann, [0, ['Exiting overdrive mode']])
                        self.overdrive = 0
                    # Clear command bit counter and data register.
                    self.bit_cnt = 0
                    self.command = 0
                elif (t > self.cnt_overdrive_reset) and self.overdrive:
                    # Save the sample number for the falling edge.
                    self.rise = self.samplenum
                    self.state = "WAIT FOR PRESENCE DETECT"
                # Otherwise this is assumed to be a data bit.
                else:
                    self.state = "WAIT FOR FALLING EDGE"
            elif self.state == 'WAIT FOR PRESENCE DETECT':
                # Sample presence status.
                t = self.samplenum - self.rise
                if t == self.cnt_presence[self.overdrive]:
                    self.present = owr
                    self.state = 'WAIT FOR RESET SLOT END'
            elif self.state == 'WAIT FOR RESET SLOT END':
                # A reset slot ends in a long recovery period.
                t = self.samplenum - self.rise
                if t != self.cnt_reset[self.overdrive]:
                    continue

                if owr == 0:
                    # This seems to be a reset slot, wait for its end.
                    self.state = 'WAIT FOR RISING EDGE'
                    continue

                self.put(self.fall, self.samplenum, self.out_ann,
                         [0, ['Reset/presence: %s'
                         % ('false' if self.present else 'true')]])
                self.put(self.fall, self.samplenum, self.out_proto,
                         ['RESET/PRESENCE', not self.present])
                # Wait for next slot.
                self.state = 'WAIT FOR FALLING EDGE'
            else:
                raise Exception('Invalid state: %s' % self.state)
