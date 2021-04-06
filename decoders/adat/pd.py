##
## This file is part of the libsigrokdecode project.
##
## Copyright (C)  2020 Hans Baier <hansfbaier@gmail.com>
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

ANN_BIT, ANN_SYNC, ANN_USER, ANN_NIBBLE, ANN_ERROR, ANN_CHANNEL, \
ANN_USER_DATA, \
ANN_CHANNEL_0, ANN_CHANNEL_1, ANN_CHANNEL_2, ANN_CHANNEL_3, \
ANN_CHANNEL_4, ANN_CHANNEL_5, ANN_CHANNEL_6, ANN_CHANNEL_7, \
= range(15)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'adat'
    name = 'ADAT'
    longname = 'ADAT lightpipe decoder'
    desc = 'Decodes the ADAT protocol'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Audio']
    channels = (
        {'id': 'adat', 'name': 'ADAT', 'desc': 'ADAT data line'},
    )
    optional_channels = ()
    annotations = (
        ('bit'            , 'bit'            ),
        ('sync'           , 'SYNC pad'       ),
        ('user-bits'      , 'user bits'      ),
        ('nibble'         , 'nibbles'        ),
        ('error'          , 'error'          ),
        ('channel'        , 'channel data'   ),
        ('frame-user-data', 'frame user data'),
        ('channel-0'      , 'channel 0 data' ),
        ('channel-1'      , 'channel 1 data' ),
        ('channel-2'      , 'channel 2 data' ),
        ('channel-3'      , 'channel 3 data' ),
        ('channel-4'      , 'channel 4 data' ),
        ('channel-5'      , 'channel 5 data' ),
        ('channel-6'      , 'channel 6 data' ),
        ('channel-7'      , 'channel 7 data' ),
    )
    annotation_rows = (
        ('bits',    'Bits',    (ANN_BIT,)),
        ('nibbles', 'Nibbles', (ANN_NIBBLE, ANN_ERROR)),
        ('fields',  'Fields',  (
            ANN_SYNC,
            ANN_USER,
            ANN_CHANNEL,
        )),
        ('user-data', 'Frame User Data', (ANN_USER_DATA,)),
        ('channel0',  'Channel 0 Data',  (ANN_CHANNEL_0,)),
        ('channel1',  'Channel 1 Data',  (ANN_CHANNEL_1,)),
        ('channel2',  'Channel 2 Data',  (ANN_CHANNEL_2,)),
        ('channel3',  'Channel 3 Data',  (ANN_CHANNEL_3,)),
        ('channel4',  'Channel 4 Data',  (ANN_CHANNEL_4,)),
        ('channel5',  'Channel 5 Data',  (ANN_CHANNEL_5,)),
        ('channel6',  'Channel 6 Data',  (ANN_CHANNEL_6,)),
        ('channel7',  'Channel 7 Data',  (ANN_CHANNEL_7,)),
    )
    options = (
        {'id': 'samplerate', 'desc': 'audio sample rate', 'default': 48000},
        {'id': 'sample_display', 'desc': 'How to display the channel samples',
            'default': 'decimal', 'values': ('decimal', 'hexadecimal')},
        {'id': 'annotations', 'desc': 'Which set of annotations to display',
            'default': 'both', 'values': ('intra-frame', 'per-frame', 'both')},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        # signal bits
        self.signal = []
        # bit times for signal bits
        # one list element per signal bit
        self.times = []

        self.diffs = {}
        self.state = "SYNC"
        self.channel_no = 0
        self.nibble_no = 0
        self.channel_data = 0
        self.channel_start_time = 0
        self.all_channels_data = [0] * 8
        self.frame_start_time = 0
        self.frame_user_data = 0

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            audio_samplerate = self.options['samplerate']
            minimum_samplerate = int(2.5 * (256 * audio_samplerate))
            if self.samplerate < minimum_samplerate:
                raise SamplerateError('samplerate %s MHz is too small for decoding ADAT. You need at least %s MHz.' % (self.samplerate/1e6, minimum_samplerate/1e6))

            # one ADAT frame contains one sample for each channel
            # and is 256 bits long
            self.bit_time = self.samplerate / (256 * audio_samplerate)
            self.bit_time_int = int(self.bit_time)
            self.sample_display_hex = self.options['sample_display'] == 'hexadecimal'

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putc(self, cls, ss, annlist):
        self.put(ss, self.samplenum, self.out_ann, [cls, annlist])

    def look_for_sync_pad(self):
        if self.signal[:11] == [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]:
            self.state = "USER BITS"
            times = self.times[:10]

            # chop off parsed bits
            del self.signal[:11]
            del self.times[:11]

            if self.options['annotations'] != 'per-frame':
                self.put(times[0], times[-1] + int(2 * self.bit_time + 0.5), self.out_ann, [ANN_SYNC, ["SYNC", "S"]])
            self.frame_start_time = times[0]
        else:
            # throw away bits until we find the sync pad
            del self.signal[0]
            del self.times[0]

    def decode_user_bits(self):
        if (len(self.signal) < 5):
            # accumulate more bits
            # until we get a nibble
            return

        # this bit must be one (4b/5b encoding)
        # if not, we have a decoding error
        # and start looking for the next sync pad
        if self.signal[0] != 1:
            self.put(self.times[0], self.times[1], \
                     self.out_ann, [ANN_ERROR, ["ERROR", "ERR", "E"]])
            del self.signal[0]
            del self.times[0]
            self.state = "SYNC"
        else:
            user_data = self.signal[1:5]
            times     = self.times[:5]
            content = "0b" + "".join([str(bit) for bit in user_data])
            self.frame_user_data = self.bits_to_int(user_data)

            if self.options['annotations'] != 'per-frame':
                self.put(times[0], times[-1] + self.bit_time_int, \
                        self.out_ann, [ANN_USER, ["USER DATA: " + content, "USER " + content, "U " + content, "U"]])
                self.put(times[1], times[-1] + self.bit_time_int, \
                        self.out_ann, [ANN_NIBBLE, [hex(self.frame_user_data), hex(self.frame_user_data)[2:]]])

            del self.signal[:5]
            del self.times[:5]
            self.state = "CHANNEL DATA"

    @staticmethod
    def bits_to_int(bits: list) -> int:
        result = 0
        for bit in bits:
            result = (result << 1) | bit
        return result

    @staticmethod
    def sign_extend(x):
        return -(0x800000 - (x & 0x7fffff)) if (x & 0x800000) else x

    def decode_channel_data(self):
        if (len(self.signal) < 5):
            # accumulate more bits
            # until we get a nibble
            return

        # this bit must be one (4b/5b encoding)
        # if not, we have a decoding error
        # and start looking for the next sync pad
        if self.signal[0] != 1:
            self.put(self.times[0], self.times[1], \
                     self.out_ann, [ANN_ERROR, ["ERROR", "ERR", "E"]])
            del self.signal[0]
            del self.times[0]

            self.channel_no    = 0
            self.channel_data  = 0
            self.nibble_no     = 0
            self.state = "SYNC"
            return

        nibble_bits = self.signal[1:5]
        nibble       = self.bits_to_int(nibble_bits)
        nibble_times = self.times[:5]

        # prune parsed data from the input stream
        del self.signal[:5]
        del self.times[:5]

        if self.nibble_no == 0:
            self.channel_start_time = nibble_times[0]

        self.channel_data |= nibble << (20 - (self.nibble_no * 4))
        self.nibble_no += 1

        if self.options['annotations'] != 'per-frame':
            self.put(nibble_times[1], nibble_times[-1] + self.bit_time_int, \
                    self.out_ann, [ANN_NIBBLE, [hex(nibble), hex(nibble)[2:]]])

        # data for one channel is complete (6 nibbles = 24bit)
        if self.nibble_no == 6:
            self.nibble_no = 0
            content = "0x{0:06x}".format(self.channel_data)

            if self.options['annotations'] != 'per-frame':
                self.put(self.channel_start_time, nibble_times[-1] + self.bit_time_int,
                        self.out_ann,
                            [ANN_CHANNEL, [
                                "Channel {0}: {1}".format(self.channel_no, content),
                                "Ch{0}: {1}".format(self.channel_no, content),
                                "Ch{0}: {1}".format(self.channel_no, content[2:]),
                                "Ch{0}".format(self.channel_no),
                                "{0}".format(self.channel_no)]])

            self.all_channels_data[self.channel_no] = self.channel_data
            self.channel_no = self.channel_no + 1
            self.channel_data = 0
            self.nibble_no = 0

        # after receiving all the channel data
        # the sync pad has to be next
        if (self.channel_no == 8):
            for ch_no in range(8):
                hex_str = "0x{0:06x}".format(self.all_channels_data[ch_no])
                decimal_str = "{0:+}".format(self.sign_extend(self.all_channels_data[ch_no]))
                value_str = hex_str if self.sample_display_hex else decimal_str

                if self.options['annotations'] != 'intra-frame':
                    self.put(self.frame_start_time, nibble_times[-1] + self.bit_time_int,
                            self.out_ann, [ANN_CHANNEL_0 + ch_no,
                                [value_str, value_str.replace("0x", "")]])

            if self.options['annotations'] != 'intra-frame':
                self.put(self.frame_start_time, nibble_times[-1] + self.bit_time_int,
                            self.out_ann, [ANN_USER_DATA, [bin(self.frame_user_data), bin(self.frame_user_data)[2:]]])

            self.channel_no = 0
            self.state = "SYNC"

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        last_time = 0
        while True:
            self.wait([{0: 'e'}])[0]

            now      = self.samplenum
            diff     = now - last_time
            num_bits = int(diff / self.bit_time + 0.5)

            times_n_bits = zip([last_time + int(self.bit_time * i + 0.5) for i in range(num_bits)], [1] + (num_bits - 1) * [0])
            for time, bit in times_n_bits:
                self.signal.append(bit)
                self.times.append(time)

                if self.options['annotations'] != 'per-frame':
                    self.put(time, time + self.bit_time_int, self.out_ann, [ANN_BIT, ["{0}".format(bit)]])

            if self.state == "SYNC":
                while self.state == "SYNC" and len(self.signal) >= 11:
                    self.look_for_sync_pad()
            elif self.state == "USER BITS":
                self.decode_user_bits()
            elif self.state == "CHANNEL DATA":
                self.decode_channel_data()

            last_time = now
