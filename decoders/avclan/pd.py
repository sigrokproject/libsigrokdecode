##
# This file is part of the libsigrokdecode project.
##
# Copyright (C) 2023 Maciej Grela <enki@fsck.pl>
##
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
##
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
##
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# pylint: disable=missing-module-docstring

from collections import namedtuple
import sigrokdecode as srd  # pylint: disable=import-error
from .lists import *  # pylint: disable=wildcard-import,unused-wildcard-import

DataByte = namedtuple('DataByte', ['b', 'ss', 'es'])


# Reference: https://docs.python.org/3/library/itertools.html
def first_true(iterable, default=None, pred=None):
    """Returns the first true value in the iterable.

    If no true value is found, returns *default*

    If *pred* is not None, returns the first item
    for which pred(item) is true.

    """
    # first_true([a,b,c], x) --> a or b or c or x
    # first_true([a,b], x, f) --> a if f(a) else b if f(b) else x
    return next(filter(pred, iterable), default)


class Decoder(srd.Decoder):  # pylint: disable=too-many-instance-attributes
    '''AVC-LAN Decoder class used by libsigrokdecode.'''

    api_version = 3
    id = 'avclan'
    name = 'AVC-LAN'
    longname = 'AVC-LAN Toyota Audio-Video Local Area Network'
    desc = 'AVC-LAN Protocol Decoder (IEBus Mode 2 variant)'
    license = 'gplv3+'
    inputs = ['iebus']
    outputs = []
    tags = ['Automotive']
    channels = ()
    options = ()
    annotations = (
        ('address', 'Device Address'),      # 0
        ('function', 'Function'),           # 1

        # Control Protocol
        ('ctrl-opcode', 'Opcode'),          # 2
        ('sequence-no', 'Sequence No.'),    # 3
        ('advertised-function', 'Function'),  # 4

        # HU Commands
        ('cmd-opcode', 'Opcode'),           # 5

        # CD Player
        ('cd-opcode', 'Opcode'),            # 6
        ('cd-state', 'State'),              # 7
        ('cd-flags', 'Flags'),              # 8
        ('disc-number', 'Disc Number'),     # 9
        ('track-number', 'Track Number'),   # 10
        ('disc-title', 'Disc Name'),        # 11
        ('track-title', 'Track Name'),      # 12
        ('playback-time', 'Playback time'),  # 13
        ('disc-slots', 'Disc Slots'),       # 14

        # Audio AMP
        ('audio-opcode', 'Opcode'),         # 15
        ('audio-flags', 'Audio Flags'),     # 16
        ('volume', 'Volume'),               # 17
        ('bass', 'Bass'),                   # 18
        ('treble', 'Treble'),               # 19
        ('fade', 'Fade'),                   # 20
        ('balance', 'Balance'),             # 21

        # TUNER (radio)
        ('radio-opcode', 'Opcode'),         # 22
        ('radio-state', 'State'),           # 23
        ('radio-mode', 'Mode'),             # 24
        ('radio-flags', 'Flags'),           # 25
        ('band', 'Band'),                   # 26
        ('channel', 'Channel'),             # 27
        ('freq', 'Frequency'),              # 28

        ('warning', 'Warning')
    )

    annotation_rows = (
        ('devices', 'Device Addresses and Functions', (0, 1)),
        ('control', 'Network Control', (2, 3, 4)),
        ('cmd', 'HU Commands', (5,)),
        ('cd', 'CD Player', (6, 7, 8, 9, 10, 11, 12, 13, 14)),
        ('audio', 'Audio Amplifier', (15, 16, 17, 18, 19, 20, 21)),
        ('radio', 'Radio Tuner', (22, 23, 24, 25, 26, 27, 28)),
        ('warnings', 'Warnings', (29,))
    )


    def __init__(self):
        # Make pylint happy (attribute-defined-outside-init checker)
        self.state = None
        self.broadcast_bit = None
        self.master_addr = self.slave_addr = None
        self.control = None
        self.data_length = self.data_bytes = None
        self.from_function = self.to_function = None
        self.samplerate = None
        self.out_ann = None

        self.reset()


    def reset(self):
        '''Reset decoder state.'''
        self.state = 'IDLE'
        self.broadcast_bit = None
        self.master_addr = self.slave_addr = None
        self.control = None
        self.data_length = self.data_bytes = None
        self.from_function = self.to_function = None


    def start(self):
        '''Start decoder.'''
        self.out_ann = self.register(srd.OUTPUT_ANN)


    def metadata(self, key, value):
        '''Handle metadata input from libsigrokdecode.'''
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value


    def find_annotation(self, anno_name: str):
        '''Find an annotation index based on its name.'''
        return first_true(enumerate(self.annotations), default=(None, (None, None)),
                          pred=lambda item: item[1][0] == anno_name)


    def putx(self, anno_name: str, ss, es, v):
        '''Put in an annotation using its name.'''
        (idx, _) = self.find_annotation(anno_name)
        if idx is None:
            raise RuntimeError(f'Cannot find annotation name {anno_name}')
        self.put(ss, es, self.out_ann, [idx, v])


    def pkt_from_12(self):
        '''Handle frames from function 12(COMMUNICATION)'''
        self.pkt_comm_ctrl()


    def pkt_to_12(self):
        '''Handle frames to function 12(COMMUNICATION)'''
        self.pkt_comm_ctrl()


    def pkt_to_01(self):
        '''Handle frames to function 01(COMM_CTRL).'''
        self.pkt_comm_ctrl()


    def pkt_from_01(self):
        '''Handle frames from function 01(COMM_CTRL).'''
        self.pkt_comm_ctrl()


    def pkt_comm_ctrl(self):
        '''Handle control protocol frames.'''
        opcode = self.data_bytes[0].b
        opcode_anno = f'{opcode:02x}'

        if CommCtrlOpcodes.has_value(opcode):
            opcode = CommCtrlOpcodes(opcode)

            self.putx('ctrl-opcode', self.data_bytes[0].ss, self.data_bytes[0].es,
                      [f'Opcode: {opcode.name}', opcode.name]
                      )

            if opcode == CommCtrlOpcodes.ADVERTISE_FUNCTION:
                logic_id = self.data_bytes[1].b
                if FunctionIDs.has_value(logic_id):
                    logic_id = FunctionIDs(logic_id)
                    self.putx('advertised-function',
                              self.data_bytes[1].ss, self.data_bytes[1].es,
                              [f'Function: {logic_id.name}', logic_id.name]
                              )

            elif opcode == CommCtrlOpcodes.PING_REQ:
                sequence = self.data_bytes[1].b
                self.putx('sequence-no', self.data_bytes[1].ss, self.data_bytes[1].es,
                          [f'Sequence Number: {sequence}', str(sequence), 'Seq'])

            elif opcode == CommCtrlOpcodes.PING_RESP:
                sequence = self.data_bytes[1].b
                self.putx('sequence-no', self.data_bytes[1].ss, self.data_bytes[1].es,
                          [f'Sequence Number: {sequence}', str(sequence), 'Seq'])

            elif opcode == CommCtrlOpcodes.LIST_FUNCTIONS_RESP:
                for (idx, logical_addr) in enumerate([d.b for d in self.data_bytes[1:]], 1):
                    anno = f'{logical_addr:02x}'
                    if FunctionIDs.has_value(logical_addr):
                        logical_addr = FunctionIDs(logical_addr)
                        anno = logical_addr.name

                    self.putx('advertised-function',
                                self.data_bytes[idx].ss, self.data_bytes[idx].es,
                                [f'Function: {anno}', anno, 'Func'])
            return True

        return False


    def pkt_from_25(self):
        '''Handle frames from function 25(CMD_SW).'''
        opcode = self.data_bytes[0].b
        if CmdSwOpcodes.has_value(opcode):
            opcode = CmdSwOpcodes(opcode)

            self.putx('cmd-opcode', self.data_bytes[0].ss, self.data_bytes[0].es,
                      [f'Opcode: {opcode.name}', opcode.name]
                      )
        return False


    def pkt_from_60(self):
        '''Handle frames from function 60(TUNER).'''
        opcode = self.data_bytes[0].b

        if TunerOpcodes.has_value(opcode):
            opcode = TunerOpcodes(opcode)

            self.putx('radio-opcode', self.data_bytes[0].ss, self.data_bytes[0].es,
                      [f'Opcode: {opcode.name}', opcode.name]
                      )

            if opcode == TunerOpcodes.REPORT:
                tuner_state = self.data_bytes[1].b
                if TunerState.has_value(tuner_state):
                    tuner_state = TunerState(tuner_state)

                    self.putx('radio-state', self.data_bytes[1].ss, self.data_bytes[1].es,
                              [f'State: {tuner_state.name}', tuner_state.name])

                tuner_mode = self.data_bytes[2].b
                if TunerModes.has_value(tuner_mode):
                    tuner_mode = TunerModes(tuner_mode)

                    self.putx('radio-mode', self.data_bytes[2].ss, self.data_bytes[2].es,
                              [f'Mode: {tuner_mode.name}', tuner_mode.name, 'Mode'])

                # Did not know how to properly implement this with Python enums
                band_type = self.data_bytes[3].b & 0xF0
                band_number = self.data_bytes[3].b & 0x0F
                if band_type == 0x80:
                    band_type = 'FM'
                    freq_start = 87.5
                    freq_step = 0.05
                    freq_unit = 'MHz'
                elif band_type == 0xC0:
                    # Long Wave broadcast band
                    band_type = 'AM'
                    freq_start = 153
                    freq_step = 1
                    freq_unit = 'kHz'
                elif band_type == 0x00:
                    # Medium Wave broadcast band
                    band_type = 'AM'
                    freq_start = 522
                    freq_step = 9
                    freq_unit = 'kHz'

                self.putx('band', self.data_bytes[3].ss, self.data_bytes[3].es,
                          [f'Band: {band_type} {band_number}',
                           f'{band_type} {band_number}', 'Band'])

                # Frequency is 2 bytes big-endian
                freq = 256 * self.data_bytes[4].b + self.data_bytes[5].b
                freq = freq_start + (freq-1) * freq_step
                self.putx('freq', self.data_bytes[4].ss, self.data_bytes[5].es,
                          [f'Freq: {freq} {freq_unit}', f'{freq} {freq_unit}', 'Freq'])

                channel = self.data_bytes[6].b
                if channel > 0:
                    self.putx('channel', self.data_bytes[6].ss, self.data_bytes[6].es,
                              [f'CH #{channel}', 'CH'])

                flags1 = TunerFlags(self.data_bytes[7].b)
                self.putx('radio-flags', self.data_bytes[7].ss, self.data_bytes[7].es,
                          [f'Flags: {str(flags1)}', 'Flags', 'F'])
                flags2 = TunerFlags(self.data_bytes[8].b)
                self.putx('radio-flags', self.data_bytes[8].ss, self.data_bytes[8].es,
                          [f'Flags: {str(flags2)}', 'Flags', 'F'])

            return True

        return False


    def bcd2dec(self, b: int):
        '''Convert a BCD encoded byte to a decimal integer.'''
        return 10 * ((b & 0xF0) >> 4) + (b & 0x0F)


    def pkt_from_62(self):
        '''Handle frames from function 62(CD).'''
        self.pkt_from_cd_player()


    def pkt_from_63(self):
        '''Handle frames from function 63(CD_CHANGER).'''
        self.pkt_from_cd_player()


    def pkt_from_43(self):
        '''Handle frames from function 43(CD_CHANGER2)'''
        self.pkt_from_cd_player()


    def pkt_from_cd_player(self):
        '''Handle frames from a CD player.'''
        opcode = self.data_bytes[0].b
        opcode_anno = f'{opcode:02x}'
        ret = False

        if CDOpcodes.has_value(opcode):
            opcode = CDOpcodes(opcode)
            opcode_anno = opcode.name

            if opcode == CDOpcodes.REPORT_PLAYBACK:
                cd_state = self.data_bytes[2].b

                anno = str(CDStateCodes(cd_state))
                self.putx('cd-state', self.data_bytes[2].ss, self.data_bytes[2].es,
                              [f'State: {anno}', anno, 'State'])

                # This is always 0x01 for builtin CD player
                disc_number = self.data_bytes[3].b
                anno = [ 'CD #', 'CD', 'C' ]
                if disc_number != 0xff:
                    anno.insert(0, f'CD #{disc_number}')

                self.putx('disc-number', self.data_bytes[3].ss, self.data_bytes[3].es, anno)
                
                track_number = self.data_bytes[4].b
                anno = [ 'Track #', 'Tra', 'T' ]
                if track_number != 0xff:
                    anno.insert(0, f'Track #{track_number}')

                self.putx('track-number', self.data_bytes[4].ss, self.data_bytes[4].es, anno)

                minutes = self.data_bytes[5].b
                seconds = self.data_bytes[6].b
                anno = ['Time', 'T']
                if minutes != 0xff and seconds != 0xff:
                    minutes = self.bcd2dec(minutes)
                    seconds = self.bcd2dec(seconds)
                    anno.insert(0, f'{minutes:02d}:{seconds:02d}')
                    anno.insert(0, f'Time: {minutes:02d}:{seconds:02d}')

                self.putx('playback-time', self.data_bytes[5].ss, self.data_bytes[6].es, anno)

                cd_flags = self.data_bytes[7].b
                anno = str(CDFlags(cd_flags))
                self.putx('cd-flags', self.data_bytes[7].ss, self.data_bytes[7].es,
                          [f'Flags: {anno}', anno, 'Flags'])

            elif opcode == CDOpcodes.REPORT_TRACK_NAME:
                disc_number = self.data_bytes[1].b
                track_number = self.data_bytes[2].b
                text = ''.join([chr(d.b) for d in self.data_bytes[5:]])
                if disc_number != 0xff:
                    self.putx('disc-number', self.data_bytes[1].ss, self.data_bytes[1].es,
                              [f'CD #{disc_number}', 'CD #'])
                self.putx('track-number', self.data_bytes[2].ss, self.data_bytes[2].es,
                          [f'Track #{track_number}', 'Track #'])
                self.putx('track-title', self.data_bytes[5].ss, self.data_bytes[-1].es,
                        [f'Title: {text}', 'Title'])

            elif opcode == CDOpcodes.REPORT_LOADER:

                slots = self.data_bytes[2].b
                anno = str(CDSlots(slots))
                self.putx('disc-slots', self.data_bytes[2].ss, self.data_bytes[2].es,
                          [f'Slots-1: {anno}', anno, 'Slots-1'])

                slots = self.data_bytes[4].b
                anno = str(CDSlots(slots))
                self.putx('disc-slots', self.data_bytes[4].ss, self.data_bytes[4].es,
                          [f'Slots-2: {anno}', anno, 'Slots-2'])

                slots = self.data_bytes[6].b
                anno = str(CDSlots(slots))
                self.putx('disc-slots', self.data_bytes[6].ss, self.data_bytes[6].es,
                          [f'Slots-3: {anno}', anno, 'Slots-3'])


            ret = True

        self.putx('cd-opcode', self.data_bytes[0].ss, self.data_bytes[0].es, 
                    [f'Opcode: {opcode_anno}', opcode_anno, 'Opcode'])
        return ret


    def map_left_right(self, value: int, center: int,
                       negative_tag: str = '-', positive_tag: str = '+'):
        '''
        Map values corresponding to left/right or front/back settings to strings.
        Used for balance, fade and so on.
        '''
        value -= center
        if value < 0:
            return f'{negative_tag}{abs(value)}'
        if value > 0:
            return f'{positive_tag}{abs(value)}'
        return '0'


    def pkt_74(self):
        '''Handle frames to/from function 74(AUDIO_AMP)'''
        opcode = self.data_bytes[0].b

        if AudioAmpOpcodes.has_value(opcode):
            opcode = AudioAmpOpcodes(opcode)

            self.putx('audio-opcode', self.data_bytes[0].ss, self.data_bytes[0].es,
                      [f'Opcode: {opcode.name}', opcode.name]
                      )

            if opcode == AudioAmpOpcodes.REPORT:
                # First byte is always 0x80 in volume reports
                volume = self.data_bytes[2].b
                self.putx('volume', self.data_bytes[2].ss, self.data_bytes[2].es,
                          [f'Volume: {volume}', 'Volume', 'Vol'])

                balance = self.map_left_right(
                    self.data_bytes[3].b, 0x10, negative_tag='L', positive_tag='R')
                self.putx('balance', self.data_bytes[3].ss, self.data_bytes[3].es,
                          [f'Balance: {balance}', 'Balance', 'Bal'])

                fade = self.map_left_right(
                    self.data_bytes[4].b, 0x10, negative_tag='F', positive_tag='R')
                self.putx('fade', self.data_bytes[4].ss, self.data_bytes[4].es,
                          [f'Fade: {fade}', 'Fade'])

                bass = self.map_left_right(self.data_bytes[5].b, 0x10)
                self.putx('bass', self.data_bytes[5].ss, self.data_bytes[5].es,
                          [f'Bass: {bass}', 'Bass'])

                treble = self.map_left_right(self.data_bytes[7].b, 0x10)
                self.putx('treble', self.data_bytes[7].ss, self.data_bytes[7].es,
                          [f'Treble: {treble}', 'Treble'])

                flags = AudioAmpFlags(self.data_bytes[12].b)
                self.putx('audio-flags', self.data_bytes[12].ss, self.data_bytes[12].es,
                          [f'Flags: {str(flags)}', 'Flags'])

            return True

        return False


    def decode(self, ss, es, data):
        '''Decode Python output data from low-level (iebus) decoder.'''

        (ptype, pdata) = data

        if ptype == 'NAK':
            # A NAK condition has been observed, bus is reset back to IDLE
            #
            self.reset()

        if self.state == 'IDLE' and ptype == 'HEADER':
            self.broadcast_bit = pdata
            self.state = 'MASTER ADDRESS'
        elif self.state == 'MASTER ADDRESS' and ptype == 'MASTER ADDRESS':
            (address, parity_bit) = pdata
            self.master_addr = address
            if HWAddresses.has_value(self.master_addr):
                self.putx('address', ss, es, [
                          HWAddresses(self.master_addr).name])

            self.state = 'SLAVE ADDRESS'

        elif self.state == 'SLAVE ADDRESS' and ptype == 'SLAVE ADDRESS':
            (address, parity_bit, ack_bit) = pdata
            self.slave_addr = address

            if HWAddresses.has_value(self.slave_addr):
                self.putx('address', ss, es, [
                          HWAddresses(self.slave_addr).name])

            self.state = 'CONTROL'

        elif self.state == 'CONTROL' and ptype == 'CONTROL':
            (control, parity_bit, ack_bit) = pdata
            self.control = control

            self.state = 'DATA LENGTH'
        elif self.state == 'DATA LENGTH' and ptype == 'DATA LENGTH':
            (data_length, parity_bit, ack_bit) = pdata

            self.data_length = data_length

            self.state = 'DATA'
        elif self.state == 'DATA' and ptype == 'DATA':

            # Ignore parity bit and ack bit for simplicity
            self.data_bytes = [DataByte(b=b, ss=ss, es=es)
                               for (b, parity_bit, ack_bit, ss, es) in pdata]

            #
            # Decode logical device IDs
            #
            if self.broadcast_bit == 1:
                # Unicast packets

                # Some packets do not seem to follow this format
                if len(self.data_bytes) >= 3:

                    # In unicast communications the meaning of the first
                    # data byte is unknown. Values seen so far are:
                    # - 0x00
                    # - 0xff
                    #
                    self.from_function = self.data_bytes[1].b
                    self.to_function = self.data_bytes[2].b

                    from_anno = ['From Function', 'From']
                    if FunctionIDs.has_value(self.from_function):
                        self.from_function = FunctionIDs(self.from_function)
                        from_anno.insert(
                            0, f'From Function: {self.from_function.name}')
                    self.putx(
                        'function', self.data_bytes[1].ss, self.data_bytes[1].es, from_anno)

                    to_anno = ['To Function', 'To']
                    if FunctionIDs.has_value(self.to_function):
                        self.to_function = FunctionIDs(self.to_function)
                        to_anno.insert(
                            0, f'To Function: {self.to_function.name}')
                    self.putx(
                        'function', self.data_bytes[2].ss, self.data_bytes[2].es, to_anno)

                    self.data_bytes = self.data_bytes[3:]

            elif self.broadcast_bit == 0:
                # Broadcast packets

                self.from_function = self.data_bytes[0].b
                self.to_function = self.data_bytes[1].b

                from_anno = ['From Function', 'From']
                if FunctionIDs.has_value(self.from_function):
                    self.from_function = FunctionIDs(self.from_function)
                    from_anno.insert(
                        0, f'From Function: {self.from_function.name}')
                self.putx(
                    'function', self.data_bytes[0].ss, self.data_bytes[0].es, from_anno)

                to_anno = ['To Function', 'To']
                if FunctionIDs.has_value(self.to_function):
                    self.to_function = FunctionIDs(self.to_function)
                    to_anno.insert(0, f'To Function: {self.to_function.name}')
                self.putx(
                    'function', self.data_bytes[1].ss, self.data_bytes[1].es, to_anno)

                self.data_bytes = self.data_bytes[2:]

            else:
                raise RuntimeError(
                    f'Unexpected broadcast bit value {self.broadcast_bit}')

            if (self.from_function is not None) and (self.to_function is not None) and \
                (len(self.data_bytes) > 0):
                # Dispatch to device and function ID handling
                # This logic allows for prioritised matching
                fn = filter(lambda x: x is not None, [
                    getattr(
                        self, f'pkt_from_{self.from_function:02x}_to_{self.to_function:02x}', None),
                    getattr(self, f'pkt_to_{self.to_function:02x}', None),
                    getattr(self, f'pkt_from_{self.from_function:02x}', None),
                    getattr(self, f'pkt_{self.to_function:02x}', None),
                    getattr(self, f'pkt_{self.from_function:02x}', None),
                    #    getattr(self, f'pkt_default', None)
                ])

                for f in fn:
                    if f() is True:
                        break

            #
            # Prepare for next frame
            self.reset()

        else:
            #
            # Invalid state transition
            self.reset()
