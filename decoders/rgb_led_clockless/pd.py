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

# Implementor's notes on the wire format:
# - World Semi vendor, (Adafruit copy of the) datasheet
#   https://cdn-shop.adafruit.com/datasheets/WS2812.pdf
# - reset pulse is 50us (or more) of low pin level
# - 24bits per WS281x item, 3x 8bits, MSB first, GRB sequence,
#   cascaded WS281x items, all "excess bits" are passed through
# - bit time starts with high period, continues with low period,
#   high to low periods' ratio determines bit value, datasheet
#   mentions 0.35us/0.8us for value 0, 0.7us/0.6us for value 1
#   (huge 150ns tolerances, un-even 0/1 value length, hmm)
# - experience suggests the timing "is variable", rough estimation
#   often is good enough, microcontroller firmware got away with
#   four quanta per bit time, or even with three quanta (30%/60%),
#   Adafruit learn article suggests 1.2us total and 0.4/0.8 or
#   0.8/0.4 high/low parts, four quanta are easier to handle when
#   the bit stream is sent via SPI to avoid MCU bit banging and its
#   inaccurate timing (when interrupts are used in the firmware)
# - RGBW datasheet (Adafruit copy) for SK6812
#   https://cdn-shop.adafruit.com/product-files/2757/p2757_SK6812RGBW_REV01.pdf
#   also 1.2us total, shared across 0.3/0.9 for 0, 0.6/0.6 for 1,
#   80us reset pulse, R8/G8/B8/W8 format per 32bits
# - WS2815, RGB LED, uses GRB wire format, 280us RESET pulse width
# - more vendors and models available and in popular use,
#   suggests "one third" or "two thirds" ratio would be most robust,
#   sample "a little before" the bit half? reset pulse width may need
#   to become an option? matrices and/or fast refresh environments
#   may want to experiment with back to back pixel streams

import sigrokdecode as srd
from common.srdhelper import bitpack_msb

class SamplerateError(Exception):
    pass

class DecoderError(Exception):
    pass

