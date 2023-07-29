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

class DecoderError(Exception):
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
        {'id': 'wireorder', 'desc': 'colour components order (wire)',
         'default': 'GRB',
         'values': ('BGR', 'BRG', 'GBR', 'GRB', 'RBG', 'RGB', 'RWBG', 'RGBW')},
        {'id': 'textorder', 'desc': 'components output order (text)',
         'default': 'RGB', 'values': ('wire', 'RGB[W]', 'RGB', 'RGBW', 'RGWB')},
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
        ss_packet, es_packet = self.bits[0][1], self.bits[-1][2]
        r, g, b, w = 0, 0, 0, None
        comps = []
        for i, c in enumerate(self.wireformat):
            first_idx, after_idx = 8 * i, 8 * i + 8
            comp_bits = self.bits[first_idx:after_idx]
            comp_ss, comp_es = comp_bits[0][1], comp_bits[-1][2]
            comp_value = bitpack_msb(comp_bits, 0)
            comp_item = (comp_ss, comp_es, comp_value)
            comps.append(comp_item)
            if c.lower() == 'r':
                r = comp_value
            elif c.lower() == 'g':
                g = comp_value
            elif c.lower() == 'b':
                b = comp_value
            elif c.lower() == 'w':
                w = comp_value
        wt = '' if w is None else '{:02x}'.format(w)
        if self.textformat == 'wire':
            rgb_text = ['{:02x}'.format(c[-1]) for c in comps]
            rgb_text = '#' + ''.join(rgb_text)
        else:
            rgb_text = self.textformat.format(r = r, g = g, b = b, w = w, wt = wt)
        if rgb_text:
            self.putg(ss_packet, es_packet, ANN_RGB, [rgb_text])
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

        # Preprocess options here, to simplify logic which executes
        # much later in loops while settings have the same values.
        wireorder = self.options['wireorder'].lower()
        self.wireformat = [c for c in wireorder if c in 'rgbw']
        self.need_bits = len(self.wireformat) * 8
        textorder = self.options['textorder'].lower()
        if textorder == 'wire':
            self.textformat = 'wire'
        elif textorder == 'rgb[w]':
            self.textformat = '#{r:02x}{g:02x}{b:02x}{wt:s}'
        else:
            self.textformat = {
                # "Obvious" permutations of R/G/B.
                'bgr': '#{b:02x}{g:02x}{r:02x}',
                'brg': '#{b:02x}{r:02x}{g:02x}',
                'gbr': '#{g:02x}{b:02x}{r:02x}',
                'grb': '#{g:02x}{r:02x}{b:02x}',
                'rbg': '#{r:02x}{b:02x}{g:02x}',
                'rgb': '#{r:02x}{g:02x}{b:02x}',
                # RGB plus White. Only one of them useful?
                'rgbw': '#{r:02x}{g:02x}{b:02x}{w:02x}',
                # Weird RGBW permutation for compatibility to test case.
                # Neither used RGBW nor the 'wire' order. Obsolete now?
                'rgwb': '#{r:02x}{g:02x}{w:02x}{b:02x}',
            }.get(textorder, None)
            if self.textformat is None:
                raise DecoderError('Unsupported text output format.')

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
