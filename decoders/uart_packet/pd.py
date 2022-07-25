##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Sergey Spivak <sespivak@yandex.ru>
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

from collections import deque
import sigrokdecode as srd


class Ann:
    PACKET_RX, PACKET_RX_INVALID, \
    PACKET_TX, PACKET_TX_INVALID, \
        = range(4)


RX = 0
TX = 1
PACKET_LEN_MAX = 256


class Decoder(srd.Decoder):
    api_version = 3
    id = 'uart_packet'
    name = 'UART packet'
    longname = 'UART packet builder'
    desc = 'Combine UART data to packets'
    license = 'mit'
    inputs = ['uart']
    outputs = []
    tags = ['Embedded/industrial']
    options = (
        {'id': 'max_len', 'desc': 'Maximum packet length', 'default': PACKET_LEN_MAX, 'min': 1, 'max': PACKET_LEN_MAX},
        {'id': 'break_time', 'desc': 'Detect packet end by idle time (us)', 'default': 2000},
        {'id': 'format', 'desc': 'Data format', 'default': 'hex',
            'values': ('ascii', 'dec', 'hex', 'oct', 'bin')},
        {'id': 'print_sec', 'desc': 'Print start time (sec) in annotations', 'default': 'no', 'values': ('yes', 'no')},
    )
    annotations = (
        ('rx-packet', 'RX packet'),
        ('rx-packet-err', 'RX packet err'),
        ('tx-packet', 'TX packet'),
        ('tx-packet-err', 'TX packet err'),
    )
    annotation_rows = (
        ('packet_rx', 'RX', (Ann.PACKET_RX, Ann.PACKET_RX_INVALID)),
        ('packet_tx', 'TX', (Ann.PACKET_TX, Ann.PACKET_TX_INVALID)),
    )

    def __init__(self):
        self.out_py = None
        self.out_ann = None
        self.accum_bytes = (deque(maxlen=PACKET_LEN_MAX), deque(maxlen=PACKET_LEN_MAX))
        self.packet_size = [0, 0]
        self.packet_ss = [0, 0]
        self.packet_es = [0, 0]
        self.packet_valid = [True, True]
        self.max_len = 0
        self.print_sec = False
        self.format = None
        self.break_time = 0
        self.break_samples = 0
        self.samplerate = 0
        self.sampletime = 0
        self.reset(RX)
        self.reset(TX)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            self.sampletime = 1.0 / self.samplerate

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.max_len = self.options['max_len']
        self.break_time = self.options['break_time']

        format_name = self.options['format']
        if format_name == 'hex':
            self.format = '{:02X}'
        elif format_name == 'dec':
            self.format = '{:d}'
        elif format_name == 'bin':
            self.format = '{:08b}'
        elif format_name == 'oct':
            self.format = '{:03o}'
        else:
            self.format = None

        self.print_sec = self.options['print_sec'] == 'yes'
        self.accum_bytes = (deque(maxlen=self.max_len), deque(maxlen=self.max_len))
        self.break_samples = self.break_time * self.samplerate * 1e-6

    def reset(self, rxtx):
        self.accum_bytes[rxtx].clear()
        self.packet_size[rxtx] = 0
        self.packet_ss[rxtx] = 0
        self.packet_es[rxtx] = 0
        self.packet_valid[rxtx] = True

    def putg(self, ss, es, data):
        """Put a graphical annotation."""
        self.put(ss, es, self.out_ann, data)

    def data_array_to_str(self, data_array):
        if self.format:
            str_array = [self.format.format(data) for data in data_array]
            return ' '.join(str_array)
        else:
            str_array = [chr(data).__repr__()[1:-1] for data in data_array]
            return ''.join(str_array)

    def put_packet(self, rxtx):
        packet_str = self.data_array_to_str(self.accum_bytes[rxtx])
        if rxtx == RX:
            if self.packet_valid[RX]:
                ann = Ann.PACKET_RX
            else:
                ann = Ann.PACKET_RX_INVALID
        else:
            if self.packet_valid[TX]:
                ann = Ann.PACKET_TX
            else:
                ann = Ann.PACKET_TX_INVALID

        if self.print_sec and self.sampletime:
            packet_str = "{:8.3f} {:}{:}: ".format(
                self.packet_ss[rxtx] * self.sampletime,
                'TX' if rxtx == TX else 'RX',
                '' if self.packet_valid[rxtx] else ' err',
            ) + packet_str

        self.putg(self.packet_ss[rxtx], self.packet_es[rxtx], [ann, [packet_str, ]])
        self.reset(rxtx)

    def check_idle(self, idle_sample: int):
        if not self.break_samples:
            return

        if self.packet_size[RX]:
            if idle_sample > self.packet_es[RX] + self.break_samples:
                self.put_packet(RX)

        if self.packet_size[TX]:
            if idle_sample > self.packet_es[TX] + self.break_samples:
                self.put_packet(TX)

    def handle_frame(self, ss: int, es: int, rxtx: int, data: int, valid: bool):
        """UART data frame were seen"""

        self.check_idle(ss)
        if self.packet_size[rxtx] == 0:
            self.packet_ss[rxtx] = ss
        self.accum_bytes[rxtx].append(data)
        self.packet_size[rxtx] += 1
        self.packet_es[rxtx] = es
        if not valid:
            self.packet_valid[rxtx] = False

        if self.packet_size[rxtx] == self.max_len:
            self.put_packet(rxtx)

    def decode(self, ss, es, data):
        ptype = data[0]
        if ptype == 'IDLE':
            self.check_idle(ss)
        elif ptype == 'FRAME':
            # Analyze FRAMES only
            rxtx = data[1]
            frame_data, frame_valid = data[2]
            self.handle_frame(ss, es, rxtx, frame_data, frame_valid)
