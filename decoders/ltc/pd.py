##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2026 Simon Wood <simon@mungewell.org>
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


class SamplerateError(Exception):
    pass


class Decoder(srd.Decoder):
    api_version = 3
    id = "ltc"
    name = "LTC"
    longname = "Audio LTC"
    desc = "LinearTimeCode BiPhase Decoder"
    license = "gplv2+"
    inputs = ["logic"]
    outputs = []
    tags = ["Audio"]
    channels = ({"id": "data", "name": "Data", "desc": "Data line"},)
    options = ({"id": "fps", "desc": "Video Framerate", "default": 25.0},)
    annotations = (
        ("bit", "Bit"),
        ("nosync", "NoSync"),
        ("sync", "Sync"),
        ("timel", "TimeL"),
        ("userl", "UserL"),
        ("timeh", "TimeH"),
        ("drop", "Drop"),
        ("clock", "Clock"),
        ("flag", "Flag"),
        ("userh", "UserH"),
        ("frame", "Frame"),
    )
    annotation_rows = (
        ("bits", "Bits", (0,)),
        ("fields", "Fields", (1, 2, 3, 4, 5, 6, 7, 8, 9)),
        ("tag", "Frame", (10,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.bit_width = 0
        self.bit25pc = 0
        self.bit75pc = 0

        self.oldpl = 0
        self.oldsamplenum = 0
        self.cache = 0

        self.state = "NOSYNC"
        self.sync = 0
        self.data = 0
        self.payload_cnt = 0
        self.ss_first = 0
        self.es_last = 0
        self.ss_data = [0] * 16

        self.time = [0] * 8
        self.drop = 0

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
        self.bit_width = self.samplerate / (80 * self.options["fps"])
        self.bit25pc = self.bit_width / 4
        self.bit75pc = self.bit_width / 2 + self.bit_width / 4

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putbit(self, bit, ss, es):
        self.put(ss, es, self.out_ann, [0, [str(bit)]])

        if self.state == "SYNC" or self.state == "NOSYNC":
            if self.ss_first == 0:
                self.ss_first = ss
            if self.es_last == 0:
                self.es_last = ss

            # sync 'footer' is 16bit, shift register downwards
            self.sync = ((self.sync & 0xFFFF) >> 1) | (bit << 15)
            self.payload_cnt += 1

            if self.sync == 0xBFFC:
                if self.state == "NOSYNC" or self.payload_cnt > 16:
                    self.put(
                        self.ss_first,
                        es,
                        self.out_ann,
                        [1, ["NoSync", "None", "No", "N"]],
                    )
                else:
                    frame = format(
                        "%2.2d:%2.2d:%2.2d%s%2.2d"
                        % (
                            (self.time[7] * 10) + self.time[6],
                            (self.time[5] * 10) + self.time[4],
                            (self.time[3] * 10) + self.time[2],
                            ":" if self.drop == 0 else ";",
                            (self.time[1] * 10) + self.time[0],
                        )
                    )
                    self.put(
                        self.ss_first,
                        es,
                        self.out_ann,
                        [2, [": %s" % frame, "Sync", "Sy", "S"]],
                    )
                    self.put(self.es_last, es, self.out_ann, [10, ["%s" % frame]])

                self.es_last = es
                self.state = "PAYLOAD"
                self.payload_cnt = 0
                return

        if self.state == "PAYLOAD":
            # save ss boundaries for labels
            self.ss_data[self.payload_cnt % 16] = ss

            self.data = ((self.data & 0xFFFF) >> 1) | (bit << 15)

            if self.payload_cnt % 16 == 15:
                word = (self.payload_cnt - 1) >> 4

                self.time[word * 2] = self.data & 0xF
                self.put(
                    self.ss_data[0],
                    self.ss_data[4],
                    self.out_ann,
                    [3, [": %X" % (self.data & 0xF)]],
                )
                self.put(
                    self.ss_data[4],
                    self.ss_data[8],
                    self.out_ann,
                    [4, [": %X" % ((self.data >> 4) & 0xF)]],
                )

                if word == 1 or word == 2:
                    self.time[(word * 2) + 1] = (self.data >> 8) & 0x7
                    self.put(
                        self.ss_data[8],
                        self.ss_data[11],
                        self.out_ann,
                        [5, [": %X" % ((self.data >> 8) & 0x7)]],
                    )
                else:
                    self.time[(word * 2) + 1] = (self.data >> 8) & 0x3
                    self.put(
                        self.ss_data[8],
                        self.ss_data[10],
                        self.out_ann,
                        [5, [": %X" % ((self.data >> 8) & 0x3)]],
                    )
                    if word == 0:
                        self.drop = (self.data >> 10) & 0x1
                        self.put(
                            self.ss_data[10],
                            self.ss_data[11],
                            self.out_ann,
                            [6, [": %X" % ((self.data >> 10) & 0x1)]],
                        )
                    else:
                        self.put(
                            self.ss_data[10],
                            self.ss_data[11],
                            self.out_ann,
                            [7, [": %X" % ((self.data >> 10) & 0x1)]],
                        )

                self.put(
                    self.ss_data[11],
                    self.ss_data[12],
                    self.out_ann,
                    [8, [": %X" % ((self.data >> 11) & 0x1)]],
                )
                self.put(
                    self.ss_data[12],
                    es,
                    self.out_ann,
                    [9, [": %X" % ((self.data >> 12) & 0xF)]],
                )

            self.payload_cnt += 1
            if self.payload_cnt >= 64:
                self.state = "SYNC"
                self.payload_cnt = 0
                self.ss_first = 0

            # abort if input stops/glitches
            if (es - ss) > (2 * self.bit_width):
                self.state = "NOSYNC"
                self.payload_cnt = 0
                self.ss_first = 0
                self.es_last = 0

            return

    def biphase_decode(self, pl):
        if pl > self.bit75pc:
            self.putbit(0, self.oldsamplenum, self.samplenum)
            return True
        elif self.oldpl < self.bit75pc and self.oldpl > self.bit25pc:
            if self.cache:
                self.putbit(1, self.cache, self.samplenum)
            return True

        return False

    def decode(self):
        if not self.samplerate:
            raise SamplerateError("Cannot decode without samplerate.")

        # Initialize internal state from the very first sample.
        (pin,) = self.wait()
        self.oldpl = 0
        self.oldsamplenum = 0

        while True:
            # Ignore identical samples, only process edges.
            (pin,) = self.wait({0: "e"})

            # assumes clean data, ie no glitches
            pl = self.samplenum - self.oldsamplenum
            if self.biphase_decode(pl):
                self.oldpl = 0
                self.cache = self.samplenum
            else:
                self.oldpl = pl

            self.oldsamplenum = self.samplenum
