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

# Define annotation constants for easy reference.
(
    ANN_BIT, ANN_RESET, ANN_RGB, ANN_W,
    ANN_COMP_R, ANN_COMP_G, ANN_COMP_B, ANN_COMP_W,
    ANN_BIT_DURATION, ANN_HIGH_PERIOD, ANN_LOW_PERIOD
) = range(11)

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
        ('w', 'W'),
        ('r', 'R'),
        ('g', 'G'),
        ('b', 'B'),
        ('w_comp', 'W'),
        ('bit_duration', 'Bit Duration'),
        ('high_period', 'High Period'),
        ('low_period', 'Low Period'),
    )
    annotation_rows = (
        ('bit-timing', 'Bit Timing', (ANN_HIGH_PERIOD, ANN_LOW_PERIOD,)),
        ('bits', 'Bits', (ANN_BIT, ANN_RESET,)),
        ('bit-duration', 'Bit Duration', (ANN_BIT_DURATION,)),
        ('rgb-comps', 'RGB components', (ANN_COMP_R, ANN_COMP_G, ANN_COMP_B, ANN_COMP_W,)),
        ('rgb-vals', 'RGB values', (ANN_RGB, ANN_W,)),
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
         'default': 'RGB[W]', 'values': ('wire', 'RGB[W]')},
        {'id': 'rgb_text_format', 'desc': 'RGB Text Format',
         'default': 'hex', 'values': ('hex', 'decimal')},
        {'id': 'w_text_format', 'desc': 'W Text Format',
         'default': 'hex', 'values': ('hex', 'decimal', 'percentage')},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset internal state for a new decoding session."""
        self.samplerate = None
        self.bits = []
        self.bit_start_sample = None
        self.inversion_point_sample = None
        self.bit_end_sample = None
        self.is_processing_bit = False
        self.is_looking_for_reset = False

    def preprocess_options(self):
        """Process user options and prepare internal settings based on them."""
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        # Get the wireorder, textorder, and determine if RGBW mode is used.
        wireorder = self.options['wireorder'].lower()
        self.is_rgbw = self.options['is_rgbw'].lower() == 'true'
        textorder = self.options['textorder'].lower()

        # Prepare wire format based on RGBW option
        self.wireformat = [c for c in wireorder if c in 'rgb']
        if self.is_rgbw:
            self.wireformat.append('w')

        # Calculate the number of bits needed based on the wire format
        self.need_bits = len(self.wireformat) * 8

        # Handle the output text format
        self.textformat = 'wire' if textorder == 'wire' else '#{r:02x}{g:02x}{b:02x}'

        # Determine settings based on the LED type.
        led_type = self.options['led_type'].lower()
        # Constants for bit timing and reset detection
        if led_type == 'ws281x':
            self.DUTY_CYCLE_THRESHOLD = 0.5  # 50% threshold for distinguishing bit values
            self.RESET_CODE_TIMING = round(self.samplerate * 50e-6)
        elif led_type == 'sk6812':
            self.DUTY_CYCLE_THRESHOLD = 0.375  # 37.5% threshold for distinguishing bit values
            self.RESET_CODE_TIMING = round(self.samplerate * 80e-6)
        else:
            raise DecoderError(f'Unsupported LED Type: {led_type}')
        self.BIT_PERIOD = 1.25e-6  # 1.25 microseconds for WS281x and SK681

    def start(self):
        """Initialize decoder output and prepare options."""
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.preprocess_options()  # Preprocess options when the decoding starts

    def metadata(self, key, value):
        """Receive and store metadata such as samplerate."""
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def putg(self, ss, es, cls, text):
        """Helper method to output annotated data."""
        self.put(ss, es, self.out_ann, [cls, text])

    def handle_bits(self):
        """Process and interpret collected bits into RGB(W) values."""
        if len(self.bits) < self.need_bits:
            return

        ss_rgb_packet, es_rgb_packet = self.bits[0][1], self.bits[-1][2]
        r, g, b, w = 0, 0, 0, None
        comps = []

        # Extract and annotate each component based on wire format
        for i, c in enumerate(self.wireformat):
            first_idx, after_idx = 8 * i, 8 * i + 8
            comp_bits = self.bits[first_idx:after_idx]
            comp_ss, comp_es = comp_bits[0][1], comp_bits[-1][2]
            comp_value = bitpack_msb(comp_bits, 0)
            comp_text = '{:02x}'.format(comp_value)

            # Annotation class selection for the component.
            comp_ann = {
                'r': ANN_COMP_R, 'g': ANN_COMP_G,
                'b': ANN_COMP_B, 'w': ANN_COMP_W,
            }.get(c.lower(), None)

            if comp_ann is not None:
                self.putg(comp_ss, comp_es, comp_ann, [comp_text])

            comps.append((comp_ss, comp_es, comp_ann, comp_value, comp_text))

            # Assign the value to the appropriate RGBW component.
            if c.lower() == 'r':
                r = comp_value
            elif c.lower() == 'g':
                g = comp_value
            elif c.lower() == 'b':
                b = comp_value
            elif c.lower() == 'w':
                w = comp_value

        # Format the RGB text for annotation
        if self.textformat == 'wire':
            rgb_text = '#' + ''.join([comp[4] for comp in comps])
            if rgb_text:
                self.putg(ss_rgb_packet, es_rgb_packet, ANN_RGB, [rgb_text])
        else:
            # Output the RGB part.
            ss_rgb_end = self.bits[23][2] if len(self.bits) >= 24 else es_rgb_packet
            ss_w_start = self.bits[24][1] if len(self.bits) > 24 else es_rgb_packet
            es_w_end = self.bits[-1][2]

            rgb_text_format = self.options['rgb_text_format']
            if rgb_text_format == 'hex':
                rgb_text = self.textformat.format(r=r, g=g, b=b)
            elif rgb_text_format == 'decimal':
                rgb_text = 'RGB({},{},{})'.format(r, g, b)

            if rgb_text:
                self.putg(ss_rgb_packet, ss_rgb_end, ANN_RGB, [rgb_text])

            # Output the W component if in RGBW mode.
            if self.is_rgbw and w is not None:
                w_text_format = self.options['w_text_format']
                if w_text_format == 'hex':
                    w_text = '{:02x}'.format(w)
                elif w_text_format == 'decimal':
                    w_text = str(w)
                elif w_text_format == 'percentage':
                    w_text = f'{w * 100 // 255}%'

                self.putg(ss_w_start, es_w_end, ANN_W, [w_text])

        # Clear the bits list after processing the packet
        self.bits.clear()

    def handle_bit(self, bit_start_sample, bit_end_sample, bit_value, ann_late=False):
        """Process a single bit and manage its annotations."""
        if not ann_late:
            self.putg(bit_start_sample, bit_end_sample, ANN_BIT, ['{:d}'.format(bit_value)])

        self.bits.append((bit_value, bit_start_sample, bit_end_sample))
        self.handle_bits()

        if ann_late:
            self.putg(bit_start_sample, bit_end_sample, ANN_BIT, ['{:d}'.format(bit_value)])

    def annotate_bit_timing(self, bit_start_sample, bit_end_sample, inversion_point_sample):
        """Calculate and annotate timing details for a bit."""
        bit_duration_us = self.convert_samples_to_time(bit_end_sample - bit_start_sample, 'us')
        high_period_us = self.convert_samples_to_time(inversion_point_sample - bit_start_sample, 'us')
        low_period_us = self.convert_samples_to_time(bit_end_sample - inversion_point_sample, 'us')

        self.putg(bit_start_sample, bit_end_sample, ANN_BIT_DURATION, [f'{bit_duration_us:.2f} µs'])
        self.putg(bit_start_sample, inversion_point_sample, ANN_HIGH_PERIOD, [f'{high_period_us:.2f} µs'])
        self.putg(inversion_point_sample, bit_end_sample, ANN_LOW_PERIOD, [f'{low_period_us:.2f} µs'])

    def process_bit(self, bit_start_sample, bit_end_sample, inversion_point_sample):
        """Process a bit and update annotations."""
        period = bit_end_sample - bit_start_sample
        high_time = inversion_point_sample - bit_start_sample
        bit_value = 1 if (high_time / period) > self.DUTY_CYCLE_THRESHOLD else 0

        self.handle_bit(bit_start_sample, bit_end_sample, bit_value)
        self.annotate_bit_timing(bit_start_sample, bit_end_sample, inversion_point_sample)

    def decode(self):
        """Main decoding loop to interpret the input signal."""

        cond_bit_starts = {0: 'r'}
        cond_inbit_edge = {0: 'f'}
        cond_reset_pulse = {'skip': self.RESET_CODE_TIMING + 1}
        conds = [cond_bit_starts, cond_inbit_edge, cond_reset_pulse]

        self.bit_start_sample, self.inversion_point_sample, self.bit_end_sample = None, None, None
        pin, = self.wait({0: 'l'})
        self.inversion_point_sample = self.samplenum
        self.is_processing_bit = False
        self.is_looking_for_reset = False

        while True:
            pin, = self.wait(conds)

            if self.is_looking_for_reset and self.matched[2]:
                self.bit_end_sample = self.inversion_point_sample
                reset_start_sample, reset_end_sample = self.inversion_point_sample, self.samplenum

                if self.bit_start_sample and self.inversion_point_sample:
                    # Extend the last bit's annotation to the expected end of the bit period
                    expected_bit_end_sample = self.bit_start_sample + int(self.samplerate * self.BIT_PERIOD)
                    self.process_bit(self.bit_start_sample, expected_bit_end_sample, self.inversion_point_sample)

                    # Update the start and end of the reset to be after the bit period
                    reset_start_sample = expected_bit_end_sample
                    reset_end_sample = expected_bit_end_sample + self.RESET_CODE_TIMING

                # Annotate RESET after the extended bit period
                if reset_start_sample and reset_end_sample:
                    self.putg(reset_start_sample, reset_end_sample, ANN_RESET, ['RESET', 'RST', 'R'])

                self.is_looking_for_reset = False
                self.bits.clear()
                self.bit_start_sample, self.inversion_point_sample, self.bit_end_sample = None, None, None

            # Bit value detection logic
            if self.matched[0]:  # Rising edge indicates the start of a bit
                self.is_processing_bit = True
                self.is_looking_for_reset = False

                if self.bit_start_sample and self.inversion_point_sample:
                    self.bit_end_sample = self.samplenum
                    self.process_bit(self.bit_start_sample, self.bit_end_sample, self.inversion_point_sample)

                self.bit_start_sample, self.inversion_point_sample, self.bit_end_sample = self.samplenum, None, None

            if self.matched[1]:  # Falling edge indicates the end of high period in bit
                self.is_looking_for_reset = True
                self.is_processing_bit = False
                self.inversion_point_sample = self.samplenum

    def convert_samples_to_time(self, samples, unit='us'):
        """Convert sample counts to time units based on the current samplerate."""
        factor = 1e6 if unit == 'us' else 1e3
        return (samples / self.samplerate) * factor