(
    ANN_BIT, ANN_RESET, ANN_RGB,
    ANN_COMP_R, ANN_COMP_G, ANN_COMP_B, ANN_COMP_W,
) = range(7)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'rgb_led_clockless'
    name = 'RGB LED (clockless)'
    longname = 'RGB LED string decoder (clockless)'
    desc = 'Decoder for RGB LED string clockless one-wire protocol (WS2812, WS2812B, APA104, SM16703, SK6812 ).'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = []
    tags = ['Display', 'Lighting']
    channels = (
        {'id': 'din', 'name': 'DIN', 'desc': 'DIN data line'},
    )
    annotations = (
        ('bit', 'Bit'),
        ('reset', 'RESET'),
        ('rgb', 'RGB'),
        ('r', 'R'),
        ('g', 'G'),
        ('b', 'B'),
        ('w', 'W'),
    )
    annotation_rows = (
        ('bits', 'Bits', (ANN_BIT, ANN_RESET,)),
        ('rgb-comps', 'RGB components', (ANN_COMP_R, ANN_COMP_G, ANN_COMP_B, ANN_COMP_W,)),
        ('rgb-vals', 'RGB values', (ANN_RGB,)),
    )
    options = (
        {'id': 'led_type', 'desc': 'LED Type',
         'default': 'WS281x',
        'values': ('WS281x', 'SK6812')},
        {'id': 'wireorder', 'desc': 'Color order (wire)',
         'default': 'GRB',
        'values': ('BGR', 'BRG', 'GBR', 'GRB', 'RBG', 'RGB')},
        {'id': 'is_rgbw', 'desc': 'Is this RGBW?',
         'default': 'False', 'values': ('True', 'False')},
        {'id': 'textorder', 'desc': 'Components output order (text)',
         'default': 'RGB[W]', 'values': ('wire', 'RGB[W]', 'RGB')},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.bits = []

    def preprocess_options(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        # Preprocess wire order
        wireorder = self.options['wireorder'].lower()

        # Determine if RGBW is selected
        is_rgbw = self.options['is_rgbw'].lower() == 'true'

        # Prepare wire format based on RGBW option
        self.wireformat = [c for c in wireorder if c in 'rgb']
        if is_rgbw:
            self.wireformat.append('w')

        # Calculate the number of bits needed based on the wire format
        self.need_bits = len(self.wireformat) * 8

        # Handle the output text format
        textorder = self.options['textorder'].lower()
        if textorder == 'wire':
            self.textformat = 'wire'
        elif textorder == 'rgb[w]':
            self.textformat = '#{r:02x}{g:02x}{b:02x}{wt:s}'
        else:
            # Default RGB format string
            self.textformat = '#{r:02x}{g:02x}{b:02x}'

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.preprocess_options()  # Preprocess options when the decoding starts

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putg(self, ss, es, cls, text):
        self.put(ss, es, self.out_ann, [cls, text])

    def handle_bits(self):
        if len(self.bits) < self.need_bits:
            return

        # Determine the start and end sample numbers for the packet
        ss_packet, es_packet = self.bits[0][1], self.bits[-1][2]

        # Initialize RGB and W component values
        r, g, b, w = 0, 0, 0, None
        comps = []

        # Extract and annotate each component based on wire format
        for i, c in enumerate(self.wireformat):
            first_idx, after_idx = 8 * i, 8 * i + 8
            comp_bits = self.bits[first_idx:after_idx]
            comp_ss, comp_es = comp_bits[0][1], comp_bits[-1][2]
            comp_value = bitpack_msb(comp_bits, 0)
            comp_text = '{:02x}'.format(comp_value)
            comp_ann = {
                'r': ANN_COMP_R, 'g': ANN_COMP_G,
                'b': ANN_COMP_B, 'w': ANN_COMP_W,
            }.get(c.lower(), None)
            comps.append((comp_ss, comp_es, comp_ann, comp_value, comp_text))

            if c.lower() == 'r':
                r = comp_value
            elif c.lower() == 'g':
                g = comp_value
            elif c.lower() == 'b':
                b = comp_value
            elif c.lower() == 'w':
                w = comp_value

        # Determine the wt (white component text) for formatting
        wt = '' if w is None else '{:02x}'.format(w)

        # Format the RGB text for annotation
        if self.textformat == 'wire':
            rgb_text = '#' + ''.join([c[-1] for c in comps])
        else:
            rgb_text = self.textformat.format(r=r, g=g, b=b, w=w, wt=wt)

        # Annotate each component and the RGB value
        for ss_comp, es_comp, cls_comp, _, text_comp in comps:
            self.putg(ss_comp, es_comp, cls_comp, [text_comp])

        if rgb_text:
            self.putg(ss_packet, es_packet, ANN_RGB, [rgb_text])

        # Clear the bits list after processing the packet
        self.bits.clear()

    def handle_bit(self, ss, es, value, ann_late=False):
        if not ann_late:
            text = ['{:d}'.format(value)]
            self.putg(ss, es, ANN_BIT, text)

        self.bits.append((value, ss, es))
        self.handle_bits()

        if ann_late:
            text = ['{:d}'.format(value)]
            self.putg(ss, es, ANN_BIT, text)

    def decode(self):
        led_type = self.options['led_type'].lower()
        # Constants for bit timing and reset detection
        if led_type == 'ws281x':
            DUTY_CYCLE_THRESHOLD = 0.5  # 50% threshold for distinguishing bit values
            RESET_CODE_TIMING = round(self.samplerate * 50e-6)
        elif led_type == 'sk6812':
            DUTY_CYCLE_THRESHOLD = 0.375  # 37.5% threshold for distinguishing bit values
            RESET_CODE_TIMING = round(self.samplerate * 80e-6)
        else:
            raise DecoderError('Unsupported LED Type')
        BIT_PERIOD = 1.25e-6  # 1.25 microseconds for WS281x and SK6812
        HALF_BIT_PERIOD = int(self.samplerate * (BIT_PERIOD / 2))

        # Conditions for bit and reset detection
        cond_bit_starts = {0: 'r'}
        cond_inbit_edge = {0: 'f'}
        cond_reset_pulse = {'skip': RESET_CODE_TIMING + 1}
        conds = [cond_bit_starts, cond_inbit_edge, cond_reset_pulse]

        ss_bit, inv_bit, es_bit = None, None, None
        pin, = self.wait({0: 'l'})
        inv_bit = self.samplenum
        check_reset = False

        while True:
            pin, = self.wait(conds)

            # Check for RESET condition
            if check_reset and self.matched[2]:
                es_bit = inv_bit
                ss_rst, es_rst = inv_bit, self.samplenum

                if ss_bit and inv_bit:
                    # Decode the last bit value
                    duty = inv_bit - ss_bit
                    period = self.samplerate * BIT_PERIOD
                    thres = period * DUTY_CYCLE_THRESHOLD
                    bit_value = 1 if duty >= thres else 0

                    # Extend the last bit's annotation to the expected end of the bit period
                    expected_es_bit = ss_bit + int(self.samplerate * BIT_PERIOD)
                    self.handle_bit(ss_bit, expected_es_bit, bit_value, True)

                    # Update the start and end of the reset to be after the bit period
                    ss_rst = expected_es_bit
                    es_rst = expected_es_bit + RESET_CODE_TIMING

                # Annotate RESET after the extended bit period
                if ss_rst and es_rst:
                    text = ['RESET', 'RST', 'R']
                    self.putg(ss_rst, es_rst, ANN_RESET, text)

                check_reset = False
                self.bits.clear()
                ss_bit, inv_bit, es_bit = None, None, None

            # Bit value detection logic
            if self.matched[0]:  # Rising edge starts a bit time
                check_reset = False
                if ss_bit and inv_bit:
                    es_bit = self.samplenum
                    period = es_bit - ss_bit
                    duty = inv_bit - ss_bit
                    bit_value = 1 if (duty / period) > DUTY_CYCLE_THRESHOLD else 0
                    self.handle_bit(ss_bit, es_bit, bit_value)
                ss_bit, inv_bit, es_bit = self.samplenum, None, None

            if self.matched[1]:  # Falling edge ends its high period
                check_reset = True
                inv_bit = self.samplenum

