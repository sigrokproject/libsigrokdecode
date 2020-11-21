##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Benedikt Otto <benedikt_o@web.de>
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
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from common.srdhelper import bitpack

# time limits in seconds
ontime_min, ontime_max = 52e-6, 64e-6
offtime_min, offtime_max = 90e-6, 10000e-6

class SamplerateError(Exception):
    pass

class Pin:
    DATA, = range(1)

class Ann:
    ERRORS, BITS, SYNC, START, STOP, BYTE, CHECKSUM = range(7)

class Mode:
    SEARCHING, SYNCHRONISATION, START, BYTE, STOP = range(5)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'dcc'
    name = 'DCC'
    longname = 'Digital Command Control'
    desc = 'Digital Command Control'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['dcc']
    tags = ['Train']

    options = (
    )
    optional_channels = (
    )
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data'},
    )
    annotations = (
        ('timing error', 'Timing Error'),
        ('bit', 'Bit'),
        ('synchronisation', 'Synchronisation'),
        ('start', 'Start'),
        ('stop', 'Stop'),
        ('byte', 'Byte'),
        ('checksum', 'Checksum'),
    )
    annotation_rows = (
        ('errors', 'Errors', (Ann.ERRORS, )),
        ('bits', 'Bits', (Ann.BITS, )),
        ('addr-data', 'Address/Data',
            (Ann.SYNC, Ann.START, Ann.STOP, Ann.BYTE, Ann.CHECKSUM, )),
    )

    def __init__(self):
        ''' Initialize the object '''
        self.reset()

    def reset(self):
        ''' Reset the object '''
        self.state = Mode.SEARCHING
        self.start_bit_es = 0
        self.start_bit_ss = 0
        self.stop_bit_es = 0
        self.stop_bit_ss = 0
        self.byte_ss = 0
        self.byte_es = 0
        self.validity = False

    def start(self):
        ''' Register output methods '''
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, ss, es, data):
        # Helper for annotations which span exactly one sample.
        self.put(ss, es, self.out_ann, data)

    def putp(self, ss, es, data):
        # Helper for python output.
        self.put(ss, es, self.out_python, data)

    def metadata(self, key, value):
        ''' Receive metadata (samplerate) '''
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def handle_bit(self, bit, bit_ss, bit_es):
        ''' Decode one bit '''
        if self.state == Mode.SEARCHING:
            if bit == 1:
                self.start_sync = bit_ss
                self.state = Mode.SYNCHRONISATION
                self.num_sync_bits = 1

        if self.state == Mode.SYNCHRONISATION:
            self.data = []
            self.borders = []

            if bit == 1:
                # synchronisation continues
                self.num_sync_bits += 1
                self.stop_sync = bit_es

            else:
                # synchronisation is over
                if self.num_sync_bits >= 16:
                    self.putx(self.start_sync, self.stop_sync, [Ann.SYNC,
                              ['Synchronisation: %d Bits' % self.num_sync_bits,
                               'Sync: %d' % self.num_sync_bits, 'Sync']])
                    self.putp(self.start_sync, self.stop_sync,
                              ['Synchronisation',
                               {'length': self.num_sync_bits}])

                    self.state = Mode.START
                    self.start_bit_ss = bit_ss
                    self.start_bit_es = bit_es
                    self.package_ss = bit_ss
                else:
                    self.state = Mode.SEARCHING
                    self.num_sync_bits = 1

        elif self.state == Mode.START:
            self.putx(self.start_bit_ss, self.start_bit_es,
                      [Ann.START, ['Start']])
            self.putp(self.start_bit_ss, self.start_bit_es, ['Start', None])
            self.state = Mode.BYTE
            self.byte_ss = bit_ss
            self.bits = [bit]

        elif self.state == Mode.STOP:
            self.putx(self.stop_bit_ss, self.stop_bit_es,
                      [Ann.STOP, ['Stop']])
            self.putp(self.stop_bit_ss, self.stop_bit_es, ['Stop', None])

            self.putp(self.package_ss, self.start_bit_ss, ['Package', {
                      'data': self.data, 'length': len(self.data),
                      'validity': self.validity, 'borders': self.borders}])

            self.state = Mode.SEARCHING
            if bit == 1:
                self.start_sync = bit_ss
                self.state = Mode.SYNCHRONISATION
                self.num_sync_bits = 1

        elif self.state == Mode.BYTE:
            if len(self.bits) < 8:
                self.bits.append(bit)
                self.byte_es = bit_es

            elif bit == 0:
                self.state = Mode.START
                self.start_bit_ss = bit_ss
                self.start_bit_es = bit_es
                value = bitpack(self.bits)
                self.putx(self.byte_ss, self.byte_es,
                          [Ann.BYTE, ['%02x' % (value)]])
                self.putp(self.byte_ss, self.byte_es,
                          ['Byte', {'value': value}])
                self.data.append(value)
                self.borders.append((self.byte_ss, self.byte_es))

            elif bit == 1:
                checksum = bitpack(self.bits)
                val = checksum
                # calculate checksum
                for byte in self.data:
                    val ^= byte

                validity = (val == 0)
                text = 'ok' if validity else 'invalid'
                self.putx(self.byte_ss, self.byte_es, [Ann.CHECKSUM,
                          ['Checksum %s: %02x' % (text, checksum),
                           '%s: %02x' % (text, checksum), text]])
                self.putp(self.byte_ss, self.byte_es, ['Checksum',
                          {'value': checksum, 'validity': validity}])
                self.validity = validity
                self.state = Mode.STOP
                self.stop_bit_ss = bit_ss
                self.stop_bit_es = bit_es

    def decode(self):
        ''' main decoding function '''

        signal_ss = 0
        last_signal_ss = 0
        last_signal_es = 0
        last_bit_es = 0

        bit = None
        lastbit = None
        transition_seen = False

        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            # wait for any edge
            self.wait({Pin.DATA: 'e'})

            time = (self.samplenum - signal_ss) / self.samplerate

            valid = False
            if ontime_min <= time <= ontime_max:
                valid = True
                bit = 1

            elif offtime_min <= time <= offtime_max:
                valid = True
                bit = 0

            if valid:
                if lastbit == bit:
                    # two parts of one bit have the same value
                    bit_ss = last_signal_ss
                    bit_es = self.samplenum

                    if last_signal_es == signal_ss:
                        if last_bit_es <= bit_ss:
                            if transition_seen:
                                self.putx(bit_ss, bit_es,
                                          [Ann.BITS, [str(bit)]])
                                self.handle_bit(bit, bit_ss, bit_es)
                            last_bit_es = bit_es

                elif lastbit is not None:
                    transition_seen = True
                last_signal_ss = signal_ss
                last_signal_es = self.samplenum

            elif transition_seen:
                self.putx(signal_ss, self.samplenum, [Ann.ERRORS, [
                          'invalid timing: %0.1fµs' % (time * 1e6),
                          'invalid timing', 'invalid']])

            signal_ss = self.samplenum
            lastbit = bit
