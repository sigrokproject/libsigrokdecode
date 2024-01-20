##
# This file is part of the libsigrokdecode project.
##
# Copyright (C) 2020 Nie Guangze <guangze.nie@outlook.com>
##
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
##
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
##
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd

# define Enumerate for Frame Field
(INIT, SYNC, SSC, DATA, CRC, PP) = range(6)

# define List for CRC with 4 bits
crc4_list = [0, 13, 7, 10, 14, 3, 9, 4, 1, 12, 6, 11, 15, 2, 8, 5]


class SamplerateError(Exception):
    pass


class Decoder(srd.Decoder):
    api_version = 3
    id = 'sent'
    name = 'SENT'
    longname = 'SENT SAE J2716-2016'
    desc = 'Single Edge Nibble Transmission.'
    license = 'gplv2+'
    # input is raw sample data from line
    inputs = ['logic']
    outputs = []
    tags = ['Automotive']

    # Configure Option for Signal Channel selection
    channels = (
        {'id': 'data', 'name': 'Signal', 'desc': 'Line Index'},  # 0
    )

    # Configure Option for Decoding Setting
    options = (
        {'id': 'tick',
            'desc': 'Tick Time(in [3,90]) us:', 'default': 3.0},
        {'id': 'format', 'desc': 'Frame Format',
            'default': 'H.1', 'values': ('H.1', 'H.2', 'H.3', 'H.4', 'H.5', 'H.6', 'H.7')},
    )

    # Configure Decoding Annotations, annotation id & label
    annotations = (
        ('period', 'Period'),        # 0
        ('ticks', 'Ticks'),          # 1
        ('cal-sync', 'CS'),          # 2
        ('ssc', 'SS'),               # 3
        ('sd', 'DN'),                # 4
        ('crc', 'CRC'),              # 5
        ('pp', 'Pause-Pulse'),       # 6
        ('dv', 'Value'),             # 7
        ('fch', 'FChannel'),          # 8
    )

    # Configure Annotations grouping method, row id & label & annotation index
    annotation_rows = (
        ('nibble-period', 'Period', (0,)),              # at 1st row
        ('nibble-ticks', 'Ticks', (1,)),                # at 2nd row
        ('nibble-field', 'Field', tuple(range(2, 7))),  # at 3rd row
        ('nibble-value', 'Value', (7,)),                # at 4th row
        ('Fast-Channel', 'Fast Channel', (8,)),           # at 5th row
    )

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Method to initialize private variable
        """
        self.samplerate = None
        self.ss_block = None
        self.idx_nibble = None
        self.fieldState = INIT
        self.tickSample = 0
        self.period = 0
        self.ss_fch = self.se_fch = None
        self.data_num = None
        self.idx_ch1end = None
        self.idx_ch2end = None
        self.__fStr = None
        self.channel_val = None
        self.CheckSum = 0

    def metadata(self, key, value):
        """
        Method to read parameter value of analyser
        """
        if key == srd.SRD_CONF_SAMPLERATE:
            # get sampling rate in Hz
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def __putp(self, period_t):
        """
        Method to report period of Nibble Pulse
        """
        # Adjust granularity.
        if period_t == 0 or period_t >= 1:
            period_s = '%.1f s' % (period_t)
        elif period_t <= 1e-12:
            period_s = '%.1f fs' % (period_t * 1e15)
        elif period_t <= 1e-9:
            period_s = '%.1f ps' % (period_t * 1e12)
        elif period_t <= 1e-6:
            period_s = '%.1f ns' % (period_t * 1e9)
        elif period_t <= 1e-3:
            period_s = '%.1f us' % (period_t * 1e6)
        else:
            period_s = '%.1f ms' % (period_t * 1e3)

        self.put(self.ss_block, self.samplenum, self.out_ann, [0, [period_s]])

    def __putt(self, tickNum):
        """
        Method to report tick number of Nibble Pulse
        """
        self.put(self.ss_block, self.samplenum,
                 self.out_ann, [1, ['%d' % tickNum]])

    def __putv(self, data):
        """
        Method to report annotation for Nibble Pulse
        """
        self.put(self.ss_block, self.samplenum, self.out_ann, data)

    def __putc(self, data):
        """
        Method to report annotation for fast channel
        """
        self.put(self.ss_fch, self.se_fch, self.out_ann, data)

    def __get_field(self, tickNum):
        """
        Method to figure out field of current nibble in SENT Signal
        Support with and without PP field format
        """
        # calc. data value of nibble
        data = tickNum - 12

        if self.fieldState == INIT:
            # in INIT Field

            # check jump out condition
            if self.__check_SYNC_nibble(tickNum):
                # jump into SYNC State
                self.fieldState = SYNC
                # enter operation of SYNC
                self.__do_SYNC_entry()
            else:
                # during INIT
                # report field for INIT
                self.__putv([6, ['INIT']])

        elif self.fieldState == SYNC:
            # in SYNC Field

            # check jump out condition
            if self.__check_SYNC_nibble(tickNum):
                # jump into SYNC State
                self.fieldState = SYNC
                # enter operation of SYNC
                self.__do_SYNC_entry()

            elif self.__check_Data_nibble(tickNum):
                # jump into SSC State
                self.fieldState = SSC
                # report field and data for SSC
                self.__putv([3, ['SSC']])
                self.__putv([7, ['0x%X'%data]])
                # intialize Check Sum
                self.CheckSum = 5
            else:
                # get Abnormal Nibble
                self.fieldState = INIT
                # enter Init State for unexpected nibble
                self.__do_Abnormal_entry()

        elif self.fieldState == SSC:
            # in SSC Field

            # check jump out condition
            if self.__check_Data_nibble(tickNum):
                # jump into Data State
                self.fieldState = DATA
                self.idx_nibble = 0
                self.ss_fch = self.ss_block
                self.channel_val = data
                # report field and data for DATA
                self.idx_nibble += 1
                self.__putv([7, ['0x%X'%data]])
                self.__putv([4, ['D_%d'%self.idx_nibble]])
                # calc check sum
                self.CheckSum = int(data) ^ int(crc4_list[self.CheckSum])
            else:
                # get Abnormal Nibble
                self.fieldState = INIT
                # enter Init State for unexpected nibble
                self.__do_Abnormal_entry()

        elif self.fieldState == DATA:
            # in DATA Field

            # check jump out condition
            if not self.__check_Data_nibble(tickNum):
                # get Abnormal Nibble
                self.fieldState = INIT
                # enter Init State for unexpected nibble
                self.__do_Abnormal_entry()
            elif self.data_num == self.idx_nibble:
                # get CRC Nibble
                self.fieldState = CRC
                # report field and data for CRC
                self.__putv([5, ['CRC']])
                self.__putv([7, ['0x%X'%data]])

                # calc check sum
                self.CheckSum = int(data) ^ int(crc4_list[self.CheckSum])
                # report check sum
                if self.CheckSum == 0:
                    self.__putv([8, ['Pass']])
                else:
                    self.__putv([8, ['Fail']])
            else:
                # during Data Field
                # report field and data for DATA
                self.idx_nibble += 1
                self.__putv([4, ['D_%d'%self.idx_nibble]])
                self.__putv([7, ['0x%X'%data]])

                # calc check sum
                self.CheckSum = int(data) ^ int(crc4_list[self.CheckSum])

                # calc channel value in Decimal
                if self.idx_nibble <= self.idx_ch1end or self.__fStr == 'H.4':
                    # calc for channel 1
                    if self.__fStr == 'H.3':
                        self.channel_val *= 8
                    else:
                        self.channel_val *= 16
                    self.channel_val += data
                elif self.idx_ch2end and (self.idx_ch1end < self.idx_nibble <= self.idx_ch2end):
                    # calc for channel 2
                    if self.__fStr == 'H.6':
                        self.channel_val += data * \
                            pow(16, self.idx_nibble - self.idx_ch1end)
                    else:
                        self.channel_val += data * \
                            pow(16, self.idx_nibble - self.idx_ch1end - 1)
                else:
                    pass

                # check value for Fast Channel
                if self.idx_nibble == self.idx_ch1end:
                    # report value in Fast Channel 1
                    if self.__fStr == 'H.6':
                        self.se_fch = self.samplenum - round(self.period / 2)
                        self.channel_val = round(self.channel_val / 4)
                    else:
                        self.se_fch = self.samplenum
                    self.__putc([8, ['CH1:%d'%self.channel_val]])
                    self.ss_fch = self.se_fch
                    if self.__fStr == 'H.6':
                        self.channel_val = round(data % 4) * 4
                    else:
                        self.channel_val = 0
                elif self.idx_nibble == self.idx_ch2end:
                    # report value in Fast Channel 2
                    self.se_fch = self.samplenum
                    if self.__fStr == 'H.6':
                        self.channel_val = round(self.channel_val / 4)
                    self.__putc([8, ['CH2:%d'%self.channel_val]])
                    self.ss_fch = self.se_fch
                    self.channel_val = 0
                elif self.idx_nibble == self.data_num and self.__fStr == 'H.4':
                    # report Inverted Copy of CH1 MSN
                    self.se_fch = self.samplenum
                    self.__putc([8, ['~D_1:%d'%self.channel_val]])
                else:
                    # do nothing
                    pass

        elif self.fieldState == CRC:
            # in CRC Field

            # check jump out condition
            if self.__check_SYNC_nibble(tickNum):
                # get Sync Nibble
                self.fieldState = SYNC
                self.__do_SYNC_entry()
            else:
                # get Pause Nibble
                self.fieldState = INIT
                # report field for PP
                self.__putv([6, ['PP']])

        else:
            # get Unexpected Filed
            raise Exception("Get Unkown Field")

    def __check_SYNC_nibble(self, tickNum):
        """
        Method to check whether current nibble is SYNC Nibble
        """
        return 45 <= tickNum <= 67

    def __check_Data_nibble(self, tickNum):
        """
        Method to check whether current nibble is SSC\\Data\\CRC Nibble
        """
        return 12 <= tickNum <= 27

    def __do_Abnormal_entry(self):
        """
        Method to process unexpected nibble
        """
        self.__putv([6, ['ERR']])

    def __do_SYNC_entry(self):
        """
        Method to do SYNC_entry Operation
        """
        # update self.tickSample by Sync. Nibble Pulse
        self.tickSample = round(self.period / 56)
        # report field and data for SYNC
        self.__putv([2, ['Sync./Cali.']])
        self.__putv(
            [7, ['tick:%2.1fus' % (self.tickSample / self.samplerate * 1e6)]])

    def decode(self):
        """
        Mehtod to decode signal
        """
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        if float(self.options['tick']) < 3 or float(self.options['tick']) > 90:
            raise Exception('Clock Tick Time must in [3, 90] us.')

        # get Frame Format
        self.__fStr = self.options['format']
        if self.__fStr == 'H.1' or self.__fStr == 'H.5':
            self.data_num = 6
            self.idx_ch1end = 3
            self.idx_ch2end = 6
        elif self.__fStr == 'H.2':
            self.data_num = 3
            self.idx_ch1end = 3
        elif self.__fStr == 'H.3':
            self.data_num = 4
            self.idx_ch1end = 4
        elif self.__fStr == 'H.4':
            self.data_num = 6
            self.idx_ch1end = 3
            self.idx_ch2end = 5
        elif self.__fStr == 'H.6' or self.__fStr == 'H.7':
            self.data_num = 6
            self.idx_ch1end = 4
            self.idx_ch2end = 6
        else:
            raise Exception('Get unexpected Frame Format')

        # set inital sample number in tick
        self.tickSample = float(self.options['tick']) * self.samplerate * 1e-6

        # Wait for an "active" edge (depends on config).
        self.wait({0: 'f'})

        # Keep getting samples for the period's falling edges.
        # At the same time that last sample starts the next period.
        while True:

            # Get the next two edges. Setup some variables that get
            # referenced in the calculation and in put() routines.
            start_samplenum = self.samplenum
            self.wait({0: 'f'})
            # end_samplenum = self.samplenum
            self.ss_block = start_samplenum

            # Calculate the period, ticks Number.
            self.period = self.samplenum - start_samplenum
            tickNum = round(self.period / self.tickSample)

            # Report the period in units of time.
            period_t = float(self.period / self.samplerate)

            # Report properties of current nibble pulse
            self.__putp(period_t)
            self.__putt(tickNum)

            # decode for format with and without PP Field
            self.__get_field(tickNum)
