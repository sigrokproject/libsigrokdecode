##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Jean Gressmann <jean@0x42.de>
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included in all
## copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
## SOFTWARE.
##

import abc
import sigrokdecode as srd

class DataCrc:
    '''CRC computation for the SENT frame and Short Serial Message Format'''

    TABLE = [0, 13, 7, 10, 14, 3, 9, 4, 1, 12, 6, 11, 15, 2, 8, 5]
    INIT = 5

    @staticmethod
    def update(crc, nibble):
        return DataCrc.TABLE[crc] ^ nibble

    @staticmethod
    def finalize(crc):
        return DataCrc.update(crc, 0)


class EnhancedSerialCrc:
    '''CRC computation for the Enhanced Serial Message Format'''

    TABLE = [
        0, 25, 50, 43, 61, 36, 15, 22, 35, 58, 17, 8, 30, 7, 44, 53,
        31, 6, 45, 52, 34, 59, 16, 9, 60, 37, 14, 23, 1, 24, 51, 42,
        62, 39, 12, 21, 3, 26, 49, 40, 29, 4, 47, 54, 32, 57, 18, 11,
        33, 56, 19, 10, 28, 5, 46, 55, 2, 27, 48, 41, 63, 38, 13, 20
    ]
    INIT = 0x15

    @staticmethod
    def update(crc, value):
        return EnhancedSerialCrc.TABLE[crc] ^ value

    @staticmethod
    def finalize(crc):
        return EnhancedSerialCrc.update(crc, 0)

class SlowProtocolBase(abc.ABC):
    def __init__(self):
        self.decoder = None

    @abc.abstractmethod
    def on_frame_start(self):
        return NotImplemented

    @abc.abstractmethod
    def on_frame_end(self, error):
        return NotImplemented

    @abc.abstractmethod
    def update(self, status_nibble):
        return NotImplemented


class SlowProtocolNone(SlowProtocolBase):
    '''Protocol for SENT channels without slow / serial data'''

    def on_frame_start(self):
        pass

    def on_frame_end(self, error):
        pass

    def update(self, status_nibble):
        if status_nibble & 0xC:
            self.decoder.put_error_at(self.decoder.pulse_falling0, self.decoder.pulse_falling1, 'No Serial: expect 0 in status bits 2 and 3')


class SlowProtocolShort(SlowProtocolBase):
    '''Protocol for the Short Serial Message Format (4-bit message ID, 8-bit data)'''

    FRAMES_FOR_MESSAGE = 16
    START_OF_MESSAGE_FLAG = 0x8
    DATA_FLAG = 0x4

    def __init__(self, *args, **kwargs):
        SlowProtocolBase.__init__(self, *args, **kwargs)
        self.frame_starts = [0 for _ in range(SlowProtocolShort.FRAMES_FOR_MESSAGE + 1)]
        self._reset()

    def _reset(self):
        self.frame_index = 0
        self.start_of_message_seen = False
        self.bits = 0

    def on_frame_start(self):
        self.frame_starts[self.frame_index] = self.decoder.pulse_falling0

    def on_frame_end(self, error):
        if None is error or not error:
            if self.start_of_message_seen:
                self.frame_index += 1

                if SlowProtocolShort.FRAMES_FOR_MESSAGE == self.frame_index:
                    self.frame_starts[self.frame_index] = self.decoder.pulse_falling1

                    message_id = (self.bits >> 12) & 0xf
                    byte = (self.bits >> 4) & 0xff
                    crc = self.bits & 0xf

                    self.decoder.put_field_at(self.frame_starts[0], self.frame_starts[4], Decoder.SHORT_SERIAL_MESSAGE_ID_ANN_INDEX, [f'Message ID: 0x{message_id:X}', f'Msg ID: 0x{message_id:X}', f'0x{message_id:X}'])
                    self.decoder.put_field_at(self.frame_starts[4], self.frame_starts[12], Decoder.SHORT_SERIAL_DATA_BYTE_ANN_INDEX, [f'Data: 0x{byte:02X}', f'0x{byte:02X}'])
                    self.decoder.put_field_at(self.frame_starts[12], self.frame_starts[16], Decoder.SHORT_SERIAL_CRC_ANN_INDEX, [f'CRC: 0x{crc:X}', f'0x{crc:X}'])

                    # compute CRC
                    computed_crc = DataCrc.INIT
                    computed_crc = DataCrc.update(computed_crc, message_id)
                    computed_crc = DataCrc.update(computed_crc, (byte >> 4) & 0xf)
                    computed_crc = DataCrc.update(computed_crc, (byte >> 0) & 0xf)
                    computed_crc = DataCrc.finalize(computed_crc)

                    if crc != computed_crc:
                        self.decoder.put_error_at(self.frame_starts[12], self.frame_starts[16], f'Serial: CRC Mismatch: 0x{computed_crc:X}')


                    self._reset()
        else:
             self._reset()

    def update(self, status_nibble):
        if status_nibble & SlowProtocolShort.START_OF_MESSAGE_FLAG:
            self.decoder.put_field(Decoder.SHORT_SERIAL_START_ANN_INDEX, ['Start of Frame', 'SOF', 'S'])

            if self.start_of_message_seen:
                self.decoder.put_error(f'Serial: expect status bit 3 to be zero (0), prev. SOF {self.frame_index} frames ago')


                # re-start from this frame
                self.frame_starts[0] = self.frame_starts[self.frame_index]
                self.frame_index = 0
                self.bits = 0

            else:
                self.start_of_message_seen = True


        if self.start_of_message_seen:
            self.bits <<= 1
            self.bits |= int((status_nibble & SlowProtocolShort.DATA_FLAG) == SlowProtocolShort.DATA_FLAG)

