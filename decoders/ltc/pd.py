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
    options = (
        {"id": "fps", "desc": "Video Framerate", "default": 25.0},
        {'id': "hfr", "desc": "High Framerate mode", "default": "Off",
            "values": ("Off", "Wide_LTC", "Frame_Pair")},
    )
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
        self.fps = None
        self.samplerate = None
        self.bit_width = 0
        self.bit25pc = 0
        self.bit75pc = 0

        self.oldpl = 0
        self.oldsamplenum = 0
        self.cache = 0

        self.state = "NOSYNC"
        self.forward = True
        self.sync = 0
        self.data = 0
        self.payload_cnt = 0
        self.ss_first = 0
        self.ss_frame = 0
        self.ss_data = [0] * 16

        self.time = [0] * 8
        self.drop = 0
        self.polarity = 0
        self.bgf1_flag = 0

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
        self.fps = self.options["fps"]
        self.bit_width = self.samplerate / (80 * self.fps)
        self.bit25pc = self.bit_width / 4
        self.bit75pc = self.bit_width / 2 + self.bit_width / 4

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putbit(self, bit, ss, es):
        self.put(ss, es, self.out_ann, [0, [str(bit)]])

        if self.state == "SYNC" or self.state == "NOSYNC":
            if self.ss_first == 0:
                self.ss_first = ss
            if self.ss_frame == 0:
                self.ss_frame = ss

            # sync 'footer' is 16bit, shift register downwards
            self.sync = ((self.sync & 0xFFFF) >> 1) | (bit << 15)
            self.payload_cnt += 1

            if self.state == "NOSYNC":
                self.ss_frame = es

            if self.sync == 0xBFFC or self.sync == 0x3FFD:
                if self.state == "NOSYNC" or self.payload_cnt > 16:
                    self.put(
                        self.ss_first,
                        es,
                        self.out_ann,
                        [1, ["NoSync", "None", "No", "N"]],
                    )
                else:
                    ff = (self.time[1] * 10) + self.time[0]
                    if self.options["hfr"] == "Wide_LTC":
                        if self.bgf1_flag:
                            ff += 40
                    elif self.options["hfr"] == "Frame_Pair":
                        ff = (ff * 2) + self.polarity

                    frame = format(
                        "%2.2d:%2.2d:%2.2d%s%2.2d"
                        % (
                            (self.time[7] * 10) + self.time[6],
                            (self.time[5] * 10) + self.time[4],
                            (self.time[3] * 10) + self.time[2],
                            ":" if self.drop == 0 else ";",
                            ff,
                        )
                    )

                    if self.sync == 0xBFFC:
                        self.forward = True
                        self.put(
                            self.ss_first,
                            es,
                            self.out_ann,
                            [2, [": %s" % "Sync", "Sy", "S"]],
                        )
                        self.put(
                            self.ss_frame,
                            es,
                            self.out_ann,
                            [10, ["%s" % frame]],
                        )
                        self.ss_frame = es
                    else:
                        self.forward = False
                        self.put(
                            self.ss_first,
                            es,
                            self.out_ann,
                            [2, [": %s" % "Cnys", "Cn", "C"]],
                        )
                        self.put(
                            self.ss_frame,
                            self.ss_first,
                            self.out_ann,
                            [10, ["%s" % frame]],
                        )
                        self.ss_frame = self.ss_first

                self.state = "PAYLOAD"
                self.payload_cnt = 0
                return

        if self.state == "PAYLOAD":
            # save ss boundaries for labels
            self.ss_data[self.payload_cnt % 16] = ss

            if self.forward:
                self.data = ((self.data & 0xFFFF) >> 1) | (bit << 15)
            else:
                self.data = ((self.data & 0x7FFF) << 1) | bit

            if self.payload_cnt % 16 == 15:
                word = (self.payload_cnt - 1) >> 4
                if not self.forward:
                    word = word ^ 0x03

                self.time[word * 2] = self.data & 0xF
                self.put(
                    self.ss_data[0] if self.forward else self.ss_data[12],
                    self.ss_data[4] if self.forward else es,
                    self.out_ann,
                    [3, [": %X" % (self.data & 0xF)]],
                )
                self.put(
                    self.ss_data[4] if self.forward else self.ss_data[8],
                    self.ss_data[8] if self.forward else self.ss_data[12],
                    self.out_ann,
                    [4, [": %X" % ((self.data >> 4) & 0xF)]],
                )

                if word == 1 or word == 2:
                    self.time[(word * 2) + 1] = (self.data >> 8) & 0x7
                    self.put(
                        self.ss_data[8] if self.forward else self.ss_data[5],
                        self.ss_data[11] if self.forward else self.ss_data[8],
                        self.out_ann,
                        [5, [": %X" % ((self.data >> 8) & 0x7)]],
                    )
                else:
                    self.time[(word * 2) + 1] = (self.data >> 8) & 0x3
                    self.put(
                        self.ss_data[8] if self.forward else self.ss_data[6],
                        self.ss_data[10] if self.forward else self.ss_data[8],
                        self.out_ann,
                        [5, [": %X" % ((self.data >> 8) & 0x3)]],
                    )
                    if word == 0:
                        self.drop = (self.data >> 10) & 0x1
                        self.put(
                            self.ss_data[10] if self.forward else self.ss_data[5],
                            self.ss_data[11] if self.forward else self.ss_data[6],
                            self.out_ann,
                            [6, [": %X" % ((self.data >> 10) & 0x1)]],
                        )
                    else:
                        self.put(
                            self.ss_data[10] if self.forward else self.ss_data[5],
                            self.ss_data[11] if self.forward else self.ss_data[6],
                            self.out_ann,
                            [7, [": %X" % ((self.data >> 10) & 0x1)]],
                        )

                # these flags are repurposed for HighFramerate modes
                if self.fps == 25 or self.fps == 50:
                    if word == 3:
                        self.polarity = (self.data >> 11) & 0x1
                elif word == 1:
                    self.polarity = (self.data >> 11) & 0x1
                if word == 3:
                    self.bgf1_flag = (self.data >> 10) & 0x1

                self.put(
                    self.ss_data[11] if self.forward else self.ss_data[4],
                    self.ss_data[12] if self.forward else self.ss_data[5],
                    self.out_ann,
                    [8, [": %X" % ((self.data >> 11) & 0x1)]],
                )
                self.put(
                    self.ss_data[12] if self.forward else self.ss_data[0],
                    es if self.forward else self.ss_data[4],
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
