##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2025 Vincent Hamp <hamp@zimo.at>
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
from common.srdhelper import SrdIntEnum
from .lists import *


class ChannelError(Exception):
    pass


class SamplerateError(Exception):
    pass


Pin = SrdIntEnum.from_str('Pin', 'P N BIDI')
Ann = SrdIntEnum.from_str(
    'Ann',
    'TIMING_VALID TIMING_INVALID '
    'BIT '
    'BYTE '
    'ERROR '
    'FRAME_PREAMBLE FRAME_START_BIT FRAME_ADDRESS FRAME_INSTR FRAME_CHECKSUM FRAME_END_BIT '
    'SERVICE_INSTR '
    'BROADCAST_ADDR BROADCAST_INSTR '
    'LOCO_ADDR LOCO_INSTR '
    'ACCY_ADDR ACCY_INSTR '
    'DATA_TRANSFER_ADDR DATA_TRANSFER_INSTR '
    'AUTOMATIC_LOGON_ADDR AUTOMATIC_LOGON_INSTR '
    'IDLE_ADDR IDLE_INSTR '
    'BIDI_BIT_START BIDI_BIT BIDI_BIT_STOP '
    'BIDI_ENC_BYTE '
    'BIDI_DEC_BYTE '
    'BIDI_ERROR '
    'BIDI_FRAME_TCS BIDI_FRAME_CH BIDI_FRAME_TCE '
    'BIDI_ID BIDI_DATA '
    'HIGHLIGHT_ADDR HIGHLIGHT_INSTR ',
)