class SlowProtocolEnhanced(SlowProtocolBase):
    '''Protocol for the Enhanced Serial Message Format

C0: 8-bit message ID, 12-bit data
C1: 4-bit message ID, 16-bit data
'''

    FRAMES_FOR_MESSAGE = 18
    BIT3_FLAG = 0x8
    BIT2_FLAG = 0x4

    def __init__(self, no, *args, **kwargs):
        SlowProtocolBase.__init__(self, *args, **kwargs)
        self.no = no
        self._reset()

    def _reset(self):
        self.bits3 = ''
        self.bits2 = ''
        self.frame_starts = []

    def _on_message_complete(self):
        # pop off frame with leading 0 in bit 3
        self.bits3 = self.bits3[1:]
        self.bits2 = self.bits2[1:]
        self.frame_starts = self.frame_starts[1:]

        # add end of this frame
        self.frame_starts.append(self.decoder.pulse_falling1)

        # extract fields
        b3 = int(self.bits3, 2)
        b2 = int(self.bits2, 2)

        config = (b3 >> 10) & 0x1
        msg_id = (b3 >> 6) & 0xf
        msg_id_or_data = (b3 >> 1) & 0xf
        crc = (b2 >> 12) & 0x3f
        data = (b2 & 0xfff)

        if self.no:
            data |= msg_id_or_data << 12
        else:
            msg_id <<= 4
            msg_id |= msg_id_or_data



        message_id_labels = [f'Message ID: 0x{msg_id:02X}', f'Msg ID: 0x{msg_id:02X}', f'0x{msg_id:02X}']
        data_labels = [f'Data: 0x{data:04X}', f'0x{data:04X}']
        zero_labels = ['Zero (0)', '0']

        # on bit 3
        self.decoder.put_field_at(self.frame_starts[0], self.frame_starts[7], Decoder.ENHANCED_SERIAL_START_OF_FRAME_ANN_INDEX, ['Start of Frame', 'SOF', 'S'])
        self.decoder.put_field_at(self.frame_starts[7], self.frame_starts[8], Decoder.ENHANCED_SERIAL_CONFIG_ANN_INDEX, [f'Configuration: {config}', f'Conf: {config}', f'{config}'])

        self.decoder.put_field_at(self.frame_starts[8], self.frame_starts[12], Decoder.ENHANCED_SERIAL_MESSAGE_ID3_ANN_INDEX, message_id_labels)
        self.decoder.put_field_at(self.frame_starts[12], self.frame_starts[13], Decoder.ENHANCED_SERIAL_ZERO_ANN_INDEX, zero_labels)


        if self.no:
            self.decoder.put_field_at(self.frame_starts[13], self.frame_starts[17], Decoder.ENHANCED_SERIAL_DATA3_ANN_INDEX, data_labels)
        else:
            self.decoder.put_field_at(self.frame_starts[13], self.frame_starts[17], Decoder.ENHANCED_SERIAL_MESSAGE_ID3_ANN_INDEX, message_id_labels)

        self.decoder.put_field_at(self.frame_starts[17], self.frame_starts[18], Decoder.ENHANCED_SERIAL_ZERO_ANN_INDEX, zero_labels)

        # on bit 2
        self.decoder.put_field_at(self.frame_starts[0], self.frame_starts[6], Decoder.ENHANCED_SERIAL_CRC_ANN_INDEX, [f'CRC: 0x{crc:02X}', f'0x{crc:02X}'])
        self.decoder.put_field_at(self.frame_starts[6], self.frame_starts[18], Decoder.ENHANCED_SERIAL_DATA2_ANN_INDEX, data_labels)

        # static verification of zeros in bit 3
        if self.bits3[12] != '0':
            self.decoder.put_error_at(self.frame_starts[12], self.frame_starts[13], 'Serial: bit number 13: expect status bit 3 to be zero (0)')

        if self.bits3[17] != '0':
            self.decoder.put_error_at(self.frame_starts[17], self.frame_starts[18], 'Serial: bit number 18: expect status bit 3 to be zero (0)')

        # verification of configuration
        if self.no != config:
            self.decoder.put_error_at(self.frame_starts[7], self.frame_starts[8], f'Serial: bit number 8: expect status bit 3 to match configuration ({self.no})')

        # compute CRC
        crc_bits = ''

        for (b2, b3) in zip(self.bits2[6:], self.bits3[6:]):
            crc_bits += b2
            crc_bits += b3

        computed_crc = EnhancedSerialCrc.INIT

        for i in range(4):
            x = int(crc_bits[i*6:(i+1)*6], 2)
            computed_crc = EnhancedSerialCrc.update(computed_crc, x)

        computed_crc = EnhancedSerialCrc.finalize(computed_crc)

        if computed_crc != crc:
            self.decoder.put_error_at(self.frame_starts[0], self.frame_starts[7], f'Serial: CRC mismatch: 0x{computed_crc:02X}')

        # clean up
        self._reset()

        # pretend we just read the last part of this message
        self.bits3 = '0'
        self.bits2 = '0'
        self.frame_starts = [self.decoder.pulse_falling1]

    def on_frame_start(self):
        self.frame_starts.append(self.decoder.pulse_falling0)

    def on_frame_end(self, error):
        if None is error or not error:
            if len(self.bits3) == SlowProtocolEnhanced.FRAMES_FOR_MESSAGE + 1 and self.bits3.startswith('01111110'):
                self._on_message_complete()
        else:
             self._reset()

    def update(self, status_nibble):
        self.bits3 += str(int((status_nibble & SlowProtocolEnhanced.BIT3_FLAG) == SlowProtocolEnhanced.BIT3_FLAG))
        self.bits2 += str(int((status_nibble & SlowProtocolEnhanced.BIT2_FLAG) == SlowProtocolEnhanced.BIT2_FLAG))

        if len(self.bits3) > SlowProtocolEnhanced.FRAMES_FOR_MESSAGE + 1:
            self.bits3 = self.bits3[1:]
            self.bits2 = self.bits2[1:]
            self.frame_starts = self.frame_starts[1:]


