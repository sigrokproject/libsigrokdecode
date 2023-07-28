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
        self.oldpin = None
        self.ss = None
        self.es = None
        self.bits = []
        self.inreset = False

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

        while True:
            # TODO: Come up with more appropriate self.wait() conditions.
            (pin,) = self.wait()

            if self.oldpin is None:
                self.oldpin = pin
                continue

            # Check RESET condition (manufacturer recommends 50 usec minimal,
            # but real minimum is ~10 usec).
            if not self.inreset and not pin and self.es is not None and \
                    self.ss is not None and \
                    (self.samplenum - self.es) / self.samplerate > 50e-6:

                # Decode last bit value.
                tH = (self.es - self.ss) / self.samplerate
                bit_ = True if tH >= 625e-9 else False

                self.handle_bit(self.ss, self.es, bit_, True)

                text = ['RESET', 'RST', 'R']
                self.putg(self.es, self.samplenum, ANN_RESET, text)

                self.inreset = True
                self.bits.clear()
                self.ss = None

            if not self.oldpin and pin:
                # Rising edge.
                if self.ss and self.es:
                    period = self.samplenum - self.ss
                    duty = self.es - self.ss
                    # Ideal duty for T0H: 33%, T1H: 66%.
                    bit_ = (duty / period) > 0.5
                    self.handle_bit(self.ss, self.samplenum, bit_)
                self.ss = self.samplenum

            elif self.oldpin and not pin:
                # Falling edge.
                self.inreset = False
                self.es = self.samplenum

            self.oldpin = pin