class Decoder(srd.Decoder):
    api_version = 3
    id = 'dcc'
    name = 'DCC'
    longname = 'Digital Command Control'
    desc = 'Digital operation of model railways'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = ['out']
    tags = ['Embedded']
    optional_channels = (
        {
            'id': 'p',
            'name': 'P',
            'desc': 'P Track'
        },
        {
            'id': 'n',
            'name': 'N',
            'desc': 'N Track'
        },
        {
            'id': 'bidi',
            'name': 'BIDI',
            'desc': 'RailCom'
        },
    )
    options = (
        {
            'id': 'initial_mode',
            'desc': 'Initial Mode',
            'default': 'Operations',
            'values': ('Operations', 'Service')
        },
        {
            'id': 'min_preamble_bits',
            'desc': 'Minimum Preamble Bits',
            'default': 10,
            'values': tuple(range(10, 12 + 1))
        },
        {
            'id': 'min_bit1',
            'desc': 'Minimum Bit1 Duration',
            'default': 52,
            'values': tuple(range(52, 56 + 1))
        },
        {
            'id': 'max_bit1',
            'desc': 'Maximum Bit1 Duration',
            'default': 64,
            'values': tuple(range(60, 64 + 1))
        },
        {
            'id': 'min_bit0',
            'desc': 'Minimum Bit0 Duration',
            'default': 90,
            'values': tuple(range(90, 97 + 1))
        },
        {
            'id': 'max_bit0',
            'desc': 'Maximum Bit0 Duration',
            'default': 119,
            'values': tuple(range(114, 119 + 1))
        },
        {
            'id': 'tts1',
            'desc': 'BiDi Channel1 Start',
            'default': BIDI_TTS1,
            'values': tuple(range(BIDI_TCS_MAX, BIDI_TTS1 + 1))
        },
        {
            'id': 'ttc2',
            'desc': 'BiDi Channel2 End',
            'default': BIDI_TTC2,
            'values': tuple(range(BIDI_TTC2, BIDI_TCE_MAX + 1))
        },
        {
            'id': 'cv29_1',
            'desc': 'CV29:1',
            'default': 1,
            'values': (1, 0)
        },
        {
            'id': 'debounce',
            'desc': 'Debounce [µs]',
            'default': 4,
            'values': tuple(range(1, 5 + 1))
        },
        {
            'id': 'highlight_address',
            'desc': 'Highlight Address',
            'default': ''
        },
        {
            'id':
            'highlight_instruction',
            'desc':
            'Highlight Instruction',
            'default':
            '',
            'values': ('', 'Decoder Control', 'Consist Control',
                       'Advanced Operations', 'Speed and Direction',
                       'Function Group', 'Feature Expansion', 'CV Access')
        },
        {
            'id': 'empty_new_line_after_packets_annotation',
            'desc': 'Empty \\n after Packets',
            'default': 'No',
            'values': ('No', 'Yes')
        },
    )
    annotations = (
        ('timing_valid', 'Valid'),
        ('timing_invalid', 'Invalid'),  #
        ('bit', 'Bit'),  #
        ('byte', 'Byte'),  # 
        ('error', 'Error'),  #
        ('frame_preamble', 'Preamble'),
        ('frame_startbit', 'Start Bit'),
        ('frame_address', 'Address'),
        ('frame_instruction', 'Instruction'),
        ('frame_checksum', 'Checksum'),
        ('frame_endbit', 'End Bit'),
        ('service_instruction', 'Instruction'),  # 
        ('broadcast_address', 'Address'),
        ('broadcast_instr', 'Instruction'),  # 
        ('loco_address', 'Address'),
        ('loco_instr', 'Instruction'),  #
        ('accessory_address', 'Address'),
        ('accessory_instr', 'Instruction'),  #
        ('data_transfer_address', 'Address'),
        ('data_transfer_instr', 'Instruction'),  #
        ('automatic_logon_address', 'Address'),
        ('automatic_logon_instr', 'Instruction'),  #
        ('idle_address', 'Address'),
        ('idle_instr', 'Instruction'),  #
        ('bidi_bit_start', 'Start Bit'),
        ('bidi_bit', 'Bit'),
        ('bidi_bit_stop', 'Stop Bit'),  #
        ('bidi_enc_byte', 'Byte'),  #
        ('bidi_dec_byte', 'Byte'),  #
        ('bidi_error', 'Error'),  #
        ('bidi_frame_tcs', 'Cutout Start'),
        ('bidi_frame_ch', 'Channel'),
        ('bidi_frame_tce', 'Cutout End'),
        ('bidi_id', 'Id'),
        ('bidi_data', 'Data'),  #
        ('highlight_address', 'Address'),
        ('highlight_instr', 'Instruction'))
    annotation_rows = (
        ('timings', 'Timings', (Ann.TIMING_VALID, Ann.TIMING_INVALID)),
        ('bits', 'Bits', (Ann.BIT, )),
        ('bytes', 'Bytes', (Ann.BYTE, )),
        ('errors', 'Errors', (Ann.ERROR, )),
        ('frames', 'Frames',
         (Ann.FRAME_PREAMBLE, Ann.FRAME_START_BIT, Ann.FRAME_ADDRESS,
          Ann.FRAME_INSTR, Ann.FRAME_CHECKSUM, Ann.FRAME_END_BIT)),
        ('service_packets', 'Service Packets', (Ann.SERVICE_INSTR, )),
        ('broadcast_packets', 'Broadcast Packets', (Ann.BROADCAST_ADDR,
                                                    Ann.BROADCAST_INSTR)),
        ('loco_packets', 'Loco Packets', (Ann.LOCO_ADDR, Ann.LOCO_INSTR)),
        ('accessory_packets', 'Accessory Packets', (Ann.ACCY_ADDR,
                                                    Ann.ACCY_INSTR)),
        ('data_transfer_packets', 'Data transfer Packets',
         (Ann.DATA_TRANSFER_ADDR, Ann.DATA_TRANSFER_INSTR)),
        ('automatic_logon_packets', 'Automatic logon Packets',
         (Ann.AUTOMATIC_LOGON_ADDR, Ann.AUTOMATIC_LOGON_INSTR)),
        ('idle_packets', 'Idle Packets', (Ann.IDLE_ADDR, Ann.IDLE_INSTR)),
        ('bidi_bits', 'BiDi Bits', (Ann.BIDI_BIT_START, Ann.BIDI_BIT,
                                    Ann.BIDI_BIT_STOP)),
        ('bidi_encoded_bytes', 'BiDi Encoded Bytes', (Ann.BIDI_ENC_BYTE, )),
        ('bidi_decoded_bytes', 'BiDi Decoded Bytes', (Ann.BIDI_DEC_BYTE, )),
        ('bidi_errors', 'BiDi Errors', (Ann.BIDI_ERROR, )),
        ('bidi_frames', 'BiDi Frames', (Ann.BIDI_FRAME_TCS, Ann.BIDI_FRAME_CH,
                                        Ann.BIDI_FRAME_TCE)),
        ('bidi_datagrams', 'BiDi Datagrams', (Ann.BIDI_ID, Ann.BIDI_DATA)),
        ('highlights', 'Highlights', (Ann.HIGHLIGHT_ADDR,
                                      Ann.HIGHLIGHT_INSTR)),
    )
    binary = (('csv', 'CSV file'), )

    def __init__(self):
        self.samplerate = None
        self.bidi_app = {}  # Dict for received BiDi datagrams
        self.reset()

    def reset(self):
        self.reset_dcc()
        self.reset_bidi()

    def reset_dcc(self):
        '''Reset DCC variables.'''
        self.state = 'PREAMBLE'  # DCC state
        self.p = -1  # Pin P state
        self.n = -1  # Pin N state

        # Inputs
        self.dcc_ss = [self.samplenum] if hasattr(self, 'samplenum') else []
        self.dcc_hbit_count = 0  # DCC halfbit count
        self.dcc_hbits = []  # DCC halfbits

        # Outputs
        self.dcc_bytes = bytearray()  # DCC bytes
        self.dcc_addr = -1  # DCC address
        self.dcc_addr_type = ''  # DCC address type

    def reset_bidi(self):
        '''Reset BiDi variables.'''
        # Store data from last packet as cutout is context sensitive
        self.last_dcc_ss = []  # Last DCC samplenums
        self.last_dcc_bytes = bytearray()  # Last DCC bytes
        self.last_dcc_addr = -1  # Last DCC address
        self.last_dcc_addr_type = ''  # Last DCC address type

        self.bidi = -1  # Pin BIDI state

        # Inputs
        self.bidi_edges_ss = []  # List of BiDi bit edge samplenums
        self.bidi_states = []  # List of Pin BIDI states

        # Outputs
        self.bidi_bytes_ss = []  # List of BiDi bytes startbit samplenums
        self.bidi_enc_bytes = bytearray()  # List of encoded BiDi bytes
        self.bidi_dec_bytes = bytearray()  # List of decoded BiDi bytes

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        '''Read and verify options.'''
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
        self.service_mode = True if self.options[
            'initial_mode'] == 'Service' else False
        self.min_preamble_bits = self.options['min_preamble_bits']
        self.min_bit1 = self.options['min_bit1']
        self.max_bit1 = self.options['max_bit1']
        self.min_bit0 = self.options['min_bit0']
        self.max_bit0 = self.options['max_bit0']
        self.tts1 = self.options['tts1']
        self.ttc2 = self.options['ttc2']
        self.cv29_1 = self.options['cv29_1']
        self.debounce = self.options['debounce']
        try:
            self.highlight_addr = int(self.options['highlight_address'], 0)
        except:
            self.highlight_addr = None
        self.highlight_instr = self.options['highlight_instruction']
        self.empty_new_line_after_packets_annotation = '\n' if self.options[
            'empty_new_line_after_packets_annotation'] == 'Yes' else ''
        csv_header = 'timestamp,dcc,bidi\n' if self.has_channel(
            Pin.BIDI) else 'timestamp,dcc\n'
        self.put(0, 0, self.out_binary, [0, csv_header.encode('utf-8')])

    def ss_es2us(self, startsample, endsample):
        '''Get difference between start- and endsample in µs.
        
        :param startsample: Startsample
        :type startsample: int
        :param endsample: Endsample
        :type endsample: int
        :return: Difference between start- and endsample in µs
        :rtype: int
        '''
        return round(1e6 * (endsample - startsample) / self.samplerate)

    def ss_us2es(self, startsample, us):
        '''Get endsample from startsample and µs.
        
        :param startsample: Startsample
        :type startsample: int
        :param us: Microseconds to add to startsample
        :type us: int or float
        :return: Endsample
        :rtype: int
        '''
        return round(startsample + (us * self.samplerate) / 1e6)

    def us2hbit(self, us):
        '''Get DCC halfbit from µs.
        
        :param us: Microseconds
        :type us: int
        :return: Bit
        :rtype: None or int
        '''
        if us < self.debounce:
            return None
        elif self.min_bit1 <= us <= self.max_bit1:
            return 1
        elif self.min_bit0 <= us <= self.max_bit0:
            return 0
        else:
            return -1

    def ss_es2hbit(self, startsample, endsample):
        '''Get DCC halfbit from start- and endsample.
        
        :param startsample: Startsample
        :type startsample: int
        :param endsample: Endsample
        :type endsample: int
        :return: Bit
        :rtype: None or int
        '''
        return self.us2hbit(self.ss_es2us(startsample, endsample))

    def ss_es2bidi_bits_passed(self, startsample, endsample):
        '''Calculate how many BiDi UART bits fit between start- and endsample.
        
        :param startsample: Startsample
        :type startsample: int
        :param endsample: Endsample
        :type endsample: int
        :return: Number of UART bits
        :rtype: int
        '''
        us = self.ss_es2us(startsample, endsample)
        return round(us / 4)

    def get_ann_instr(self):
        '''Convenience getter for instruction annotation.
        
        :return: Annotation enumeration value for current instruction
        :rtype: SrdIntEnum
        '''
        if self.service_mode:
            return Ann.SERVICE_INSTR
        elif self.dcc_addr_type == 'BROADCAST':
            return Ann.BROADCAST_INSTR
        elif self.dcc_addr_type in ('BASIC_LOCO', 'EXT_LOCO'):
            return Ann.LOCO_INSTR
        elif self.dcc_addr_type in ('BASIC_ACCY', 'EXT_ACCY'):
            return Ann.ACCY_INSTR
        elif self.dcc_addr_type == 'DATA_TRANSFER':
            return Ann.DATA_TRANSFER_INSTR
        elif self.dcc_addr_type == 'AUTOMATIC_LOGON':
            return Ann.AUTOMATIC_LOGON_INSTR
        elif self.dcc_addr_type == 'IDLE':
            return Ann.IDLE_INSTR
        else:
            return Ann.SERVICE_INSTR

    def get_dcc_byte_at(self, i):
        '''Convert halfbits to DCC byte at index.
        
        :param i: Index
        :type i: int
        :return: Byte at i
        :rtype: int
        '''
        return (self.dcc_hbits[i + 0 * 2] << 7 | self.dcc_hbits[i + 1 * 2] << 6
                | self.dcc_hbits[i + 2 * 2] << 5
                | self.dcc_hbits[i + 3 * 2] << 4
                | self.dcc_hbits[i + 4 * 2] << 3
                | self.dcc_hbits[i + 5 * 2] << 2
                | self.dcc_hbits[i + 6 * 2] << 1
                | self.dcc_hbits[i + 7 * 2] << 0)

    def instr_feature_expansion_fxx_fyy_annotate_dcc_helper(self, i, xx, yy):
        '''Convenience helper for annotating the 8x 'Feature Extension - FXX-FYY' instructions.'''
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Feature Expansion - F{}-F{}'.format(xx, yy)]
        ])
        i += BYTE_HBIT
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        f = [(self.dcc_bytes[-1] >> bit) & 0b1 for bit in range(8)]
        fstr = ' | '.join('F{}={}'.format(xx + i, f[i]) for i in range(8))
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), [fstr]])
        i = self.annotate_dcc_byte(i)
        return i

    def bidi_annotate_app_adr_helper(self, i):
        '''Convenience helper for annotating 'app:adr_high' and 'app_adr_low' datagrams.'''
        if 'adr_high' in self.bidi_app and 'adr_low' in self.bidi_app:
            if self.bidi_app['adr_high'] == 0:
                addr = self.bidi_app['adr_low']
                self.put(
                    self.bidi_bytes_ss[i + 1],
                    self.ss_us2es(self.bidi_bytes_ss[i + 1],
                                  10 * BIDI_BIT_TIME), self.out_ann,
                    [Ann.BIDI_DATA, ['Basic Loco={}'.format(addr)]])
            elif self.bidi_app['adr_high'] == 0b01100000:
                r = self.bidi_app['adr_low'] >> 7
                addr = self.bidi_app['adr_low'] & 0x7F
                self.put(
                    self.bidi_bytes_ss[i + 1],
                    self.ss_us2es(self.bidi_bytes_ss[i + 1],
                                  10 * BIDI_BIT_TIME), self.out_ann,
                    [
                        Ann.BIDI_DATA,
                        ['Reversed={} | Consist={}'.format(r, addr)]
                    ])
            else:
                addr = (self.bidi_app['adr_high'] << 8
                        | self.bidi_app['adr_low']) & 0x3FFF
                self.put(
                    self.bidi_bytes_ss[i + 1],
                    self.ss_us2es(self.bidi_bytes_ss[i + 1],
                                  10 * BIDI_BIT_TIME), self.out_ann,
                    [Ann.BIDI_DATA, ['Extended Loco={}'.format(addr)]])
        else:
            self.put(
                self.bidi_bytes_ss[i + 1],
                self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                self.out_ann, [Ann.BIDI_DATA, ['?']])

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        elif self.samplerate < 1e6:
            raise SamplerateError('DCC needs a samplerate of at least 1MS/s')

        if not self.has_channel(Pin.P) and not self.has_channel(Pin.N):
            raise ChannelError('Need at least one of P or N pins.')

        # Wait until P != N (this is safe as state of not assigned channels is 255)
        while self.p == self.n:
            self.p, self.n, self.bidi = self.wait()
            self.dcc_ss = [self.samplenum]

        # Wait for rise or fall on every track pin
        dcc_cond = [{Pin.P: 'e'}, {Pin.N: 'e'}]
        # Wait for rise or fall on BiDi pin
        bidi_cond = {Pin.BIDI: 'e'}

        while True:
            p, n, bidi = self.wait(dcc_cond + [bidi_cond])

            # DCC
            if self.matched[0] == True or self.matched[1] == True:
                self.decode_dcc()
                self.p = p
                self.n = n

            # BiDi
            if self.matched[2] == True:
                self.decode_bidi(bidi)
                self.bidi = bidi

            # BiDi cutout end after last valid DCC packet (write CSV here before resetting!)
            if self.last_dcc_ss and self.samplenum > self.ss_us2es(
                    self.last_dcc_ss[-1], BIDI_TCE_MAX):
                self.annotate_bidi()
                self.csv_writerow()
                self.reset_bidi()

    def decode_dcc(self):
        '''Decode DCC.

        'annotate_and_reset_dcc' is called in both success and failure cases.
        '''
        hbit = self.ss_es2hbit(self.dcc_ss[-1], self.samplenum)
        if hbit is None:
            return
        self.dcc_hbits.append(hbit)
        self.dcc_ss.append(self.samplenum)
        # Error, invalid bit time
        if hbit == -1:
            return self.annotate_and_reset_dcc()
        # Count ones until start bit 0
        elif self.state == 'PREAMBLE':
            if hbit == 1:
                self.dcc_hbit_count += 1
            elif self.dcc_hbit_count >= self.min_preamble_bits * 2:
                self.state = 'START_BIT'
            else:
                return self.annotate_and_reset_dcc()
        # Everything but another 0 is an error
        elif self.state == 'START_BIT':
            if hbit == 0:
                self.dcc_hbit_count = 0
                self.state = 'DATA'
            else:
                return self.annotate_and_reset_dcc()
        # Collect 8 bits (16 hbits), check that they come in pairs
        elif self.state == 'DATA':
            self.dcc_hbit_count += 1
            if self.dcc_hbit_count >= BYTE_HBIT:
                self.dcc_hbit_count = 0
                self.state = 'END_BIT'
            # Halfbits must come in pairs
            elif (self.dcc_hbit_count & 0b1 == 0) and (self.dcc_hbits[-2]
                                                       != self.dcc_hbits[-1]):
                return self.annotate_and_reset_dcc()
        # 0 means more data, 1 means end
        elif self.state == 'END_BIT':
            if hbit == 0:
                self.state = 'START_BIT'
            else:
                self.dcc_hbit_count += 1
                if self.dcc_hbit_count >= 2:
                    return self.annotate_and_reset_dcc()

    def annotate_and_reset_dcc(self):
        self.annotate_dcc()
        self.reset_dcc()

    def annotate_dcc(self):
        '''Annotate DCC packet, then store context for eventual cutout.'''
        # Dont litter code with range checks
        try:
            self.annotate_dcc_timings_bits_and_errors()
            i = 0
            i = self.annotate_dcc_preamble(i)
            if self.service_mode:
                i = self.annotate_dcc_service_mode(i)
            else:
                i = self.annotate_dcc_operations_mode(i)
            i = self.annotate_dcc_instr_unknown(i)
            i = self.annotate_dcc_checksum(i)

            # Store context
            self.last_dcc_bytes = self.dcc_bytes
            self.last_dcc_ss = self.dcc_ss
            self.last_dcc_addr = self.dcc_addr
            self.last_dcc_addr_type = self.dcc_addr_type
        except:
            pass

    def annotate_dcc_byte(self, i):
        '''Annotate DCC byte.'''
        byte = self.get_dcc_byte_at(i)
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [Ann.BYTE, ['0x{:02X}'.format(byte)]])
        return i + BYTE_HBIT

    def annotate_frame_address(self, i):
        '''Annotate DCC frame address.'''
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [Ann.FRAME_ADDRESS, ['Address', 'Addr', 'A']])
        return i + BYTE_HBIT

    def annotate_frame_instr(self, i):
        '''Annotate DCC frame instruction.'''
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [Ann.FRAME_INSTR, ['Instruction', 'Instr', 'I']])
        return i + BYTE_HBIT

    def annotate_dcc_timings_bits_and_errors(self):
        # The preamble might be odd, so get the second 1-bit and first 0-bit to
        # determine when to start looking for matching hbits
        second_1 = self.dcc_hbits.index(1, self.dcc_hbits.index(1) + 1)
        first_0 = self.dcc_hbits.index(0)
        '''Annotate DCC timings, bits and errors.'''
        for i in range(0, len(self.dcc_hbits), 1):
            us = self.ss_es2us(self.dcc_ss[i], self.dcc_ss[i + 1])
            if i == 0 and BIDI_TCS_MIN <= us <= BIDI_TCS_MAX:
                self.put(self.dcc_ss[i], self.dcc_ss[i + 1], self.out_ann,
                         [Ann.TIMING_VALID, ['{}µs'.format(us),
                                             str(us)]])
            elif i == 0 and (BIDI_TCE_MIN - BIDI_TCS_MAX) <= us <= (
                    BIDI_TCE_MAX - BIDI_TCS_MIN):
                self.put(self.dcc_ss[i], self.dcc_ss[i + 1], self.out_ann, [
                    Ann.TIMING_VALID,
                    ['{}µs (cutout)'.format(us), '{}µs'.format(us)]
                ])
            elif i == 0 and BIDI_TCE_MIN <= us <= BIDI_TCE_MAX + self.max_bit0:
                self.put(self.dcc_ss[i], self.dcc_ss[i + 1], self.out_ann, [
                    Ann.TIMING_VALID,
                    ['{}µs (maybe cutout)'.format(us), '{}µs'.format(us)]
                ])
            else:
                ann = Ann.TIMING_INVALID if self.us2hbit(
                    us) == -1 else Ann.TIMING_VALID
                self.put(self.dcc_ss[i], self.dcc_ss[i + 1], self.out_ann,
                         [ann, ['{}µs'.format(us), str(us)]])
                if i >= second_1 and (i - first_0) & 0b1:
                    hb0 = self.dcc_hbits[i - 1]
                    hb1 = self.dcc_hbits[i]
                    if hb0 == hb1:
                        self.put(self.dcc_ss[i - 1],
                                 self.dcc_ss[i - 1 + BIT_HBIT], self.out_ann,
                                 [Ann.BIT, [str(self.dcc_hbits[i])]])
                    else:
                        self.put(self.dcc_ss[i - 1],
                                 self.dcc_ss[i - 1 + BIT_HBIT], self.out_ann,
                                 [Ann.ERROR, ['Invalid Bit']])

    def annotate_dcc_preamble(self, i):
        '''Annotate DCC preamble.'''
        i = self.dcc_hbits.index(0)
        if i == 0:
            return 0
        self.put(self.dcc_ss[0], self.dcc_ss[i], self.out_ann,
                 [Ann.FRAME_PREAMBLE, ['Preamble', 'P']])
        return i

    def annotate_dcc_service_mode(self, i):
        '''Annotate DCC service mode.'''
        first_byte = self.get_dcc_byte_at(i + BIT_HBIT)
        if first_byte == 0 or (first_byte & 0xF0) != 0b01110000:
            self.service_mode = first_byte != 0  # Leave service mode if anything but reset
            return self.annotate_dcc_operations_mode(i)
        else:
            i = self.annotate_dcc_frame_start_bit(i)
            self.dcc_bytes.append(first_byte)
            i = self.annotate_dcc_instr_cv_access_long_form(i)
        return i

    def annotate_dcc_operations_mode(self, i):
        '''Annotate DCC operations mode.'''
        i, self.dcc_addr, self.dcc_addr_type = self.annotate_dcc_address(i)
        i = self.annotate_dcc_instr(i)
        return i

    def annotate_dcc_frame_start_bit(self, i):
        '''Annotate DCC frame start bit.'''
        self.put(self.dcc_ss[i], self.dcc_ss[i + BIT_HBIT], self.out_ann,
                 [Ann.FRAME_START_BIT, ['Start Bit', 'Start', 'S']])
        return i + BIT_HBIT

    def annotate_dcc_frame_endbit(self, i):
        '''Annotate DCC frame end bit and add empty \\n in case 'empty_new_line_after_packet' option is used.'''
        self.put(self.dcc_ss[i], self.dcc_ss[i + BIT_HBIT], self.out_ann,
                 [Ann.FRAME_END_BIT, ['End Bit', 'End', 'E']])
        return i + BIT_HBIT

    def annotate_dcc_address(self, i):
        '''Annotate and decode DCC address.
        
        :param i: Index
        :type i: int
        :return: Tuple of index after annotation, DCC address and DCC address type
        :rtype: tuple[int, int, str]
        '''
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_address(i)
        ss = self.dcc_ss[i]
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)

        # Broadcast address
        if self.dcc_bytes[0] == 0:
            self.put(ss, self.dcc_ss[i], self.out_ann,
                     [Ann.BROADCAST_ADDR, ['Broadcast', 'B']])
            return (i, 0, 'BROADCAST')

        # Basic loco addresses 1-127
        elif self.dcc_bytes[0] <= 127:
            addr = self.dcc_bytes[0]
            anns = [
                'Basic Loco={}'.format(addr), 'Loco={}'.format(addr),
                '{}'.format(addr)
            ]
            self.put(ss, self.dcc_ss[i], self.out_ann, [Ann.LOCO_ADDR, anns])
            if addr == self.highlight_addr:
                self.put(ss, self.dcc_ss[i], self.out_ann,
                         [Ann.HIGHLIGHT_ADDR, anns])
            return (i, self.dcc_bytes[0], 'BASIC_LOCO')

        # Basic and extended accessory addresses 0-2047
        elif self.dcc_bytes[0] <= 191:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_address(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            i = self.annotate_dcc_byte(i)
            a7_2 = (self.dcc_bytes[0] & 0x3F) << 2
            a10_8 = (~self.dcc_bytes[1] & 0x70) << 4
            a1_0 = (self.dcc_bytes[1] >> 1) & 0x03
            addr = a10_8 | a7_2 | a1_0
            is_basic = self.dcc_bytes[1] & 0x80 or (self.dcc_bytes[1]
                                                    & 0b10000001) == 0
            fstr = 'Basic Accessory' if is_basic else 'Extended Accessory'
            anns = [
                '{}={}'.format(fstr, addr), 'Accessory={}'.format(addr),
                '{}'.format(addr)
            ]
            is_nop = (self.dcc_bytes[1] & 0b10001000) == 0b00001000
            # This is so god damn stupid... don't annotate basic accessories and NOPs yet -.-
            if not is_basic and not is_nop:
                self.put(ss, self.dcc_ss[i], self.out_ann,
                         [Ann.ACCY_ADDR, anns])
            if addr == self.highlight_addr:
                self.put(ss, self.dcc_ss[i], self.out_ann,
                         [Ann.HIGHLIGHT_ADDR, anns])
            return (i, addr, 'BASIC_ACCY' if is_basic else 'EXT_ACCY')

        # Extended loco addresses 1-10239
        elif self.dcc_bytes[0] <= 231:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_address(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            i = self.annotate_dcc_byte(i)
            a13_8 = (self.dcc_bytes[0] & 0x3F) << 8
            a7_0 = self.dcc_bytes[1]
            addr = a13_8 | a7_0
            anns = ['Extended Loco={}'.format(addr), 'Loco={}'.format(addr)]
            self.put(ss, self.dcc_ss[i], self.out_ann, [
                Ann.LOCO_ADDR,
                [
                    'Extended Loco={}'.format(addr), 'Loco={}'.format(addr),
                    '{}'.format(addr)
                ]
            ])
            if addr == self.highlight_addr:
                self.put(ss, self.dcc_ss[i], self.out_ann,
                         [Ann.HIGHLIGHT_ADDR, anns])
            return (i, addr, 'EXT_LOCO')

        # Reserved addresses
        elif self.dcc_bytes[0] <= 252:
            self.put(ss, self.dcc_ss[i], self.out_ann,
                     [Ann.RESERVED_ADDRESS, ['Reserved', 'R']])
            return (i, self.dcc_bytes[0], 'RESERVED')

        # Data transfer address
        elif self.dcc_bytes[0] <= 253:
            self.put(ss, self.dcc_ss[i], self.out_ann,
                     [Ann.DATA_TRANSFER_ADDR, ['Data Transfer', 'DT']])
            return (i, self.dcc_bytes[0], 'DATA_TRANSFER')

        # Automatic logon address
        elif self.dcc_bytes[0] <= 254:
            self.put(ss, self.dcc_ss[i], self.out_ann,
                     [Ann.AUTOMATIC_LOGON_ADDR, ['Automatic Logon', 'Logon']])
            return (i, self.dcc_bytes[0], 'AUTOMATIC_LOGON')

        # Idle
        else:
            self.put(ss, self.dcc_ss[i], self.out_ann,
                     [Ann.IDLE_ADDR, ['Idle']])
            return (i, self.dcc_bytes[0], 'IDLE')

    def annotate_dcc_instr(self, i):
        '''Annotate DCC instruction and highlight instruction in case 'highlight_instruction' option is used.'''
        if self.dcc_addr_type == 'BASIC_ACCY':
            if self.dcc_bytes[-1] & 0b10000000:
                i = self.annotate_dcc_instr_basic_accessory_decoder_control(i)
            else:
                i = self.annotate_dcc_instr_nop_for_basic_and_extended_accessory(
                    i)
        elif self.dcc_addr_type == 'EXT_ACCY':
            if self.dcc_bytes[-1] & 0b1000:
                i = self.annotate_dcc_instr_nop_for_basic_and_extended_accessory(
                    i)
            else:
                i = self.annotate_dcc_instr_extended_accessory_decoder_control(
                    i)
        else:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            self.annotate_dcc_byte(i)
            if self.dcc_addr_type in ('BROADCAST', 'BASIC_LOCO', 'EXT_LOCO'):
                instr = decode_instruction(self.dcc_bytes[-1])
                if instr == self.highlight_instr.upper().replace(' ', '_'):
                    self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT],
                             self.out_ann,
                             [Ann.HIGHLIGHT_INSTR, [self.highlight_instr]])
                if instr == 'UNKNOWN_SERVICE':
                    pass
                elif instr == 'DECODER_CONTROL':
                    i = self.annotate_dcc_instr_decoder_control(i)
                elif instr == 'CONSIST_CONTROL':
                    i = self.annotate_dcc_instr_consist_control(i)
                elif instr == 'ADVANCED_OPERATIONS':
                    i = self.annotate_dcc_instr_advanced_operations(i)
                elif instr == 'SPEED_AND_DIRECTION':
                    i = self.annotate_dcc_instr_speed_and_direction(i)
                elif instr == 'FUNCTION_GROUP':
                    i = self.annotate_dcc_instr_function_group(i)
                elif instr == 'FEATURE_EXPANSION':
                    i = self.annotate_dcc_instr_feature_expansion(i)
                elif instr == 'CV_ACCESS':
                    i = self.annotate_dcc_instr_cv_access(i)
            elif self.dcc_addr_type == 'DATA_TRANSFER':
                i = self.annotate_dcc_instr_data_transfer(i)
            elif self.dcc_addr_type == 'AUTOMATIC_LOGON':
                i = self.annotate_dcc_instr_automatic_logon(i)
            elif self.dcc_addr_type == 'IDLE':
                i = self.annotate_dcc_instr_digital_decoder_idle(i)
        return i

    def annotate_dcc_instr_unknown(self, i):
        '''Annotate unknown DCC instruction.
        
        This function annotates whatever is left between the last annotated data byte and the checksum.
        '''
        # As long as there are halfbits minus checksum and endbit
        while i < len(self.dcc_hbits) - BIT_HBIT - BYTE_HBIT - BIT_HBIT:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_decoder_control(self, i):
        '''Annotate DCC 'Decoder Control' instructions.'''
        instr = self.dcc_bytes[-1]
        if instr == 0b00000000:
            i = self.annotate_dcc_instr_decoder_control_digital_decoder_reset(
                i)
        elif instr == 0b00000001:
            i = self.annotate_dcc_instr_decoder_control_hard_reset(i)
        elif instr in (0b00000010, 0b00000011):
            i = self.annotate_dcc_instr_decoder_control_factory_test(i)
        elif instr in (0b00001010, 0b00001011):
            i = self.annotate_dcc_instr_decoder_control_set_advanced_addressing(
                i)
        elif instr == 0b00001111:
            i = self.annotate_dcc_instr_decoder_control_decoder_acknowledgement_request(
                i)
        return i

    def annotate_dcc_instr_decoder_control_digital_decoder_reset(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Decoder Control - Digital Decoder Reset',
                'Digital Decoder Reset'
            ]
        ])
        self.service_mode = True
        return i + BYTE_HBIT

    def annotate_dcc_instr_decoder_control_hard_reset(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Decoder Control - Hard Reset', 'Hard Reset']
        ])
        return i + BYTE_HBIT

    def annotate_dcc_instr_decoder_control_factory_test(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Decoder Control - Factory Test', 'Factory Test']
        ])
        i += BYTE_HBIT
        while i < len(self.dcc_hbits) - BIT_HBIT - BYTE_HBIT - BIT_HBIT:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         self.get_ann_instr(),
                         [
                             'Data=0x{:02X}'.format(self.dcc_bytes[-1]),
                             'D=0x{:02X}'.format(self.dcc_bytes[-1])
                         ]
                     ])
            i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_decoder_control_set_advanced_addressing(self, i):
        d = self.dcc_bytes[-1] & 0b1
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Decoder Control - Set Advanced Addressing (CV29:5={})'.format(
                    d), 'Set Advanced Addressing (CV29:5={})'.format(d),
                'CV29:5={}'.format(d)
            ]
        ])
        return i + BYTE_HBIT

    def annotate_dcc_instr_decoder_control_decoder_acknowledgement_request(
            self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Decoder Control - Decoder Acknowledgement Request',
                'Decoder Acknowledgement Request', 'Acknowledgement Request',
                'ACK Request'
            ]
        ])
        return i + BYTE_HBIT

    def annotate_dcc_instr_consist_control(self, i):
        '''Annotate DCC 'Consist Control' instructions.'''
        instr = self.dcc_bytes[-1]
        if instr in (0b00010010, 0b00010011):
            i = self.annotate_dcc_instr_consist_control_set_consist_address(i)
        return i

    def annotate_dcc_instr_consist_control_set_consist_address(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Consist Control - Set Consist Address', 'Set Consist Address']
        ])
        i += BYTE_HBIT
        # CV19
        r = self.dcc_bytes[-1] & 0b1
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        addr = self.dcc_bytes[-1] & 0x7F
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Reversed={} | Address={}'.format(r, addr),
                'R={} | A={}'.format(r, addr)
            ]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_advanced_operations(self, i):
        '''Annotate DCC 'Advanced Operations' instructions.'''
        instr = self.dcc_bytes[-1]
        if instr == 0b00111100:
            i = self.annotate_dcc_instr_advanced_operations_speed_direction_and_function(
                i)
        elif instr == 0b00111101:
            i = self.annotate_dcc_instr_advanced_operations_analog_function_group(
                i)
        elif instr == 0b00111110:
            i = self.annotate_dcc_instr_advanced_operations_special_operating_modes(
                i)
        elif instr == 0b00111111:
            i = self.annotate_dcc_instr_advanced_operations_128_speed_step_control(
                i)
        return i

    def annotate_dcc_instr_advanced_operations_speed_direction_and_function(
            self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Advanced Operations - Speed, Direction and Functions',
                'Speed, Direction and Functions', 'SDF'
            ]
        ])
        i += BYTE_HBIT
        # RGGGGGGG
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        dir = (self.dcc_bytes[-1] >> 7) & 0b1
        speed = decode_rggggggg(self.dcc_bytes[-1])
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Direction={} | Speed={}/128'.format(dir, speed),
                'D={} | S={}/128'.format(dir, speed)
            ]
        ])
        i = self.annotate_dcc_byte(i)
        # Functions (max. 4)
        byte_count = min(
            ((len(self.dcc_hbits) - i) // (BIT_HBIT + BYTE_HBIT)) - 1, 4)
        for j in range(byte_count):
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            f = [(self.dcc_bytes[-1] >> bit) & 0b1 for bit in range(8)]
            fstr = ' | '.join('F{}={}'.format(j * 8 + i, f[i])
                              for i in range(8))
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), [fstr]])
            i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_advanced_operations_analog_function_group(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Advanced Operations - Analog Function Group',
                'Analog Function Group'
            ]
        ])
        i += BYTE_HBIT
        # Analog channel
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        ch = decode_ssssssss(self.dcc_bytes[-1])
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Channel={}'.format(ch), 'CH={}'.format(ch)]
        ])
        i = self.annotate_dcc_byte(i)
        # Analog data
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        data = self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Data={}'.format(data), 'D={}'.format(data)]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_advanced_operations_special_operating_modes(
            self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Advanced Operations - Special Operating Modes',
                'Special Operating Modes'
            ]
        ])
        i += BYTE_HBIT
        # Bits
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        consist_map = {
            0b00: 'Not Part',
            0b10: 'Leading',
            0b01: 'Middle',
            0b11: 'Rear'
        }
        consist = consist_map.get((self.dcc_bytes[-1] >> 2) & 0b11, 'Unknown')
        shunting = (self.dcc_bytes[-1] >> 4) & 0b1
        west = (self.dcc_bytes[-1] >> 5) & 0b1
        east = (self.dcc_bytes[-1] >> 6) & 0b1
        man = (self.dcc_bytes[-1] >> 7) & 0b1
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Consist={} | Shunting={} | West={} | East={} | MAN={}'.format(
                    consist, shunting, west, east, man),
                'C={} | S={} | W={} | E={} | M={}'.format(
                    consist, shunting, west, east, man)
            ]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_advanced_operations_128_speed_step_control(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Advanced Operations - 128 Speed Step Control',
                '128 Speed Step Control'
            ]
        ])
        i += BYTE_HBIT
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        dir = (self.dcc_bytes[-1] >> 7) & 0b1
        speed = decode_rggggggg(self.dcc_bytes[-1])
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Direction={} | Speed={}/128'.format(dir, speed),
                'D={} | S={}/128'.format(dir, speed)
            ]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_speed_and_direction(self, i):
        '''Annotate DCC 'Speed & Direction' instructions.'''
        dir = (self.dcc_bytes[-1] >> 5) & 0b1
        speed = decode_rggggg(self.dcc_bytes[-1], self.cv29_1)
        if self.cv29_1:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         self.get_ann_instr(),
                         [
                             'Speed and Direction: Direction={} | Speed={}/28'.
                             format(dir, speed),
                             'Direction={} | Speed={}/28'.format(dir, speed),
                             'D={} | S={}/28'.format(dir, speed)
                         ]
                     ])
        else:
            f0 = (self.dcc_bytes[-1] >> 4) & 0b1
            self.put(
                self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    [
                        'Speed and Direction: Direction={} | Speed={}/14 F0={}'
                        .format(dir, speed, f0),
                        'Direction={} | Speed={}/14 F0={}'.format(
                            dir, speed, f0), 'D={} | S={}/14 | F0={}'.format(
                                dir, speed, f0)
                    ]
                ])
        return i + BYTE_HBIT

    def annotate_dcc_instr_function_group(self, i):
        '''Annotate DCC 'Function Group' instructions.'''
        instr = self.dcc_bytes[-1] & 0xF0
        if instr in (0b10000000, 0b10010000):
            i = self.annotate_dcc_instr_function_group_f0_f4(i)
        elif instr == 0b10100000:
            i = self.annotate_dcc_instr_function_group_f9_f12(i)
        elif instr == 0b10110000:
            i = self.annotate_dcc_instr_function_group_f5_f8(i)
        return i

    def annotate_dcc_instr_function_group_f0_f4(self, i):
        f1 = (self.dcc_bytes[-1] >> 0) & 0b1
        f2 = (self.dcc_bytes[-1] >> 1) & 0b1
        f3 = (self.dcc_bytes[-1] >> 2) & 0b1
        f4 = (self.dcc_bytes[-1] >> 3) & 0b1
        if self.cv29_1:
            f0 = (self.dcc_bytes[-1] >> 4) & 0b1
            fstr = 'F0={} | F1={} | F2={} | F3={} | F4={}'.format(
                f0, f1, f2, f3, f4)
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         self.get_ann_instr(),
                         ['Function Group - F0-F4: ' + fstr, fstr]
                     ])
        else:
            fstr = 'F1={} | F2={} | F3={} | F4={}'.format(f1, f2, f3, f4)
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         self.get_ann_instr(),
                         ['Function Group - F0-F4: ' + fstr, fstr]
                     ])
        return i + BYTE_HBIT

    def annotate_dcc_instr_function_group_f9_f12(self, i):
        f9_12 = [(self.dcc_bytes[-1] >> bit) & 0b1 for bit in range(4)]
        fstr = ' | '.join('F{}={}'.format(9 + i, f9_12[i]) for i in range(4))
        self.put(
            self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
            [self.get_ann_instr(), ['Function Group - F9-F12: ' + fstr, fstr]])
        return i + BYTE_HBIT

    def annotate_dcc_instr_function_group_f5_f8(self, i):
        f5_8 = [(self.dcc_bytes[-1] >> bit) & 0b1 for bit in range(4)]
        fstr = ' | '.join('F{}={}'.format(5 + i, f5_8[i]) for i in range(4))
        self.put(
            self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
            [self.get_ann_instr(), ['Function Group - F5-F8: ' + fstr, fstr]])
        return i + BYTE_HBIT

    def annotate_dcc_instr_feature_expansion(self, i):
        '''Annotate DCC 'Feature Expansion' instructions.'''
        instr = self.dcc_bytes[-1]
        if instr == 0b11000000:
            i = self.annotate_dcc_instr_feature_expansion_binary_state_control_long_form(
                i)
        elif instr == 0b11000001:
            i = self.annotate_dcc_instr_feature_expansion_time_and_date(i)
        elif instr == 0b11000010:
            i = self.annotate_dcc_instr_feature_expansion_system_time(i)
        elif instr == 0b11000011:
            i = self.annotate_dcc_instr_feature_expansion_command_station_feature_identification(
                i)
        elif instr == 0b11011000:
            i = self.annotate_dcc_instr_feature_expansion_f29_f36(i)
        elif instr == 0b11011001:
            i = self.annotate_dcc_instr_feature_expansion_f37_f44(i)
        elif instr == 0b11011010:
            i = self.annotate_dcc_instr_feature_expansion_f45_f52(i)
        elif instr == 0b11011011:
            i = self.annotate_dcc_instr_feature_expansion_f53_f60(i)
        elif instr == 0b11011100:
            i = self.annotate_dcc_instr_feature_expansion_f61_f68(i)
        elif instr == 0b11011101:
            i = self.annotate_dcc_instr_feature_expansion_binary_state_control_short_form(
                i)
        elif instr == 0b11011110:
            i = self.annotate_dcc_instr_feature_expansion_f13_f20(i)
        elif instr == 0b11011111:
            i = self.annotate_dcc_instr_feature_expansion_f21_f28(i)
        return i

    def annotate_dcc_instr_feature_expansion_binary_state_control_long_form(
            self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Feature Expansion - Binary State Control Long Form',
                'Binary State Control Long Form'
            ]
        ])
        i += BYTE_HBIT
        # Low byte
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # High byte
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        d = self.dcc_bytes[-2] >> 7
        addr = (self.dcc_bytes[-1] << 7) | (self.dcc_bytes[-2] & 0x7F)
        self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['State {}={}'.format(addr, d), 'S {}={}'.format(addr, d)]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_feature_expansion_time_and_date(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Feature Expansion - Time and Date', 'Time and Date']
        ])
        i += BYTE_HBIT
        # Minutes or day
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # Weekday and hours, month and year or sign and exponent
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # Update and acceleration factor, year or mantisse
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        cc = self.dcc_bytes[-3] >> 6
        if cc == 0b00:
            minutes = self.dcc_bytes[-3] & 0b00111111
            weekdays = [
                'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                'Saturday', 'Sunday', 'Not Supported'
            ]
            weekday = weekdays[self.dcc_bytes[-2] >> 5]
            hours = self.dcc_bytes[-2] & 0b00011111
            update = self.dcc_bytes[-1] >> 7
            acc = self.dcc_bytes[-1] & 0b00111111
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                [
                    '{} {}:{} | Update={} | Acceleration={}'.format(
                        weekday, hours, minutes, update,
                        acc), '{} {}:{} | U={} | Acc={}'.format(
                            weekday, hours, minutes, update, acc)
                ]
            ])
        elif cc == 0b01:
            day = self.dcc_bytes[-3] & 0b00011111
            month = self.dcc_bytes[-2] >> 4
            year = (self.dcc_bytes[-2] & 0x0F) << 8 | self.dcc_bytes[-1]
            self.put(
                ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                [self.get_ann_instr(), ['{}/{}/{}'.format(day, month, year)]])
        elif cc == 0b10:
            scale = float16_to_float(self.dcc_bytes[-2] << 8
                                     | self.dcc_bytes[-1])
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['Scale={:.2f}'.format(scale), 'S={:.2f}'.format(scale)]
            ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_feature_expansion_system_time(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Feature Expansion - System Time', 'System Time']
        ])
        i += BYTE_HBIT
        # High byte
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # Low byte
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        ms = (self.dcc_bytes[-2] << 8) | self.dcc_bytes[-1]
        self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Milliseconds={}'.format(ms), 'ms={}'.format(ms)]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_feature_expansion_command_station_feature_identification(
            self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Feature Expansion - Command Station Feature Identification',
                'Command Station Feature Identification'
            ]
        ])
        i += BYTE_HBIT
        # Type
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        type_map = {
            0b1111: 'Loco Features',
            0b1110: 'Accessory and Broadcast Features',
            0b1101: 'BiDi Features',
            0b0000: 'Test Features'
        }
        iiii = self.dcc_bytes[-1] & 0x0F
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), [type_map.get(iiii, '?')]])
        i = self.annotate_dcc_byte(i)
        # Bitmask
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        bitmask = self.dcc_bytes[-2] << 8 | self.dcc_bytes[-1] << 0
        if iiii == 0b1111:
            fstr = 'Basic Addresses 100-127 as Extended={} | '.format(
                (bitmask >> 0) & 0b1)
            fstr += 'Extended Addresses 10000-10239={} | '.format(
                (bitmask >> 1) & 0b1)
            fstr += '128 Speed Steps={} | '.format((bitmask >> 2) & 0b1)
            fstr += 'Speed, Direction and Functions={} | '.format(
                (bitmask >> 3) & 0b1)
            fstr += 'POM Write={} | '.format((bitmask >> 4) & 0b1)
            fstr += 'XPOM Write={} | '.format((bitmask >> 5) & 0b1)
            fstr += 'F13-F28={} | '.format((bitmask >> 8) & 0b1)
            fstr += 'F29-F68={} | '.format((bitmask >> 9) & 0b1)
            fstr += 'Binary State Short={} | '.format((bitmask >> 10) & 0b1)
            fstr += 'Binary State Long={} | '.format((bitmask >> 11) & 0b1)
            fstr += 'Analog Function={} | '.format((bitmask >> 12) & 0b1)
            fstr += 'Special Operating Modes={}'.format((bitmask >> 13) & 0b1)
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), [fstr]])
        elif iiii == 0b1110:
            fstr = 'Addresses Offset by 4={} | '.format((bitmask >> 0) & 0b1)
            fstr += 'Extended={} | '.format((bitmask >> 1) & 0b1)
            fstr += 'POM Write={} | '.format((bitmask >> 3) & 0b1)
            fstr += 'Time={} | '.format((bitmask >> 8) & 0b1)
            fstr += 'Date={} | '.format((bitmask >> 9) & 0b1)
            fstr += 'Time Scale={} | '.format((bitmask >> 10) & 0b1)
            fstr += 'System Time={}'.format((bitmask >> 11) & 0b1)
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), [fstr]])
        elif iiii == 0b1101:
            fstr = 'RailCom={} | '.format((bitmask >> 0) & 0b1)
            fstr += 'DCC-A={} | '.format((bitmask >> 1) & 0b1)
            fstr += 'NOP for Accessories={} | '.format((bitmask >> 2) & 0b1)
            fstr += 'POM Read (ID0)={} | '.format((bitmask >> 3) & 0b1)
            fstr += 'XPOM Read={} | '.format((bitmask >> 4) & 0b1)
            fstr += 'POM Read (ID12)={} | '.format((bitmask >> 5) & 0b1)
            fstr += 'Container Levels (ID7:8-19)={} | '.format((bitmask >> 8)
                                                               & 0b1)
            fstr += 'Operating Parameters (ID7:0-1,7,20,22,26)={} | '.format(
                (bitmask >> 9)
                & 0b1)
            fstr += 'Track Voltage (ID7:46)={} | '.format((bitmask >> 10)
                                                          & 0b1)
            fstr += 'RailCom+={}'.format((bitmask >> 15) & 0b1)
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), [fstr]])
        else:
            fstr = ' | '.join('Bit{}={}'.format(i, (bitmask & (1 << i)) >> i)
                              for i in range(16))
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), [fstr]])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_feature_expansion_f29_f36(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 29, 36)

    def annotate_dcc_instr_feature_expansion_f37_f44(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 37, 44)

    def annotate_dcc_instr_feature_expansion_f45_f52(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 45, 52)

    def annotate_dcc_instr_feature_expansion_f53_f60(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 53, 60)

    def annotate_dcc_instr_feature_expansion_f61_f68(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 61, 68)

    def annotate_dcc_instr_feature_expansion_binary_state_control_short_form(
            self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            [
                'Feature Expansion - Binary State Control Short Form',
                'Binary State Control Short Form'
            ]
        ])
        i += BYTE_HBIT
        # State
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        d = self.dcc_bytes[-1] >> 7
        addr = self.dcc_bytes[-1] & 0x7F
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['State {}={}'.format(addr, d), 'S {}={}'.format(addr, d)]
        ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_feature_expansion_f13_f20(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 13, 20)

    def annotate_dcc_instr_feature_expansion_f21_f28(self, i):
        return self.instr_feature_expansion_fxx_fyy_annotate_dcc_helper(
            i, 21, 28)

    def annotate_dcc_instr_cv_access(self, i):
        '''Annotate DCC 'CV Access' instructions.'''
        if self.dcc_bytes[-1] & 0b10000:
            return self.annotate_dcc_instr_cv_access_short_form(i)
        # Only byte count determines whether this is XPOM
        elif ((len(self.dcc_hbits) - i) // (BIT_HBIT + BYTE_HBIT)) - 1 <= 3:
            return self.annotate_dcc_instr_cv_access_long_form(i)
        else:
            return self.annotate_dcc_instr_cv_access_xpom(i)

    def annotate_dcc_instr_cv_access_long_form(self, i):
        # Instruction
        self.put(
            self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
            [self.get_ann_instr(), ['CV Access - Long Form', 'CV Access']])
        i += BYTE_HBIT
        # CV address
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # CV value
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        kk = (self.dcc_bytes[-3] >> 2) & 0b11
        cv_addr = (self.dcc_bytes[-3] & 0b11) << 8 | self.dcc_bytes[-2]
        # Reserved
        if kk == 0b00:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Reserved', 'R']])
        # Verify
        elif kk == 0b01:
            cv_value = self.dcc_bytes[-1]
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['Verify CV{}={}'.format(cv_addr + 1, cv_value)]
            ])
        # Write
        elif kk == 0b11:
            cv_value = self.dcc_bytes[-1]
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['Write CV{}={}'.format(cv_addr + 1, cv_value)]
            ])
        # Bit manipulation
        elif kk == 0b10:
            k = 'Write' if self.dcc_bytes[-1] & 0b10000 else 'Verify'
            d = (self.dcc_bytes[-1] >> 3) & 0b1
            bbb = self.dcc_bytes[-1] & 0b111
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['{} CV{}:{}={}'.format(k, cv_addr + 1, bbb, d)]
            ])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_cv_access_short_form(self, i):
        # Instruction
        self.put(
            self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
            [self.get_ann_instr(), ['CV Access - Short Form', 'CV Access']])
        i += BYTE_HBIT
        # KKKK
        kkkk = self.dcc_bytes[-1] & 0x0F
        # First CV
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        # CV23
        if kkkk == 0b0010:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['Write CV23={}'.format(self.dcc_bytes[-1])]
            ])
        # CV24
        elif kkkk == 0b0011:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                ['Write CV24={}'.format(self.dcc_bytes[-1])]
            ])
        # CV17/18, CV31/32 or CV19/20
        elif kkkk in (0b0100, 0b0101, 0b0110):
            i = self.annotate_dcc_byte(i)
            # Second CV
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            # CV17/18
            if kkkk == 0b0100:
                self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    [
                        'Write CV17={} | CV18={}'.format(
                            self.dcc_bytes[-2], self.dcc_bytes[-1])
                    ]
                ])
            # CV31/32
            elif kkkk == 0b0101:
                self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    [
                        'Write CV31={} | CV32={}'.format(
                            self.dcc_bytes[-2], self.dcc_bytes[-1])
                    ]
                ])
            # CV19/20
            elif kkkk == 0b0110:
                self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    [
                        'Write CV19={} | CV20={}'.format(
                            self.dcc_bytes[-2], self.dcc_bytes[-1])
                    ]
                ])
        # Deprecated
        elif kkkk == 0b1001:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Deprecated']])
        # Forbidden
        else:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Forbidden']])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_cv_access_xpom(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['CV Access - XPOM', 'XPOM']])
        i += BYTE_HBIT
        # CV31
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        cv31 = self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['CV31={}'.format(cv31)]])
        i = self.annotate_dcc_byte(i)
        # CV32
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        cv32 = self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['CV32={}'.format(cv32)]])
        i = self.annotate_dcc_byte(i)
        # CV address
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        cv_offset = self.dcc_bytes[-1]
        cv_addr = cv31 << 16 | cv32 << 8 | cv_offset << 0
        kk = (self.dcc_bytes[-4] >> 2) & 0b11
        # Reserved
        if kk == 0b00:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Reserved', 'R']])
            i = self.annotate_dcc_byte(i)
        # Verify
        elif kk == 0b01:
            self.put(
                self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    [
                        'Verify CV{} ({})'.format(cv_offset + 1, cv_addr + 1),
                        'Verify CV{}'.format(cv_offset + 1)
                    ]
                ])
            i = self.annotate_dcc_byte(i)
        # Write
        elif kk == 0b11:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Write Byte']])
            i = self.annotate_dcc_byte(i)
            # CV values (<=4)
            byte_count = ((len(self.dcc_hbits) - i) //
                          (BIT_HBIT + BYTE_HBIT)) - 1
            for j in range(byte_count):
                i = self.annotate_dcc_frame_start_bit(i)
                self.annotate_frame_instr(i)
                self.dcc_bytes.append(self.get_dcc_byte_at(i))
                cv_value = self.dcc_bytes[-1]
                self.put(
                    self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                        self.get_ann_instr(),
                        [
                            'CV{}={} ({})'.format(cv_offset + 1 + j, cv_value,
                                                  cv_addr + 1 + j),
                            'CV{}={}'.format(cv_offset + 1 + j, cv_value)
                        ]
                    ])
                i = self.annotate_dcc_byte(i)
        # Bit manipulation
        elif kk == 0b10:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Write Bit']])
            i = self.annotate_dcc_byte(i)
            # CV value
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            d = (self.dcc_bytes[-1] >> 3) & 0b1
            bbb = self.dcc_bytes[-1] & 0b111
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         self.get_ann_instr(),
                         [
                             'Write CV{}:{}={} ({})'.format(
                                 cv_offset + 1, bbb, d, cv_addr + 1),
                             'Write CV{}:{}={}'.format(cv_offset + 1, bbb, d)
                         ]
                     ])
            i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_basic_accessory_decoder_control(self, i):
        '''Annotate DCC 'Basic Accessory Decoder Control' instructions.'''
        d = (self.dcc_bytes[-1] >> 3) & 0b1
        r = self.dcc_bytes[-1] & 0b1
        ss = self.dcc_ss[i - BYTE_HBIT - BIT_HBIT - BYTE_HBIT]
        self.put(ss, self.dcc_ss[i], self.out_ann, [
            self.get_ann_instr(),
            [
                'Basic Accessory={} | Pair{}={}'.format(self.dcc_addr, r, d),
                'Accessory={} | P{}={}'.format(self.dcc_addr, r, d),
                '{} | {}={}'.format(self.dcc_addr, r, d)
            ]
        ])
        return i

    def annotate_dcc_instr_extended_accessory_decoder_control(self, i):
        '''Annotate DCC 'Extended Accessory Decoder Control' instructions.'''
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        aspect = self.dcc_bytes[-1]
        r = self.dcc_bytes[-1] >> 7
        sw_time = SWITCH_TIMES[self.dcc_bytes[-1] & 0x7F]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Aspect={} or State={} for Time={}'.format(aspect, r, sw_time)]
        ])
        i = self.annotate_dcc_byte(i)
        return i + BYTE_HBIT

    def annotate_dcc_instr_nop_for_basic_and_extended_accessory(self, i):
        '''Annotate DCC 'NOP for Basic and Extended Accessory' instructions.'''
        ss = self.dcc_ss[i - BYTE_HBIT - BIT_HBIT - BYTE_HBIT]
        if self.dcc_addr_type == 'BASIC_ACCY':
            self.put(ss, self.dcc_ss[i], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Basic Accessory={} NOP'.format(self.dcc_addr),
                    'Accessory={} NOP'.format(self.dcc_addr)
                ]
            ])
        elif self.dcc_addr_type == 'EXT_ACCY':
            self.put(ss, self.dcc_ss[i], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Extended Accessory={} NOP'.format(self.dcc_addr),
                    'Accessory={} NOP'.format(self.dcc_addr)
                ]
            ])
        return i

    def annotate_dcc_instr_data_transfer(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['TODO']])
        i += BYTE_HBIT
        return i

    def annotate_dcc_instr_automatic_logon(self, i):
        instr = self.dcc_bytes[-1]
        if instr in (0b00000000, 0b00000001):
            i = self.annotate_dcc_instr_automatic_logon_get_data(i)
        elif instr in (0b00000010, 0b00000011):
            i = self.annotate_dcc_instr_automatic_logon_set_data(i)
        elif instr in (0b11010000, 0b11010001, 0b11010010, 0b11010011,
                       0b11010100, 0b11010101, 0b11010110, 0b11010111,
                       0b11011000, 0b11011001, 0b11011010, 0b11011011,
                       0b11011100, 0b11011101, 0b11011110, 0b11011111):
            i = self.annotate_dcc_instr_automatic_logon_select(i)
        elif instr in (0b11100000, 0b11100001, 0b11100010, 0b11100011,
                       0b11100100, 0b11100101, 0b11100110, 0b11100111,
                       0b11101000, 0b11101001, 0b11101010, 0b11101011,
                       0b11101100, 0b11101101, 0b11101110, 0b11101111):
            i = self.annotate_dcc_instr_automatic_logon_assign(i)
        elif instr in (0b11111100, 0b11111101, 0b11111110, 0b11111111):
            i = self.annotate_dcc_instr_automatic_logon_enable(i)
        else:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Reserved', 'R']])
            i += BYTE_HBIT
        return i

    def annotate_dcc_instr_automatic_logon_get_data(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['TODO']])
        i += BYTE_HBIT
        return i

    def annotate_dcc_instr_automatic_logon_set_data(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['TODO']])
        i += BYTE_HBIT
        return i

    def annotate_dcc_instr_automatic_logon_select(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['SELECT']])
        i += BYTE_HBIT
        # Manufacturer ID
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        mid = (self.dcc_bytes[-2] & 0x0F) << 8 | self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Manufacturer ID={}'.format(mid), 'MID={}'.format(mid)]
        ])
        i = self.annotate_dcc_byte(i)
        # UID
        for j in range(0, 4):
            i = self.annotate_dcc_frame_start_bit(i)
            if j == 0:
                ss = self.dcc_ss[i]
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            if j == 3:
                uid = (self.dcc_bytes[-4] << 24 | self.dcc_bytes[-3] << 16
                       | self.dcc_bytes[-2] << 8 | self.dcc_bytes[-1] << 0)
                self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                         [self.get_ann_instr(), ['UID=0x{:08X}'.format(uid)]])
            i = self.annotate_dcc_byte(i)
        # Sub command
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        bbbbbbbb = self.dcc_bytes[-1]
        block_map = {
            0: 'Extended Capabilities',
            1: 'SpaceInfo',
            2: 'ShortGUI',
            3: 'CV-Block',
            4: 'Icon',
            5: 'Name',
            6: 'DecoderInfo',
            7: 'VehicleInfo',
        }
        if bbbbbbbb == 0b11111111:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['ReadShortInfo']])
        elif bbbbbbbb == 0b11111110:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['ReadBlock']])
            i = self.annotate_dcc_byte(i)
            # NNNN-NNNN
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            nnnnnnnn = self.dcc_bytes[-1]
            self.put(
                self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    ['#={} {}'.format(nnnnnnnn, block_map.get(nnnnnnnn, ''))]
                ])
        elif bbbbbbbb == 0b11111100:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['WriteBlock']])
            i = self.annotate_dcc_byte(i)
            # NNNN-NNNN
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            nnnnnnnn = self.dcc_bytes[-1]
            self.put(
                self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                    self.get_ann_instr(),
                    ['#={} {}'.format(nnnnnnnn, block_map.get(nnnnnnnn, ''))]
                ])
            i = self.annotate_dcc_byte(i)
            # SSSS-SSSS
            i = self.annotate_dcc_frame_start_bit(i)
            ss = self.dcc_ss[i]
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            i = self.annotate_dcc_byte(i)
            # ssss-ssss
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            ssssssss = self.dcc_bytes[-2] << 8 | self.dcc_bytes[-1]
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Size={}'.format(ssssssss)]])
        elif bbbbbbbb == 0b11111011:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Set Decoder Internal Status']])
            i = self.annotate_dcc_byte(i)
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            nnnnnnnn = self.dcc_bytes[-1]
            if nnnnnnnn == 0b11111111:
                self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT],
                         self.out_ann,
                         [self.get_ann_instr(), ['Clear Change Flags']])
            else:
                self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT],
                         self.out_ann,
                         [self.get_ann_instr(), ['Reserved', 'R']])
        elif bbbbbbbb == 0b11111101 or 0b11111010 >= bbbbbbbb >= 0b00000000:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Reserved', 'R']])
        i = self.annotate_dcc_byte(i)
        return self.annotate_dcc_crc8(i)

    def annotate_dcc_instr_automatic_logon_assign(self, i):
        # Instruction
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['LOGON_ASSIGN', 'ASSIGN']])
        i += BYTE_HBIT
        # Manufacturer ID
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        mid = (self.dcc_bytes[-2] & 0x0F) << 8 | self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
            self.get_ann_instr(),
            ['Manufacturer ID={}'.format(mid), 'MID={}'.format(mid)]
        ])
        i = self.annotate_dcc_byte(i)
        # UID
        for j in range(0, 4):
            i = self.annotate_dcc_frame_start_bit(i)
            if j == 0:
                ss = self.dcc_ss[i]
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            if j == 3:
                uid = (self.dcc_bytes[-4] << 24 | self.dcc_bytes[-3] << 16
                       | self.dcc_bytes[-2] << 8 | self.dcc_bytes[-1] << 0)
                self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                         [self.get_ann_instr(), ['UID=0x{:08X}'.format(uid)]])
            i = self.annotate_dcc_byte(i)
        # Address high byte
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # Address low byte
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        bb = self.dcc_bytes[-2] >> 6
        bb_str = 'permanent' if bb == 0b10 else 'temporary'
        a13_8 = self.dcc_bytes[-2] & 0b00111111
        if 0x00 <= a13_8 <= 0x27:
            addr = a13_8 << 8 | self.dcc_bytes[-1]
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Extended Loco={} ({})'.format(addr, bb_str),
                    'Loco={}'.format(addr)
                ]
            ])
        elif 0x28 <= a13_8 <= 0x2F:
            addr = (a13_8 << 8 | self.dcc_bytes[-1]) & 0x7FF
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Extended Accessory={} ({})'.format(addr, bb_str),
                    'Accessory={}'.format(addr)
                ]
            ])
            pass
        elif 0x30 <= a13_8 <= 0x37:  # Basic accessory
            addr = (a13_8 << 8 | self.dcc_bytes[-1]) & 0x7FF
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Basic Accessory={} ({})'.format(addr, bb_str),
                    'Accessory={}'.format(addr)
                ]
            ])
        elif 0x38 == a13_8:
            addr = self.dcc_bytes[-1] & 0x7F
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann, [
                self.get_ann_instr(),
                [
                    'Basic Loco={} ({})'.format(addr, bb_str),
                    'Loco={}'.format(addr)
                ]
            ])
        elif 0x39 <= a13_8 <= 0x3E:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Reserved', 'R']])
        elif 0x3F == a13_8:
            self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), ['Firmware update', 'FW update']])
        i = self.annotate_dcc_byte(i)
        return self.annotate_dcc_crc8(i)

    def annotate_dcc_instr_automatic_logon_enable(self, i):
        # Instruction
        gg_map = {
            0b00: ['LOGON_ENABLE(ALL)', 'ENABLE(ALL)', 'ALL'],
            0b01: ['LOGON_ENABLE(LOCO)', 'ENABLE(LOCO)', 'LOCO'],
            0b10: ['LOGON_ENABLE(ACC)', 'ENABLE(ACC)', 'ACC'],
            0b11: ['LOGON_ENABLE(NOW)', 'ENABLE(NOW)', 'NOW'],
        }
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(),
                  gg_map.get(self.dcc_bytes[-1] & 0b11)])
        i += BYTE_HBIT
        # CID high byte
        i = self.annotate_dcc_frame_start_bit(i)
        ss = self.dcc_ss[i]
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        i = self.annotate_dcc_byte(i)
        # CID low byte
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        zid = self.dcc_bytes[-2] << 8 | self.dcc_bytes[-1]
        self.put(ss, self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['CID=0x{:04X}'.format(zid)]])
        i = self.annotate_dcc_byte(i)
        # SID
        i = self.annotate_dcc_frame_start_bit(i)
        self.annotate_frame_instr(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        sid = self.dcc_bytes[-1]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['SID={}'.format(sid)]])
        i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_crc8(self, i):
        if len(self.dcc_bytes) > 6:
            i = self.annotate_dcc_frame_start_bit(i)
            self.annotate_frame_instr(i)
            self.dcc_bytes.append(self.get_dcc_byte_at(i))
            crc8_sign = CROSS_MARK if crc8(self.dcc_bytes) else CHECK_SIGN
            anns = ['CRC8 ' + crc8_sign, crc8_sign]
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [self.get_ann_instr(), anns])
            i = self.annotate_dcc_byte(i)
        return i

    def annotate_dcc_instr_digital_decoder_idle(self, i):
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), ['Digital Decoder Idle', 'Idle']])
        return i + BYTE_HBIT

    def annotate_dcc_checksum(self, i):
        '''Annotate and check DCC checksum.'''
        i = self.annotate_dcc_frame_start_bit(i)
        self.dcc_bytes.append(self.get_dcc_byte_at(i))
        checksum = exor(self.dcc_bytes)
        checksum_sign = CROSS_MARK if checksum else CHECK_SIGN
        anns = ['Checksum ' + checksum_sign, checksum_sign]
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [Ann.FRAME_CHECKSUM, anns])
        if checksum:
            self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                     [
                         Ann.ERROR,
                         [
                             'Checksum should be 0x{:02X}'.format(
                                 exor(self.dcc_bytes[:-1]))
                         ]
                     ])
        # Eventually add empty \n to help readability for exported annotations
        anns[0] = anns[0] + self.empty_new_line_after_packets_annotation
        self.put(self.dcc_ss[i], self.dcc_ss[i + BYTE_HBIT], self.out_ann,
                 [self.get_ann_instr(), anns])
        i = self.annotate_dcc_byte(i)
        i = self.annotate_dcc_frame_endbit(i)
        return i

    def decode_bidi(self, bidi):
        '''Decode BiDi.

        'annotate_bidi' and 'reset_bidi' is called by 'decode' after the cutout.
        '''
        # No BIDI or prior DCC packet
        if not self.has_channel(Pin.BIDI) or not self.last_dcc_ss:
            return

        # Outside of channel timing
        ss_tcs = self.ss_us2es(self.last_dcc_ss[-1], self.tts1)
        ss_tce = self.ss_us2es(self.last_dcc_ss[-1], self.ttc2)
        if self.samplenum < ss_tcs or self.samplenum > ss_tce:
            return

        # Start bit not 0
        if not self.bidi_edges_ss and bidi == 1:
            return self.reset_bidi()

        # Debounce
        if (not self.bidi_edges_ss or self.ss_es2bidi_bits_passed(
                self.bidi_edges_ss[-1], self.samplenum) >= 1):
            self.bidi_edges_ss.append(self.samplenum)
            self.bidi_states.append(bidi)

    def annotate_bidi(self):
        '''Annotate BiDi.'''
        # Dont litter code with range checks
        try:
            self.annotate_bidi_bits_bytes_and_errors()
            self.annotate_bidi_frame()
            self.annotate_bidi_id_and_data()
        except:
            pass

    def annotate_bidi_bits_bytes_and_errors(self):
        '''Annotate BiDi bits, bytes and errors.'''
        # Prepend two empty bytes if channel 1 has been empty
        if self.bidi_edges_ss[0] > self.ss_us2es(self.last_dcc_ss[-1],
                                                 BIDI_TTC1):
            self.bidi_bytes_ss.extend([0, 0])
            self.bidi_enc_bytes.extend([0, 0])

        # Reconstruct UART bits from edges only
        edge_count = len(self.bidi_edges_ss)
        i = 0
        while i < edge_count - 1:
            ss = self.bidi_edges_ss[i]
            byte = 0
            bit_count = 0

            while bit_count < 8 and i < edge_count - 1:
                state = self.bidi_states[i]
                bits_passed = self.ss_es2bidi_bits_passed(
                    self.bidi_edges_ss[i], self.bidi_edges_ss[i + 1])

                # Skip startbit
                if ss == self.bidi_edges_ss[i] and bits_passed >= 1:
                    bits_passed -= 1
                    if state != 0:
                        pass  # TODO what to do in this case?
                # Going to surpass endbit
                elif bit_count + bits_passed >= 8:
                    bits_passed = 8 - bit_count
                    i += state == 0

                mask = ((1 << bits_passed) - 1) * state
                byte |= mask << bit_count
                bit_count += bits_passed
                i += 1

            # Missing endbits (can only be 1)
            while bit_count < 8:
                byte |= 1 << bit_count
                bit_count += 1

            # Append ss and byte
            self.bidi_bytes_ss.append(ss)
            self.bidi_enc_bytes.append(byte)

            # Start bit
            for j in range(0, 1):
                self.put(self.ss_us2es(ss, j * BIDI_BIT_TIME),
                         self.ss_us2es(ss,
                                       (j + 1) * BIDI_BIT_TIME), self.out_ann,
                         [Ann.BIDI_BIT_START, ['Start Bit', 'Start', 'S']])

            # Data
            for j in range(1, 9):
                self.put(
                    self.ss_us2es(ss, j * BIDI_BIT_TIME),
                    self.ss_us2es(ss, (j + 1) * BIDI_BIT_TIME), self.out_ann,
                    [Ann.BIDI_BIT, [str(1 if byte & (1 << (j - 1)) else 0)]])

            # Stop bit
            for j in range(9, 10):
                self.put(self.ss_us2es(ss, j * BIDI_BIT_TIME),
                         self.ss_us2es(ss,
                                       (j + 1) * BIDI_BIT_TIME), self.out_ann,
                         [Ann.BIDI_BIT_STOP, ['Stop Bit', 'Stop', 'T']])

            # Byte
            self.put(self.ss_us2es(ss, 1 * BIDI_BIT_TIME),
                     self.ss_us2es(ss, 9 * BIDI_BIT_TIME), self.out_ann,
                     [Ann.BIDI_ENC_BYTE, ['0x{:02X}'.format(byte)]])
            self.put(
                self.ss_us2es(ss, 1 * BIDI_BIT_TIME),
                self.ss_us2es(ss, 9 * BIDI_BIT_TIME), self.out_ann,
                [Ann.BIDI_DEC_BYTE, ['0x{:02X}'.format(BIDI_DECODE[byte])]])

            # Error
            popcount = bin(byte).count('1')
            if popcount != 4:
                self.put(self.ss_us2es(ss, 1 * BIDI_BIT_TIME),
                         self.ss_us2es(ss, 9 * BIDI_BIT_TIME), self.out_ann,
                         [Ann.BIDI_ERROR, ['Invalid Byte']])

        # Append empty bytes if length < 8
        self.bidi_bytes_ss.extend([0] * (8 - len(self.bidi_bytes_ss)))
        self.bidi_enc_bytes.extend([0] * (8 - len(self.bidi_enc_bytes)))

    def annotate_bidi_frame(self):
        '''Annotate BiDi frame.'''
        # TCE (put it twice, so that the annotation stays visible)
        self.put(self.last_dcc_ss[-1],
                 self.ss_us2es(self.last_dcc_ss[-1], BIDI_TCE_MAX),
                 self.out_ann, [Ann.BIDI_FRAME_TCE, ['']])
        self.put(self.ss_us2es(self.last_dcc_ss[-1], BIDI_TTC2),
                 self.ss_us2es(self.last_dcc_ss[-1], BIDI_TCE_MAX),
                 self.out_ann, [Ann.BIDI_FRAME_TCE, ['Cutout End', 'TCE']])

        # TCS
        self.put(self.last_dcc_ss[-1],
                 self.ss_us2es(self.last_dcc_ss[-1], BIDI_TCS_MIN),
                 self.out_ann, [Ann.BIDI_FRAME_TCS, ['Cutout Start', 'TCS']])

        # CH1
        self.put(self.ss_us2es(self.last_dcc_ss[-1], BIDI_TTS1),
                 self.ss_us2es(self.last_dcc_ss[-1], BIDI_TTC1), self.out_ann,
                 [Ann.BIDI_FRAME_CH, ['Channel 1', 'CH1']])

        # CH2
        self.put(self.ss_us2es(self.last_dcc_ss[-1], BIDI_TTS2),
                 self.ss_us2es(self.last_dcc_ss[-1], BIDI_TTC2), self.out_ann,
                 [Ann.BIDI_FRAME_CH, ['Channel 2', 'CH2']])

    def annotate_bidi_id_and_data(self):
        '''Annotate BiDi ID and date.'''
        # No channel 1 data if first two bytes are 0
        i = int(self.bidi_enc_bytes[0] == 0) + int(self.bidi_enc_bytes[1] == 0)

        # Validate datagram before anything else
        if not bidi_validate_datagram(self.bidi_enc_bytes[i:]):
            return

        self.bidi_dec_bytes = bidi_decode_datagram(self.bidi_enc_bytes)

        while i < 8 and self.bidi_enc_bytes[i] != 0:
            id = self.bidi_dec_bytes[i] >> 2
            if self.bidi_enc_bytes[i] in BIDI_ACKS:
                i = self.annotate_bidi_ack(i)
            elif self.bidi_enc_bytes[i] == BIDI_NAK:
                i = self.annotate_bidi_nak(i)
            elif self.last_dcc_addr_type in ('BROADCAST', 'BASIC_LOCO',
                                             'EXT_LOCO'):
                if id == 0:
                    i = self.annotate_bidi_id_and_data_app_pom(i)
                elif id == 1:
                    i = self.annotate_bidi_id_and_data_app_adr_high(i)
                elif id == 2:
                    i = self.annotate_bidi_id_and_data_app_adr_low(i)
                elif id == 3:
                    if i < 2:
                        i = self.annotate_bidi_id_and_data_app_info1(i)
                    else:
                        i = self.annotate_bidi_id_and_data_app_ext(i)
                elif id == 4:
                    i = self.annotate_bidi_id_and_data_app_info(i)
                elif id == 7:
                    i = self.annotate_bidi_id_and_data_app_dyn(i)
                elif id in (8, 9, 10, 11):
                    i = self.annotate_bidi_id_and_data_app_xpom(i)
                elif id == 12:
                    i = self.annotate_bidi_id_and_data_app_cv_auto(i)
                elif id == 13:
                    i = self.annotate_bidi_id_and_data_app_block(i)
                elif id == 14:
                    i = self.annotate_bidi_id_and_data_app_search(i)
                else:
                    return
            elif self.last_dcc_addr_type in ('BASIC_ACCY', 'EXT_ACCY'):
                if i == 0:
                    i = self.annotate_bidi_id_and_data_app_srq(i)
                elif id == 0:
                    i = self.annotate_bidi_id_and_data_app_pom(i)
                elif id == 3:
                    i = self.annotate_bidi_id_and_data_app_stat4(i)
                elif id == 4:
                    i = self.annotate_bidi_id_and_data_app_stat1(i)
                elif id == 5:
                    i = self.annotate_bidi_id_and_data_app_time(i)
                elif id == 6:
                    i = self.annotate_bidi_id_and_data_app_error(i)
                elif id == 7:
                    i = self.annotate_bidi_id_and_data_app_dyn(i)
                elif id in (8, 9, 10, 11):
                    i = self.annotate_bidi_id_and_data_app_xpom(i)
                elif id == 12:
                    i = self.annotate_bidi_id_and_data_app_test(i)
                elif id == 13:
                    i = self.annotate_bidi_id_and_data_app_block(i)
                else:
                    return
            elif self.last_dcc_addr_type == 'AUTOMATIC_LOGON':
                if id == 13:
                    i = self.annotate_bidi_id_and_data_app_decoder_state(i)
                elif id == 15:
                    i = self.annotate_bidi_id_and_data_app_decoder_unique(i)
                return
            else:
                return

    def annotate_bidi_ack(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['ACK']])
        return i + 1

    def annotate_bidi_nak(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['NAK']])
        return i + 1

    def annotate_bidi_id_and_data_app_pom(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:pom ID=0', 'ID=0']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        data = bidi_make_data(datagram)
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV={}'.format(data)]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_adr_high(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:adr_high ID=1', 'ID=1']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['adr_high'] = bidi_make_data(datagram)
        self.bidi_annotate_app_adr_helper(i)
        return i + byte_count

    def annotate_bidi_id_and_data_app_adr_low(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:adr_low ID=2', 'ID=2']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['adr_low'] = bidi_make_data(datagram)
        self.bidi_annotate_app_adr_helper(i)
        return i + byte_count

    def annotate_bidi_id_and_data_app_info1(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:info1 ID=3', 'ID=3']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['info1'] = bidi_make_data(datagram)
        track_polarity = (self.bidi_app['info1'] >> 0) & 0b1
        ew = (self.bidi_app['info1'] >> 1) & 0b1
        driving = (self.bidi_app['info1'] >> 2) & 0b1
        consist = (self.bidi_app['info1'] >> 3) & 0b1
        addr_req = (self.bidi_app['info1'] >> 4) & 0b1
        self.put(
            self.bidi_bytes_ss[i + 1],
            self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
            self.out_ann, [
                Ann.BIDI_DATA,
                [
                    'Track Polarity={} | East-West={} | Driving={} | Consist={} | Addressing Request={}'
                    .format(track_polarity, ew, driving, consist, addr_req),
                    'Pol={} | EW={} | Drv={} | C={} | AddrReq={}'.format(
                        track_polarity, ew, driving, consist, addr_req)
                ]
            ])
        return i + byte_count

    def annotate_bidi_id_and_data_app_ext(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:ext ID=3', 'ID=3']])
        byte_count = bidi_datagram_size(18)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['ext'] = bidi_make_data(datagram)
        type_map = {
            0b1000: 'Reserved',
            0b1001: 'Reserved',
            0b1010: 'Gas Station',
            0b1011: 'Coal Depot',
            0b1100: 'Water Crane',
            0b1101: 'Sand Store',
            0b1110: 'Charging Station',
            0b1111: 'Filling Station'
        }
        type = type_map.get(self.bidi_app['ext'] >> 8, 'Address Only')
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, [type]])
        position = self.bidi_app[
            'ext'] if type == 'Address Only' else self.bidi_app['ext'] & 0xFF
        self.put(
            self.bidi_bytes_ss[i + 2],
            self.ss_us2es(self.bidi_bytes_ss[i + 2], 10 * BIDI_BIT_TIME),
            self.out_ann, [
                Ann.BIDI_DATA,
                ['Position={}'.format(position), 'Pos={}'.format(position)]
            ])
        return i + byte_count

    def annotate_bidi_id_and_data_app_info(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['TODO']])
        byte_count = bidi_datagram_size(36)
        return i + byte_count

    def annotate_bidi_id_and_data_app_dyn(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:dyn ID=7', 'ID=7']])
        byte_count = bidi_datagram_size(18)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['dyn'] = bidi_make_data(datagram)
        x = self.bidi_app['dyn'] & 0x3F
        d = self.bidi_app['dyn'] >> 6
        if x == 0:
            d_anns = ['{}km/h'.format(d)]
            x_anns = [
                'Actual Speed X={}'.format(x), 'Speed X={}'.format(x),
                'X={}'.format(x)
            ]
        elif x == 1:
            d_anns = ['{}km/h'.format(256 + d)]
            x_anns = [
                'Actual Speed X={}'.format(x), 'Speed X={}'.format(x),
                'X={}'.format(x)
            ]
        elif x == 2:
            if d & 0x80:
                d_anns = [
                    'Load={} (RCN-600)'.format(d), 'Load={}'.format(d),
                    'L={}'.format(d)
                ]
                x_anns = ['Load X={}'.format(x), 'X={}'.format(x)]
            else:
                d_anns = [
                    'Speed={}/128'.format(d & 0x7F),
                    'S={}/128'.format(d & 0x7F)
                ]
                x_anns = ['Speed Steps X={}'.format(x), 'X={}'.format(x)]
        elif x == 3:
            major = (d >> 4) & 0x0F
            minor = (d >> 0) & 0x0F
            d_anns = ['v{}.{}'.format(major, minor)]
            x_anns = ['RailCom Version X={}'.format(x), 'X={}'.format(x)]
        elif x == 4:
            d_anns = ['{:08b}'.format(d)]
            x_anns = ['Change Flags X={}'.format(x), 'X={}'.format(x)]
        elif x == 5:
            d_anns = ['{:08b}'.format(d)]
            x_anns = ['Flag Register X={}'.format(x), 'X={}'.format(x)]
        elif x == 6:
            d_anns = ['{:08b}'.format(d)]
            x_anns = ['Input Register X={}'.format(x), 'X={}'.format(x)]
        elif x == 7:
            d_anns = ['{}%'.format(d)]
            x_anns = [
                'Quality of Service X={}'.format(x), 'QoS X={}'.format(x),
                'X={}'.format(x)
            ]
        elif 8 <= i <= 19:
            d_anns = ['{}%'.format(d)]
            x_anns = [
                'Container {} Level X={}'.format(x - 7, x), 'X={}'.format(x)
            ]
        elif x == 20:
            # Optional second dyn
            next_id = self.bidi_dec_bytes[i + byte_count] >> 2
            datagram = self.bidi_dec_bytes[i + byte_count:i + byte_count * 2]
            second_dyn = bidi_make_data(datagram)
            x2 = second_dyn & 0x3F
            d2 = second_dyn >> 6
            if next_id == 7 and x2 == 20:
                d_anns = ['Position={}'.format(d2 << 8 | d)]
            else:
                d_anns = ['Position={}'.format(d)]
            x_anns = ['Position (app:ext) X={}'.format(x), 'X={}'.format(x)]
        elif x == 21:
            # Related to DV
            if (d >> 6) & 0b1:
                d_anns = ['Related to DV={} Alarm={}'.format(d & 0x3F, d >> 7)]
            # MOB alarm
            elif self.last_dcc_addr_type in ('BROADCAST', 'BASIC_LOCO',
                                             'EXT_LOCO'):
                if d == 128:
                    d_anns = ['Motor Short']
                elif d == 129:
                    d_anns = ['Function Short']
                elif d == 130:
                    d_anns = ['Overtemperature']
                else:
                    d_anns = ['?']
            # STAT alarm
            elif self.last_dcc_addr_type in ('BASIC_ACCY', 'EXT_ACCY'):
                if 128 <= i <= 135:
                    d_anns = ['Output {} Short'.format(i - 127)]
                elif d == 136:
                    d_anns = ['Overtemperature']
                else:
                    d_anns = ['?']
            x_anns = [
                'Status and Alarm Messages X={}'.format(x), 'X={}'.format(x)
            ]
        elif x == 22:
            d_anns = ['{}'.format(d)]
            x_anns = ['Trip Odometer X={}'.format(x), 'X={}'.format(x)]
        elif x == 23:
            d_anns = ['{}'.format(d)]
            x_anns = ['Maintenance Interval X={}'.format(x), 'X={}'.format(x)]
        elif x == 26:
            d_anns = ['{}°C'.format(d - 50)]
            x_anns = ['Temperature X={}'.format(x), 'X={}'.format(x)]
        elif x == 27:
            dir = (d >> 0) & 0b1
            ew = (d >> 1) & 0b1
            dir_ctrl = (d >> 2) & 0b1
            dir_chg = (d >> 3) & 0b1
            ew_hide = (d >> 4) & 0b1
            ew_inv = (d >> 5) & 0b1
            d_anns = [
                'Direction={} | East-West={} | Direction Control={} | Direction Change={} | HideUI={} | East-West-Inverted={}'
                .format(dir, ew, dir_ctrl, dir_chg, ew_hide, ew_inv),
                'D={} | EW={} | DCtrl={} | DChg={} | HideUI={} | EWInv={}'.
                format(dir, ew, dir_ctrl, dir_chg, ew_hide, ew_inv)
            ]
            x_anns = [
                'Direction Status Byte X={}'.format(x),
                'Direction Status X={}'.format(x), 'X={}'.format(x)
            ]
        elif x == 34:
            d_anns = ['{}'.format(d - 128)]
            x_anns = ['Control Deviation X={}'.format(x), 'X={}'.format(x)]
        elif x == 46:
            d_anns = ['{}V'.format(5 + d * 0.1)]
            x_anns = [
                'Track Voltage X={}'.format(x), 'Voltage X={}'.format(x),
                'X={}'.format(x)
            ]
        elif x == 47:
            d_anns = ['{}m'.format(d * 4)]
            x_anns = ['Stopping Distance X={}'.format(x), 'X={}'.format(x)]
        else:
            d_anns = ['? D={}'.format(d), 'D={}'.format(d)]
            x_anns = ['? X={}'.format(x), 'X={}'.format(x)]
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, d_anns])
        self.put(self.bidi_bytes_ss[i + 2],
                 self.ss_us2es(self.bidi_bytes_ss[i + 2], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, x_anns])
        return i + byte_count

    def annotate_bidi_id_and_data_app_xpom(self, i):
        id = self.bidi_dec_bytes[i] >> 2
        self.put(
            self.bidi_bytes_ss[i],
            self.ss_us2es(self.bidi_bytes_ss[i],
                          10 * BIDI_BIT_TIME), self.out_ann,
            [Ann.BIDI_ID, ['app:xpom ID={}'.format(id), 'ID={}'.format(id)]])
        byte_count = bidi_datagram_size(36)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['xpom'] = bidi_make_data(datagram)
        ss = id & 0b11
        cvs = [(self.bidi_app['xpom'] >> shift) & 0xFF
               for shift in (24, 16, 8, 0)]
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['SS={:02b}'.format(ss)]])
        self.put(self.bidi_bytes_ss[i + 2],
                 self.ss_us2es(self.bidi_bytes_ss[i + 2], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV[0]={}'.format(cvs[0])]])
        self.put(self.bidi_bytes_ss[i + 3],
                 self.ss_us2es(self.bidi_bytes_ss[i + 3], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV[1]={}'.format(cvs[1])]])
        self.put(self.bidi_bytes_ss[i + 4],
                 self.ss_us2es(self.bidi_bytes_ss[i + 4], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV[2]={}'.format(cvs[2])]])
        self.put(self.bidi_bytes_ss[i + 5],
                 self.ss_us2es(self.bidi_bytes_ss[i + 5], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV[3]={}'.format(cvs[3])]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_cv_auto(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:CV-auto ID12', 'ID12']])
        byte_count = bidi_datagram_size(36)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['CV-auto'] = bidi_make_data(datagram)
        cv31 = (self.bidi_app['CV-auto'] >> 24) & 0xFF
        cv32 = (self.bidi_app['CV-auto'] >> 16) & 0xFF
        cv_offset = (self.bidi_app['CV-auto'] >> 8) & 0xFF
        cv_addr = cv31 << 16 | cv32 << 8 | cv_offset << 0
        cv_value = (self.bidi_app['CV-auto'] >> 0) & 0xFF
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV31={}'.format(cv31)]])
        self.put(self.bidi_bytes_ss[i + 2],
                 self.ss_us2es(self.bidi_bytes_ss[i + 2], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV32={}'.format(cv32)]])
        self.put(self.bidi_bytes_ss[i + 3],
                 self.ss_us2es(self.bidi_bytes_ss[i + 3],
                               10 * BIDI_BIT_TIME), self.out_ann,
                 [Ann.BIDI_DATA, ['CV#(rel)={}'.format(cv_offset + 1)]])
        self.put(self.bidi_bytes_ss[i + 4],
                 self.ss_us2es(self.bidi_bytes_ss[i + 4],
                               10 * BIDI_BIT_TIME), self.out_ann,
                 [Ann.BIDI_DATA, ['CV#(abs)={}'.format(cv_addr + 1)]])
        self.put(self.bidi_bytes_ss[i + 5],
                 self.ss_us2es(self.bidi_bytes_ss[i + 5], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['CV={}'.format(cv_value)]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_block(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['TODO']])
        byte_count = bidi_datagram_size(36)
        return i + byte_count

    def annotate_bidi_id_and_data_app_search(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:search ID=14', 'ID=14']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['search'] = bidi_make_data(datagram)
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [
                     Ann.BIDI_ID,
                     [
                         'Time={}s'.format(self.bidi_app['search']),
                         '{}s'.format(self.bidi_app['search'])
                     ]
                 ])
        return i + byte_count

    def annotate_bidi_id_and_data_app_srq(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:srq']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['srq'] = bidi_make_data(datagram)
        addr_type = 'Extended' if self.bidi_app['srq'] >> 11 else 'Basic'
        addr = self.bidi_app['srq'] & 0x7FF
        anns = '{} Accessory={}'.format(addr_type, addr)
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, [anns, str(addr)]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_stat4(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:stat4 ID=3', 'ID=3']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['stat4'] = bidi_make_data(datagram)
        rs_map = {0b10: '0', 0b01: '1'}
        rs = [(self.bidi_app['stat4'] >> shift) & 0b11
              for shift in (6, 4, 2, 0)]
        anns = ' '.join('R{}={}'.format(4 - i, rs_map.get(r, '?'))
                        for i, r in enumerate(rs))
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, [anns]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_stat1(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:stat1 ID=4', 'ID=4']])
        byte_count = bidi_datagram_size(12)
        # First stat1
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['stat1'] = bidi_make_data(datagram)
        bit6 = (self.bidi_app['stat1'] >> 6) & 0b1
        bit5 = (self.bidi_app['stat1'] >> 5) & 0b1
        aspect = self.bidi_app['stat1'] & 0b11111
        # Optional second stat1 for extended accessories
        next_id = self.bidi_dec_bytes[i + byte_count] >> 2
        if self.last_dcc_addr_type == 'EXT_ACCY' and next_id == 4:
            datagram = self.bidi_dec_bytes[i + byte_count:i + byte_count * 2]
            self.bidi_app['stat1'] = bidi_make_data(datagram)
            aspect = (self.bidi_app['stat1'] & 0b111) << 5 | aspect
            self.put(
                self.bidi_bytes_ss[i + 1],
                self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                self.out_ann, [
                    Ann.BIDI_DATA,
                    [
                        'Initial State Matches Last Received={}'.format(bit6),
                        'Bit6={}'.format(bit6)
                    ]
                ])
            self.put(
                self.bidi_bytes_ss[i + 2],
                self.ss_us2es(self.bidi_bytes_ss[i + 2], 10 * BIDI_BIT_TIME),
                self.out_ann, [
                    Ann.BIDI_DATA,
                    [
                        'Returned Aspect Based on Feedback={}'.format(bit6),
                        'Bit5={}'.format(bit5)
                    ]
                ])
            self.put(
                self.bidi_bytes_ss[i + 3],
                self.ss_us2es(self.bidi_bytes_ss[i + 3], 10 * BIDI_BIT_TIME),
                self.out_ann, [Ann.BIDI_DATA, ['Aspect={}'.format(aspect)]])
            return i + byte_count * 2
        # Only single stat1 for basic accessories (or if next ID ain't 4 as well)
        else:
            self.put(
                self.bidi_bytes_ss[i + 1],
                self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                self.out_ann, [
                    Ann.BIDI_DATA,
                    [
                        'Initial State Matches Last Received={} Returned Aspect Based on Feedback={} Aspect={}'
                        .format(bit6, bit5, aspect),
                        'Bit6={} Bit5={} Aspect={}'.format(bit6, bit5, aspect)
                    ]
                ])
            return i + byte_count

    def annotate_bidi_id_and_data_app_time(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:time ID=5', 'ID=5']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['time'] = bidi_make_data(datagram)
        res = 1.0 if self.bidi_app['time'] & 0x80 else 0.1
        time = res * (self.bidi_app['time'] & 0x7F)
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['Time={:.2f}s'.format(time)]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_error(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['app:error ID=6', 'ID=6']])
        byte_count = bidi_datagram_size(12)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['error'] = bidi_make_data(datagram)
        code_map = {
            0x00: 'None',
            0x01: 'Invalid Command',
            0x02: 'Overcurrent',
            0x03: 'Undervoltage',
            0x04: 'Fuse',
            0x05: 'Overtemperature',
            0x06: 'Feedback',
            0x07: 'Manual Operation',
            0x10: 'Signal',
            0x20: 'Servo',
            0x3F: 'Internal'
        }
        add = (self.bidi_app['error'] >> 6) & 0b1
        err_str = code_map.get(self.bidi_app['error'] & 0x3F, '?')
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [
                     Ann.BIDI_DATA,
                     [
                         'Additional Errors={} Code={}'.format(add, err_str),
                         'Bit6={} Code={}'.format(add, err_str)
                     ]
                 ])
        return i + byte_count

    def annotate_bidi_id_and_data_app_test(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['TODO']])
        byte_count = bidi_datagram_size(36)
        return i + byte_count

    def annotate_bidi_id_and_data_app_decoder_state(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i],
                               10 * BIDI_BIT_TIME), self.out_ann,
                 [Ann.BIDI_ID, ['app:decoder_state ID=13', 'ID=13']])
        byte_count = bidi_datagram_size(48)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['decoder_state'] = bidi_make_data(datagram)
        # Change flags
        flags = (self.bidi_app['decoder_state'] >> 36) & 0xFF
        fstr = 'CID={} | '.format((flags >> 0) & 0b1)
        fstr += 'FW={} | '.format((flags >> 1) & 0b1)
        fstr += 'Driving/Switching Behavior={} | '.format((flags >> 2) & 0b1)
        fstr += 'Mapping={} | '.format((flags >> 3) & 0b1)
        fstr += 'GUI={} | '.format((flags >> 4) & 0b1)
        fstr += 'Consist={} | '.format((flags >> 5) & 0b1)
        fstr += 'Address/ShortGUI={}'.format((flags >> 7) & 0b1)
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, [fstr]])
        # Change count
        change_count = (self.bidi_app['decoder_state'] >> 24) & 0xFFF
        self.put(self.bidi_bytes_ss[i + 2],
                 self.ss_us2es(self.bidi_bytes_ss[i + 2],
                               10 * BIDI_BIT_TIME), self.out_ann,
                 [Ann.BIDI_ID, ['Change count={}'.format(change_count)]])
        # Extended capabilities
        caps = (self.bidi_app['decoder_state'] >> 8) & 0xFFFF
        fstr = 'Dynamic CH1={} | '.format((caps >> 8) & 0b1)
        fstr += 'Info1 (ID3)={} | '.format((caps >> 9) & 0b1)
        fstr += 'Location Service (ID3)={} | '.format((caps >> 10) & 0b1)
        fstr += 'Speed (ID7:0-1)={} | '.format((caps >> 11) & 0b1)
        fstr += 'QoS (ID7:7)={} | '.format((caps >> 12) & 0b1)
        fstr += 'Status and Error Messages (ID7:21)={} | '.format((caps >> 13)
                                                                  & 0b1)
        fstr += 'Temperature (ID7:26)={} | '.format((caps >> 14) & 0b1)
        fstr += 'Direction Status Byte (ID7:27)={} | '.format((caps >> 15)
                                                              & 0b1)
        fstr += 'CV-Auto (ID12)={} | '.format((caps >> 16) & 0b1)
        fstr += 'Binary State Short={} | '.format((caps >> 17) & 0b1)
        fstr += 'Binary State Long={} | '.format((caps >> 18) & 0b1)
        fstr += 'Speed, Direction and Functions={} | '.format((caps >> 19)
                                                              & 0b1)
        fstr += 'CV Access Short | '.format((caps >> 20) & 0b1)
        fstr += 'Special Operating Modes={} | '.format((caps >> 22) & 0b1)
        fstr += 'Multiple Instructions Single Packet={}'.format((caps >> 23)
                                                                & 0b1)
        self.put(self.bidi_bytes_ss[i + 3],
                 self.ss_us2es(self.bidi_bytes_ss[i + 6], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, [fstr]])
        # CRC
        crc = (self.bidi_app['decoder_state'] >> 0) & 0xFF
        self.put(self.bidi_bytes_ss[i + 7],
                 self.ss_us2es(self.bidi_bytes_ss[i + 7], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_ID, ['CRC=0x{:02X}'.format(crc)]])
        return i + byte_count

    def annotate_bidi_id_and_data_app_decoder_unique(self, i):
        self.put(self.bidi_bytes_ss[i],
                 self.ss_us2es(self.bidi_bytes_ss[i],
                               10 * BIDI_BIT_TIME), self.out_ann,
                 [Ann.BIDI_ID, ['app:decoder_unique ID=15', 'ID=15']])
        byte_count = bidi_datagram_size(48)
        datagram = self.bidi_dec_bytes[i:i + byte_count]
        self.bidi_app['decoder_unique'] = bidi_make_data(datagram)
        # Manufacturer ID
        mid = (self.bidi_app['decoder_unique'] >> 32) & 0xFFF
        self.put(self.bidi_bytes_ss[i + 1],
                 self.ss_us2es(self.bidi_bytes_ss[i + 1], 10 * BIDI_BIT_TIME),
                 self.out_ann, [
                     Ann.BIDI_DATA,
                     ['Manufacturer ID={}'.format(mid), 'MID={}'.format(mid)]
                 ])
        # UID
        uid = self.bidi_app['decoder_unique'] & 0xFFFFFFFF
        self.put(self.bidi_bytes_ss[i + 2],
                 self.ss_us2es(self.bidi_bytes_ss[i + 7], 10 * BIDI_BIT_TIME),
                 self.out_ann, [Ann.BIDI_DATA, ['UID={}'.format(uid)]])
        return i + byte_count

    def csv_writerow(self):
        '''Write row to .csv binary output.'''
        # No prior DCC packet
        if not self.last_dcc_ss:
            return
        # 'timestamp' column
        timestamp_str = '{:.6f},'.format(self.last_dcc_ss[0] / self.samplerate)
        self.put(0, 0, self.out_binary, [0, timestamp_str.encode('utf-8')])
        # 'dcc' column
        dcc_str = '0x' + ''.join('{:02X}'.format(b)
                                 for b in self.last_dcc_bytes)
        self.put(0, 0, self.out_binary, [0, dcc_str.encode('utf-8')])
        # 'bidi' column
        if self.has_channel(Pin.BIDI):
            self.bidi_enc_bytes.extend([0] * (8 - len(self.bidi_enc_bytes)))
            bidi_str = ',0x' + ''.join('{:02X}'.format(b)
                                       for b in self.bidi_enc_bytes)
            self.put(0, 0, self.out_binary, [0, bidi_str.encode('utf-8')])
        self.put(0, 0, self.out_binary, [0, '\n'.encode('utf-8')])