class SamplerateError(Exception):
    pass


class ClockTickTimeError(Exception):
    pass


class SlowFormatError(Exception):
    pass


class Sent:
    MIN_LOW_LEVEL_TICKS = 4
    CALIBRATION_LEN_TICKS = 56       # see spec, section 5.2.2
    NIBBLE_MIN_LEN_TICKS = 12        # see spec, section 5.2.3
    NIBBLE_MAX_LEN_TICKS = 27        # see spec, section 5.2.3, 27-12 = 15 = max nibble value
    PULSE_PAUSE_MIN_LEN_TICKS = 12   # see spec, section 5.2.6
    PULSE_PAUSE_MAX_LEN_TICKS = 768  # see spec, section 5.2.6
    FAST_CH1_STATUS_ERROR_FLAG = 0x1 # see spec, Table H-2
    FAST_CH2_STATUS_ERROR_FLAG = 0x2 # see spec, Table H-2

    FAST_FORMAT_TO_FRAME_LENGTH = {
        'H.1': 6,
        'H.2': 3,
        'H.3': 4,
        'H.4': 6,
        'H.5': 6,
        'H.6': 6,
        'H.7': 6,
    }

    class ProtocolState:
        NONE = 'NONE'
        CALIBRATION = 'CALIBRATION'
        STATUS = 'STATUS'
        DATA = 'DATA'
        CRC = 'CRC'
        PAUSE = 'PAUSE'

    PULSE_PAUSE_MODE_MAYBE = 'maybe'
    PULSE_PAUSE_MODE_YES = 'yes'
    PULSE_PAUSE_MODE_NO = 'no'
    PULSE_PAUSE_MODES = (PULSE_PAUSE_MODE_MAYBE, PULSE_PAUSE_MODE_YES, PULSE_PAUSE_MODE_NO)

    SLOW_CHANNEL_FORMAT_NONE = 'None'
    SLOW_CHANNEL_FORMAT_SHORT = 'Short'
    SLOW_CHANNEL_FORMAT_ENHANCED_C0 = 'Enhanced C0'
    SLOW_CHANNEL_FORMAT_ENHANCED_C1 = 'Enhanced C1'
    SLOW_CHANNEL_FORMATS = (SLOW_CHANNEL_FORMAT_NONE, SLOW_CHANNEL_FORMAT_SHORT, SLOW_CHANNEL_FORMAT_ENHANCED_C0, SLOW_CHANNEL_FORMAT_ENHANCED_C1)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'sent'
    name = 'SENT'
    longname = 'Single Edge Nibble Transmission'
    desc = 'One-wire serial bus.'
    license = 'mit'
    inputs = ['logic']
    outputs = ['sent']
    tags = ['Automotive']
    channels = (
        {'id': 'data', 'name': 'Data', 'desc': 'Data Line'},
    )
    options = (
        {'id': 'clock-tick-time', 'desc': 'Clock Tick Time [us]', 'default': 3},
        {'id': 'fast-format', 'desc': 'Fast Channel Format', 'default': 'H.1', 'values': tuple(Sent.FAST_FORMAT_TO_FRAME_LENGTH.keys())},
        {'id': 'slow-format', 'desc': 'Slow Channel Format', 'default': Sent.SLOW_CHANNEL_FORMAT_NONE, 'values': Sent.SLOW_CHANNEL_FORMATS},
        {'id': 'pulse-pause', 'desc': 'Pulse Pause', 'default': Sent.PULSE_PAUSE_MODE_MAYBE, 'values': Sent.PULSE_PAUSE_MODES},
    )
    annotations = (
        ('error', 'Error'),                                         # 0
        ('calibration', 'Calibration'),                             # 1
        ('nibble', 'Nibble'),                                       # 2
        ('status', 'Status'),                                       # 3
        ('data', 'Data'),                                           # 4
        ('crc', 'CRC'),                                             # 5
        ('short-serial-start', 'Short Serial Start Bit'),           # 6
        ('short-serial-message-id', 'Short Serial Message ID'),     # 7
        ('short-serial-data-byte', 'Short Serial Data Byte'),       # 8
        ('short-serial-data-crc', 'Short Serial CRC'),              # 9
        ('enh-serial-data', 'Enhanced Serial Data (2)'),            # 10
        ('fast-channel1-value', 'Fast Channel 1 Value'),            # 11
        ('fast-channel2-value', 'Fast Channel 2 Value'),            # 12
        ('pulse-pause', 'Pulse Pause'),                             # 13
        ('secure-sensor-counter', 'Secure Sensor Counter'),         # 14
        ('secure-sensor-inv-msn', 'Secure Sensor Inverted MSN'),    # 15
        ('enh-serial-config', 'Enhanced Serial Configuration Bit'), # 16
        ('enh-serial-crc', 'Enhanced Serial CRC'),                  # 17
        ('enh-serial-msg-id3', 'Enhanced Serial Message ID (3)'),   # 18
        ('enh-serial-data3', 'Enhanced Serial Data (3)'),           # 19
        ('enh-serial-sof', 'Enhanced Serial Start of Frame'),       # 20
        ('enh-serial-msg-id2', 'Enhanced Serial Message ID (2)'),   # 21
        ('enh-serial-msg-zero', 'Zero'),                            # 22
        ('fast-channel1-error', 'Fast Channel 1 Error Bit'),        # 23
        ('fast-channel2-error', 'Fast Channel 2 Error Bit'),        # 24


    )
    annotation_rows = (
         ('nibbles', 'Nibbles', (2,)),
         ('fields', 'Fields', (1, 3, 4, 5, 13)),
         ('fast', 'Fast', (11, 12, 14, 15, 23, 24)),
         ('slow-bit3', 'Slow (Bit 3)', (6, 16, 17, 20, 16, 18, 18, 22)),
         ('slow-bit2', 'Slow (Bit 2)', (7, 8, 9, 10, 17, 21)),
         ('error', 'Error', (0,)),
    )

    ERROR_ANN_INDEX = 0
    CALIBRATION_ANN_INDEX = 1
    NIBBLE_ANN_INDEX = 2
    STATUS_ANN_INDEX = 3
    DATA_ANN_INDEX = 4
    CRC_ANN_INDEX = 5
    SHORT_SERIAL_START_ANN_INDEX = 6
    SHORT_SERIAL_MESSAGE_ID_ANN_INDEX = 7
    SHORT_SERIAL_DATA_BYTE_ANN_INDEX = 8
    SHORT_SERIAL_CRC_ANN_INDEX = 9
    ENHANCED_SERIAL_DATA2_ANN_INDEX = 10
    FAST_CH1_VALUE_ANN_INDEX = 11
    FAST_CH2_VALUE_ANN_INDEX = 12
    PULSE_PAUSE_ANN_INDEX = 13
    SECURE_SENSOR_COUNTER_ANN_INDEX = 14
    SECURE_SENSOR_INVERTED_MSN_ANN_INDEX = 15
    ENHANCED_SERIAL_CONFIG_ANN_INDEX = 16
    ENHANCED_SERIAL_CRC_ANN_INDEX = 17
    ENHANCED_SERIAL_MESSAGE_ID3_ANN_INDEX = 18
    ENHANCED_SERIAL_DATA3_ANN_INDEX = 19
    ENHANCED_SERIAL_START_OF_FRAME_ANN_INDEX = 20
    ENHANCED_SERIAL_MESSAGE_ID2_ANN_INDEX = 21
    ENHANCED_SERIAL_ZERO_ANN_INDEX = 22
    FAST_CH1_ERROR_ANN_INDEX = 23
    FAST_CH2_ERROR_ANN_INDEX = 24


    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.pulse_falling0 = None
        self.pulse_falling1 = None
        self.pulse_rising = None
        self.state = Sent.ProtocolState.NONE
        self.sample_rate_to_us_conversion_factor = None
        self.clock_time_time = None
        self.clock_time_time_half = None
        self.nibble_min_len_us = None
        self.nibble_max_len_us = None
        self.calibration_pulse_len_us = None
        self.pause_pulse_max_len_us = None
        self.slow_protocol = None


    def start(self):
        self.output_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def samples_to_us(self, count):
        return self.sample_rate_to_us_conversion_factor * count

    def wait_for_next_pulse(self):
        # self.wait({0: 'f'})
        # self.pulse_falling0 = self.samplenum

        self.pulse_falling0 = self.samplenum

        self.wait({0: 'r'})
        self.pulse_rising = self.samplenum

        self.wait({0: 'f'})
        self.pulse_falling1 = self.samplenum

        self.pulse_len_in_us = self.samples_to_us(self.pulse_falling1 - self.pulse_falling0)

    def pulse_to_nibble(self):
        '''Length of the pulse determines the value of the nibble'''
        nibble = max(self.nibble_min_len_us, min(self.pulse_len_in_us, self.nibble_max_len_us))
        nibble -= self.nibble_min_len_us
        nibble += self.clock_time_time_half
        return int(nibble // self.clock_time_time)

    def pulse_start_valid(self):
        '''Valid pulses start with 4 or more clock ticks of low'''
        return self.samples_to_us(self.pulse_rising - self.pulse_falling0) + self.clock_time_time >= Sent.MIN_LOW_LEVEL_TICKS * self.clock_time_time

    def pulse_length_valid(self):
        '''Valid pulses have a minimum length of 12 ticks'''
        return self.samples_to_us(self.pulse_falling1 - self.pulse_falling0) + self.clock_time_time >= self.nibble_min_len_us

    def pulse_is_valid_nibble(self):
        return self.pulse_start_valid() and \
                self.pulse_length_valid() and \
                self.pulse_len_in_us + self.clock_time_time >= self.nibble_min_len_us \
                and \
                self.pulse_len_in_us - self.clock_time_time <= self.nibble_max_len_us

    def pulse_is_valid_calibration(self):
        return self.pulse_start_valid() and \
                self.pulse_length_valid() and \
                self.pulse_len_in_us + self.clock_time_time >= self.calibration_pulse_len_us \
                and \
                self.pulse_len_in_us - self.clock_time_time <= self.calibration_pulse_len_us

    def pulse_is_valid_pause(self):
        return self.pulse_start_valid() and \
                self.pulse_length_valid() and \
                self.pulse_len_in_us + self.clock_time_time >= self.nibble_min_len_us \
                and \
                self.pulse_len_in_us - self.clock_time_time <= self.pause_pulse_max_len_us

    def _explain(self, field_name, min_len, max_len):
        if not self.pulse_start_valid():
            return field_name + ': low period too short'

        if not self.pulse_length_valid():
            return field_name + ': pulse too short (< 12 clock ticks)'

        if self.pulse_len_in_us + self.clock_time_time < min_len:
            return field_name + ': pulse too short'

        if self.pulse_len_in_us - self.clock_time_time > max_len:
            return field_name + ': pulse too long'

        return field_name + ': unknown'

    def explain_bad_nibble(self):
        return self._explain('Nibble', self.nibble_min_len_us, self.nibble_max_len_us)

    def explain_bad_calibration(self):
        return self._explain('Calibration', self.calibration_pulse_len_us, self.calibration_pulse_len_us)

    def explain_bad_pause(self):
        return self._explain('Pulse Pause', self.nibble_min_len_us, self.pause_pulse_max_len_us)

    def put_error(self, string):
        self.put_error_at(self.pulse_falling0, self.pulse_falling1, string)

    def put_error_at(self, start, end, string):
        self.put_field_at(start, end, Decoder.ERROR_ANN_INDEX, [string])

    def put_field(self, field_index, strings):
        self.put_field_at(self.pulse_falling0, self.pulse_falling1, field_index, strings)

    def put_field_at(self, start, end, field_index, strings):
        self.put(start, end, self.output_ann, [field_index, strings])

    def _set_slow_or_fail(self):
        format = self.options['slow-format']

        if Sent.SLOW_CHANNEL_FORMAT_NONE == format:
            self.slow_protocol = SlowProtocolNone()
        elif Sent.SLOW_CHANNEL_FORMAT_SHORT == format:
            self.slow_protocol = SlowProtocolShort()
        elif Sent.SLOW_CHANNEL_FORMAT_ENHANCED_C0 == format:
            self.slow_protocol = SlowProtocolEnhanced(0)
        elif Sent.SLOW_CHANNEL_FORMAT_ENHANCED_C1 == format:
            self.slow_protocol = SlowProtocolEnhanced(1)
        else:
            raise SlowFormatError(f'unknown format {format}')

        self.slow_protocol.decoder = self

    @staticmethod
    def format_fast_channel_value(no, value, hex_chars, error):
        dec_value = str(value)
        hex_value = '0x{0:0{1}X}'.format(value, hex_chars)
        error_indication = " (Error)" if error else ""

        return [f'Channel {no}: {dec_value} ({hex_value}){error_indication}', f'Ch{no}: {dec_value} ({hex_value}){error_indication}', f'Ch{no}: ({hex_value}){error_indication}']

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        self.sample_rate_to_us_conversion_factor = 1_000_000 / self.samplerate

        self.clock_time_time = self.options['clock-tick-time']
        fast_format = self.options['fast-format']
        pulse_pause_mode = self.options['pulse-pause']

        if self.clock_time_time < 1:
            raise ClockTickTimeError('Clock Tick Time must be greater or equal to 1 microsecond')


        self._set_slow_or_fail()

        nibbles = Sent.FAST_FORMAT_TO_FRAME_LENGTH[fast_format]


        self.clock_time_time_half = self.clock_time_time / 2
        self.nibble_min_len_us = Sent.NIBBLE_MIN_LEN_TICKS * self.clock_time_time
        self.nibble_max_len_us = Sent.NIBBLE_MAX_LEN_TICKS * self.clock_time_time
        self.calibration_pulse_len_us = Sent.CALIBRATION_LEN_TICKS * self.clock_time_time
        self.pause_pulse_max_len_us = Sent.PULSE_PAUSE_MAX_LEN_TICKS * self.clock_time_time

        data_index = 0
        computed_crc = 0
        calibration_strings = ['Calibration', 'Cal', 'C']
        pulse_pause_strings = ['Pulse Pause', 'Pause', 'P']
        fast_ch1_bad_value_strings = ['Channel 1: Value Error (1)', 'Ch1: Error (1)']
        fast_ch1_good_value_strings = ['Channel 1: Value OK (0)', 'Ch1: OK (0)']
        fast_ch2_bad_value_strings = ['Channel 2: Value Error (1)', 'Ch2: Error (1)']
        fast_ch2_good_value_strings = ['Channel 2: Value OK (0)', 'Ch2: OK (0)']

        fast_channel_data_nibbles = [0 for _ in range(6)]
        fast_channel_data_offsets = [0 for _ in range(7)]
        secure_sensor_prev_counter = None
        has_frame_error = False
        any_valid_calibration_seen = False

        # sync to first falling edge ...
        self.wait({0: 'f'})

        while True:
            if Sent.ProtocolState.NONE == self.state:
                self.wait_for_next_pulse()

                has_frame_error = False

                # detect calibration pulse
                if self.pulse_is_valid_calibration():
                    self.put_field(Decoder.CALIBRATION_ANN_INDEX, calibration_strings)
                    self.state = Sent.ProtocolState.STATUS
                    any_valid_calibration_seen = True
                    self.slow_protocol.on_frame_start()
                else:
                    if any_valid_calibration_seen:
                        if Sent.PULSE_PAUSE_MODE_MAYBE == pulse_pause_mode and self.pulse_is_valid_pause():
                            self.put_field(Decoder.PULSE_PAUSE_ANN_INDEX, pulse_pause_strings)
                            self.state = Sent.ProtocolState.CALIBRATION
                        else:
                            self.put_error(self.explain_bad_calibration())
                            self.slow_protocol.on_frame_end(True)


            elif Sent.ProtocolState.PAUSE == self.state:
                self.wait_for_next_pulse()

                self.put_field(Decoder.PULSE_PAUSE_ANN_INDEX, pulse_pause_strings)

                if self.pulse_is_valid_pause():
                    self.state = Sent.ProtocolState.CALIBRATION
                else:
                    has_frame_error = True
                    self.put_error(self.explain_bad_pause())

            elif Sent.ProtocolState.CALIBRATION == self.state:
                self.wait_for_next_pulse()

                self.put_field(Decoder.CALIBRATION_ANN_INDEX, calibration_strings)

                has_frame_error = False

                if self.pulse_is_valid_calibration():
                    self.state = Sent.ProtocolState.STATUS
                    any_valid_calibration_seen = True
                    self.slow_protocol.on_frame_start()
                else:
                    has_frame_error = True
                    self.put_error(self.explain_bad_calibration())

            elif Sent.ProtocolState.STATUS == self.state:
                self.wait_for_next_pulse()

                status_nibble = self.pulse_to_nibble()
                self.put_field(Decoder.NIBBLE_ANN_INDEX, [f'0x{status_nibble:01X}'])
                self.put_field(Decoder.STATUS_ANN_INDEX, ['Status', 'S'])

                self.slow_protocol.update(status_nibble)

                status_nibble_beg = self.pulse_falling0
                status_nibble_end = self.pulse_falling1

                if not self.pulse_is_valid_nibble():
                    self.put_error(self.explain_bad_nibble())
                    has_frame_error = True

                self.state = Sent.ProtocolState.DATA
                data_index = 0
                computed_crc = DataCrc.INIT

            elif Sent.ProtocolState.DATA == self.state:
                self.wait_for_next_pulse()

                nibble = self.pulse_to_nibble()
                self.put_field(Decoder.NIBBLE_ANN_INDEX, [f'0x{nibble:X}'])
                self.put_field(Decoder.DATA_ANN_INDEX, ['Data', 'D'])

                if not self.pulse_is_valid_nibble():
                    self.put_error(self.explain_bad_nibble())
                    has_frame_error = True

                fast_channel_data_nibbles[data_index] = nibble
                fast_channel_data_offsets[data_index] = self.pulse_falling0
                data_index += 1
                computed_crc = DataCrc.update(computed_crc, nibble)


                if data_index == nibbles:
                    fast_channel_data_offsets[data_index] = self.pulse_falling1
                    self.state = Sent.ProtocolState.CRC

                    ch1_error = (status_nibble & Sent.FAST_CH1_STATUS_ERROR_FLAG) == Sent.FAST_CH1_STATUS_ERROR_FLAG
                    ch2_error = (status_nibble & Sent.FAST_CH2_STATUS_ERROR_FLAG) == Sent.FAST_CH2_STATUS_ERROR_FLAG

                    fast_channel_error_flag_width = max(1, (status_nibble_end - status_nibble_beg) // 4)
                    fast_channel_error_flag_offsets = (
                        status_nibble_beg + 2 * fast_channel_error_flag_width,
                        status_nibble_beg + 3 * fast_channel_error_flag_width,
                        status_nibble_end
                    )

                    # for handling of split nibbles see spec. p. 103

                    if 'H.1' == fast_format:
                        # Two 12-bit fast channels
                        ch1_value = (fast_channel_data_nibbles[0] << 8) | (fast_channel_data_nibbles[1] << 4) | fast_channel_data_nibbles[2]
                        ch2_value = (fast_channel_data_nibbles[5] << 8) | (fast_channel_data_nibbles[4] << 4) | fast_channel_data_nibbles[3]
                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[3], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 3, ch1_error))
                        self.put_field_at(fast_channel_data_offsets[3], fast_channel_data_offsets[6], Decoder.FAST_CH2_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(2, ch2_value, 3, ch2_error))
                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, fast_ch2_bad_value_strings if ch1_error else fast_ch2_good_value_strings)
                    elif 'H.2' == fast_format:
                        # One 12-bit fast channel
                        ch1_value = (fast_channel_data_nibbles[0] << 8) | (fast_channel_data_nibbles[1] << 4) | fast_channel_data_nibbles[2]
                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[3], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 3, ch1_error))
                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        if ch2_error:
                            self.put_error_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], 'Expect 0, no second sensor channel')
                        else:
                            self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, ['0'])
                    elif 'H.3' == fast_format:
                        # High-speed with one 12-bit fast channel
                        ch1_value = ((fast_channel_data_nibbles[0] & 0x7) << 9) | \
                                    ((fast_channel_data_nibbles[1] & 0x7) << 6) | \
                                    ((fast_channel_data_nibbles[2] & 0x7) << 3) | \
                                    (fast_channel_data_nibbles[3] & 0x7)
                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[4], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 3, ch1_error))

                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        if ch2_error:
                            self.put_error_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], 'Expect 0, no second sensor channel')
                        else:
                            self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, ['0'])
                    elif 'H.4' == fast_format:
                        # Secure sensor with 12-bit fast channel 1 and secure sensor information on fast channel 2
                        ch1_value = (fast_channel_data_nibbles[0] << 8) | (fast_channel_data_nibbles[1] << 4) | fast_channel_data_nibbles[2]
                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[3], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 3, ch1_error))

                        counter = (fast_channel_data_nibbles[3] << 4) | fast_channel_data_nibbles[4]
                        inv_msn = fast_channel_data_nibbles[5]

                        self.put_field_at(fast_channel_data_offsets[3], fast_channel_data_offsets[5], Decoder.SECURE_SENSOR_COUNTER_ANN_INDEX, [f'Counter: {counter} (0x{counter:02X})'])
                        self.put_field_at(fast_channel_data_offsets[5], fast_channel_data_offsets[6], Decoder.SECURE_SENSOR_INVERTED_MSN_ANN_INDEX, [f'Inverted MSN: 0x{inv_msn:X}', f'Inv. MSN: 0x{inv_msn:X}'])

                        # check for counter match
                        if None is not secure_sensor_prev_counter:
                            secure_sensor_prev_counter_next = (secure_sensor_prev_counter + 1) & 0xff

                            if secure_sensor_prev_counter_next != counter:
                                has_frame_error = True
                                self.put_error_at(fast_channel_data_offsets[5], fast_channel_data_offsets[6], f'Expect 0x{secure_sensor_prev_counter_next:02X}')

                        secure_sensor_prev_counter = counter
                        target_inv_msn = (~fast_channel_data_nibbles[0]) & 0xf

                        if inv_msn != target_inv_msn:
                            has_frame_error = True
                            self.put_error_at(fast_channel_data_offsets[5], fast_channel_data_offsets[6], f'Expect 0x{target_inv_msn:X}')

                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        if ch2_error:
                            self.put_error_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], 'Expect 0, no second sensor channel')
                        else:
                            self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, ['0'])
                    elif 'H.5' == fast_format:
                        # Single sensor with 12-bit fast channel 1 and zero value on fast channel 2
                        ch1_value = (fast_channel_data_nibbles[0] << 8) | (fast_channel_data_nibbles[1] << 4) | fast_channel_data_nibbles[2]
                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[3], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 3, ch1_error))

                        # check remaining nibbles for zeros
                        for i in range(4, 6):
                            if fast_channel_data_nibbles[i] != 0:
                                self.put_error_at(fast_channel_data_offsets[i], fast_channel_data_offsets[i+1], 'Expect 0')

                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        if ch2_error:
                            self.put_error_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], 'Expect 0, no second sensor channel')
                        else:
                            self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, ['0'])
                    elif 'H.6' == fast_format:
                        # Two fast channels with 14-bit fast channel 1 and 10-bit fast channel 2
                        ch1_value = (fast_channel_data_nibbles[0] << 10) | \
                                    (fast_channel_data_nibbles[1] << 6) | \
                                    (fast_channel_data_nibbles[2] << 2) | \
                                    ((fast_channel_data_nibbles[3] >> 2) & 0x3)

                        ch2_value = (fast_channel_data_nibbles[5] << 6) | \
                                    (fast_channel_data_nibbles[4] << 2) | \
                                    (fast_channel_data_nibbles[3] & 0x3)

                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[4], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 4, ch1_error))
                        self.put_field_at(fast_channel_data_offsets[3], fast_channel_data_offsets[6], Decoder.FAST_CH2_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(2, ch2_value, 3, ch2_error))
                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, fast_ch2_bad_value_strings if ch1_error else fast_ch2_good_value_strings)
                    else:
                        # Two fast channels with 16-bit fast channel 1 and 8-bit fast channel 2
                        ch1_value = (fast_channel_data_nibbles[0] << 12) | \
                                    (fast_channel_data_nibbles[1] << 8) | \
                                    (fast_channel_data_nibbles[2] << 4) | \
                                    fast_channel_data_nibbles[3]

                        ch2_value = (fast_channel_data_nibbles[5] << 4) | fast_channel_data_nibbles[4]

                        self.put_field_at(fast_channel_data_offsets[0], fast_channel_data_offsets[4], Decoder.FAST_CH1_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(1, ch1_value, 4, ch1_error))
                        self.put_field_at(fast_channel_data_offsets[4], fast_channel_data_offsets[6], Decoder.FAST_CH2_VALUE_ANN_INDEX, Decoder.format_fast_channel_value(2, ch2_value, 2, ch2_error))
                        # error bits
                        self.put_field_at(fast_channel_error_flag_offsets[0], fast_channel_error_flag_offsets[1], Decoder.FAST_CH1_ERROR_ANN_INDEX, fast_ch1_bad_value_strings if ch1_error else fast_ch1_good_value_strings)
                        self.put_field_at(fast_channel_error_flag_offsets[1], fast_channel_error_flag_offsets[2], Decoder.FAST_CH2_ERROR_ANN_INDEX, fast_ch2_bad_value_strings if ch1_error else fast_ch2_good_value_strings)



            elif Sent.ProtocolState.CRC == self.state:
                self.wait_for_next_pulse()

                nibble = self.pulse_to_nibble()
                self.put_field(Decoder.NIBBLE_ANN_INDEX, [f'0x{nibble:01X}'])
                self.put_field(Decoder.CRC_ANN_INDEX, ['CRC'])

                self.crc_falling = self.pulse_falling1

                if Sent.PULSE_PAUSE_MODE_YES == pulse_pause_mode:
                    self.state = Sent.ProtocolState.PAUSE
                elif Sent.PULSE_PAUSE_MODE_NO == pulse_pause_mode:
                    self.state = Sent.ProtocolState.CALIBRATION
                else:
                    self.state = Sent.ProtocolState.NONE

                computed_crc = DataCrc.finalize(computed_crc)

                if not self.pulse_is_valid_nibble():
                    self.put_error(self.explain_bad_nibble())
                    has_frame_error = True
                elif computed_crc != nibble:
                    self.put_error(f'CRC Mismatch: 0x{computed_crc:X}')
                    has_frame_error = True

                if has_frame_error:
                    secure_sensor_prev_counter = None

                self.slow_protocol.on_frame_end(has_frame_error)

                has_frame_error = False
