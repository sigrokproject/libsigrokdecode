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

    # no optional channels
    optional_channels = (
    )

    # one channel has to be connected to the system.
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data'},
    )

    # decoded data
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
        self.startBitSamples = [0, 0]
        self.stopBitSamples = [0, 0]
        self.byteSamples = [0, 0]
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

    def handleBit(self, bit, BitStartSample, BitStopSample):
        ''' Decode one bit '''
        if self.state == Mode.SEARCHING:
            if bit == 1:
                self.startSync = BitStartSample
                self.state = Mode.SYNCHRONISATION
                self.numSyncBits = 1

        if self.state == Mode.SYNCHRONISATION:
            self.data = []
            self.borders = []

            if bit == 1:
                # synchronisation continues
                self.numSyncBits += 1
                self.stopSync = BitStopSample

            else:
                # synchronisation is over
                if self.numSyncBits >= 16:
                    self.putx(self.startSync, self.stopSync, [Ann.SYNC,
                              ['Synchronisation: %d Bits' % self.numSyncBits,
                               'Sync: %d' % self.numSyncBits]])
                    self.putp(self.startSync, self.stopSync,
                              ['Synchronisation',
                               {'length': self.numSyncBits}])

                    self.state = Mode.START
                    self.startBitSamples = (BitStartSample, BitStopSample)

                    self.startPackage = BitStartSample
                else:
                    self.state = Mode.SEARCHING
                    self.numSyncBits = 1

        elif self.state == Mode.START:
            self.putx(*self.startBitSamples, [Ann.START, ['Start']])
            self.putp(*self.startBitSamples, ['Start', None])
            self.state = Mode.BYTE
            self.byteSamples[0] = BitStartSample
            self.bits = [bit]

        elif self.state == Mode.STOP:
            self.putx(*self.stopBitSamples,
                      [Ann.STOP, ['Stop']])
            self.putp(*self.stopBitSamples, ['Stop', None])

            self.putp(self.startPackage, self.stopBitSamples[1], ['Package', {
                      'data': self.data, 'length': len(self.data),
                      'validity': self.validity, 'borders': self.borders}])

            self.state = Mode.SEARCHING
            if bit == 1:
                self.startSync = BitStartSample
                self.state = Mode.SYNCHRONISATION
                self.numSyncBits = 1

        elif self.state == Mode.BYTE:
            if len(self.bits) < 8:
                self.bits.append(bit)

                self.byteSamples[1] = BitStopSample

            elif bit == 0:
                self.state = Mode.START
                self.startBitSamples = (BitStartSample, BitStopSample)
                value = bitpack(self.bits)
                self.putx(*self.byteSamples, [Ann.BYTE, ['0x%02X' % (value)]])
                self.putp(*self.byteSamples, ['Byte', {'value': value}])

                self.data.append(value)
                self.borders.append(self.byteSamples)

            elif bit == 1:
                checksum = bitpack(self.bits)
                val = checksum
                # calculate checksum
                for byte in self.data:
                    val ^= byte

                validity = (val == 0)

                text = 'ok' if validity else 'invalid'
                self.putx(*self.byteSamples, [Ann.CHECKSUM,
                          ['Checksum %s: 0x%02X' % (text, checksum), text]])
                self.putp(*self.byteSamples, ['Checksum',
                          {'value': checksum, 'validity': validity}])

                self.validity = validity

                self.state = Mode.STOP
                self.stopBitSamples = (BitStartSample, BitStopSample)

    def decode(self):
        ''' main decoding function '''

        signalStartSample = 0
        lastSignalStopSample = 0
        lastSignalStartSample = 0
        lastBitStopSample = 0

        bit = None
        lastbit = None

        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            # wait for any edge
            self.wait({Pin.DATA: 'e'})

            time = (self.samplenum - signalStartSample) / self.samplerate

            valid = False
            if ontime_min <= time <= ontime_max:
                valid = True
                bit = 1

            elif offtime_min <= time <= offtime_max:
                valid = True
                bit = 0

            if valid:
                if lastbit == bit:
                    # two parts of bits have the same value
                    BitStartSample = lastSignalStartSample
                    BitStopSample = self.samplenum

                    if lastSignalStopSample == signalStartSample:
                        if lastBitStopSample <= BitStartSample:
                            self.putx(BitStartSample, BitStopSample,
                                      [Ann.BITS, [str(bit)]])
                            self.handleBit(bit, BitStartSample, BitStopSample)

                            lastBitStopSample = BitStopSample

                lastSignalStartSample = signalStartSample
                lastSignalStopSample = self.samplenum

            else:
                self.putx(signalStartSample, self.samplenum, [Ann.ERRORS, [
                    'invalid timing: %0.1fµs' % (time * 1e6), 'invalid']])

            signalStartSample = self.samplenum
            lastbit = bit
