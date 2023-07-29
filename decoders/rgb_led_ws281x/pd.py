##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Vladimir Ermakov <vooon341@gmail.com>
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

import sigrokdecode as srd
from common.srdhelper import bitpack_msb

class SamplerateError(Exception):
    pass

( ANN_BIT, ANN_RESET, ANN_RGB, ) = range(3)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'rgb_led_ws281x'
    name = 'RGB LED (WS281x)'
    longname = 'RGB LED string decoder (WS281x)'
    desc = 'RGB LED string protocol (WS281x).'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = []
    tags = ['Display', 'IC']
    channels = (
        {'id': 'din', 'name': 'DIN', 'desc': 'DIN data line'},
    )
    annotations = (
        ('bit', 'Bit'),
        ('reset', 'RESET'),
        ('rgb', 'RGB'),
    )
    annotation_rows = (
        ('bits', 'Bits', (ANN_BIT, ANN_RESET,)),
        ('rgb-vals', 'RGB values', (ANN_RGB,)),
    )
    options = (
        {'id': 'type', 'desc': 'RGB or RGBW', 'default': 'RGB',
         'values': ('RGB', 'RGBW')},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.bits = []

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putg(self, ss, es, cls, text):
        self.put(ss, es, self.out_ann, [cls, text])

    def handle_bits(self):
        if len(self.bits) < self.need_bits:
            return
        grb = bitpack_msb(self.bits, 0)
        if self.options['type'] == 'RGB':
            rgb = (grb & 0xff0000) >> 8 | (grb & 0x00ff00) << 8 | (grb & 0x0000ff)
            text = '#{:06x}'.format(rgb)
        else:
            rgb = (grb & 0xff0000) >> 8 | (grb & 0x00ff00) << 8 | (grb & 0xff0000ff)
            text = '#{:08x}'.format(rgb)
        ss_packet, es_packet = self.bits[0][1], self.bits[-1][2]
        self.putg(ss_packet, es_packet, ANN_RGB, [text])
        self.bits.clear()

    def handle_bit(self, ss, es, value, ann_late = False):
        if not ann_late:
            text = ['{:d}'.format(value)]
            self.putg(ss, es, ANN_BIT, text)
        item = (value, ss, es)
        self.bits.append(item)
        self.handle_bits()
        if ann_late:
            text = ['{:d}'.format(value)]
            self.putg(ss, es, ANN_BIT, text)

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        self.need_bits = len(self.options['type']) * 8

        # Either check for edges which communicate bit values, or for
        # long periods of idle level which represent a reset pulse.
        # Track the left-most, right-most, and inner edge positions of
        # a bit. The positive period's width determines the bit's value.
        # Initially synchronize to the input stream by searching for a
        # low period, which preceeds a data bit or starts a reset pulse.
        # Don't annotate the very first reset pulse, but process it. We
        # may not see the right-most edge of a data bit when reset is
        # adjacent to that bit time.
        cond_bit_starts = {0: 'r'}
        cond_inbit_edge = {0: 'f'}
        samples_625ns = int(self.samplerate * 625e-9)
        samples_50us = round(self.samplerate * 50e-6)
        cond_reset_pulse = {'skip': samples_50us + 1}
        conds = [cond_bit_starts, cond_inbit_edge, cond_reset_pulse]
        ss_bit, inv_bit, es_bit = None, None, None
        pin, = self.wait({0: 'l'})
        inv_bit = self.samplenum
        check_reset = False
        while True:
            pin, = self.wait(conds)

            # Check RESET condition. Manufacturers may disagree on the
            # minimal pulse width. 50us are recommended in datasheets,
            # experiments suggest the limit is around 10us.
            # When the RESET pulse is adjacent to the low phase of the
            # last bit time, we have no appropriate condition for the
            # bit time's end location. That's why this BIT's annotation
            # is shorter (only spans the high phase), and the RESET
            # annotation immediately follows (spans from the falling edge
            # to the end of the minimum RESET pulse width).
            if check_reset and self.matched[2]:
                es_bit = inv_bit
                ss_rst, es_rst = inv_bit, self.samplenum

                if ss_bit and inv_bit and es_bit:
                    # Decode last bit value. Use the last processed bit's
                    # width for comparison when available. Fallback to an
                    # arbitrary threshold otherwise (which can result in
                    # false detection of value 1 for those captures where
                    # high and low pulses are of similar width).
                    duty = inv_bit - ss_bit
                    thres = samples_625ns
                    if self.bits:
                        period = self.bits[-1][2] - self.bits[-1][1]
                        thres = period * 0.5
                    bit_value = 1 if duty >= thres else 0
                    self.handle_bit(ss_bit, inv_bit, bit_value, True)

                if ss_rst and es_rst:
                    text = ['RESET', 'RST', 'R']
                    self.putg(ss_rst, es_rst, ANN_RESET, text)
                check_reset = False

                self.bits.clear()
                ss_bit, inv_bit, es_bit = None, None, None

            # Rising edge starts a bit time. Falling edge ends its high
            # period. Get the previous bit's duty cycle and thus its
            # bit value when the next bit starts.
            if self.matched[0]: # and pin:
                check_reset = False
                if ss_bit and inv_bit:
                    # Got a previous bit? Handle it.
                    es_bit = self.samplenum
                    period = es_bit - ss_bit
                    duty = inv_bit - ss_bit
                    # Ideal duty for T0H: 33%, T1H: 66%.
                    bit_value = 1 if (duty / period) > 0.5 else 0
                    self.handle_bit(ss_bit, es_bit, bit_value)
                ss_bit, inv_bit, es_bit = self.samplenum, None, None
            if self.matched[1]: # and not pin:
                check_reset = True
                inv_bit = self.samplenum
