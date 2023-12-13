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

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>:
 - 'PACKET READ'  (ADDRESS READ followed by one or several
                   DATA bytes until STOP or START REPEAT)
 - 'PACKET WRITE' (ADDRESS WRITE followed by one or several
                   DATA bytes until STOP or START REPEAT)
 - 'TRANSACTION END' (End of transaction, due toi STOP bus condition)

<pdata> is the tuple with slave address byte and tuple with data bytes
if ptype is 'PACKET READ' or 'PACKET WRITE'.
Slave addresses do not include bit 0 (the READ/WRITE indication bit).
<pdata is None if ptype is 'TRANSACTION END'.
'''

class Ann:
    DATA = 0

class Decoder(srd.Decoder):
    api_version = 3
    id = 'i2c_packet'
    name = 'I²C packet'
    longname = 'I²C packet builder'
    desc = 'Concatenate I²C data to packets'
    license = 'mit'
    inputs = ['i2c']
    outputs = []
    tags = ['Embedded/industrial']
    options = (
        {'id': 'format', 'desc': 'Data format', 'default': 'hex',
            'values': ('ascii', 'dec', 'hex', 'oct', 'bin')},
    )
    annotations = (
        ('data', 'Data'),
    )
    annotation_rows = (
        ('packet', 'Packet', (Ann.DATA,)),
    )

    def __init__(self):
        self.out_py = None
        self.out_ann = None
        self.packet_data = deque()
        self.packet_str = ''
        self.packet_str_short = ''
        self.packet_ss = 0
        self.packet_part_ss = 0
        self.packet_es = 0
        self.read_sign = False
        self.address = 0
        self.fmt = None
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

        format_name = self.options['format']
        if format_name == 'hex':
            self.fmt = '{:02X}'
        elif format_name == 'dec':
            self.fmt = '{:d}'
        elif format_name == 'bin':
            self.fmt = '{:08b}'
        elif format_name == 'oct':
            self.fmt = '{:03o}'
        else:
            self.fmt = None
        self.packet_data = deque()

    def reset(self):
        self.packet_data.clear()
        self.packet_str = ''
        self.packet_str_short = ''
        self.packet_ss = 0
        self.packet_part_ss = 0
        self.packet_es = 0
        self.address = 0

    def putg(self, ss, es, data):
        """Put a graphical annotation."""
        self.put(ss, es, self.out_ann, data)

    def putp(self, ss, es, data):
        """Put a python annotation."""
        self.put(ss, es, self.out_py, data)

    def format_data_value(self, v):
        # Assume "is printable" for values from 32 to including 126,
        # below 32 is "control" and thus not printable, above 127 is
        # "not ASCII" in its strict sense, 127 (DEL) is not printable,
        # fall back to hex representation for non-printables.
        # (comment from same code of uart PD by Gerhard Sittig @gsigh)
        if self.fmt is None:
            if 32 <= v <= 126:
                return chr(v)
            return "[{:02X}]".format(v)
        else:
            return self.fmt.format(v)

    def data_array_to_str(self, data_array):
        if self.fmt:
            str_array = [self.fmt.format(value) for value in data_array]
            return ' '.join(str_array)
        else:
            str_array = [self.format_data_value(value) for value in data_array]
            return ''.join(str_array)

    def format_packet(self):
        packet_str = "0x{:02X} {:}: ".format(
            self.address,
            'RD' if self.read_sign else 'WR',
        ) + self.data_array_to_str(self.packet_data)

        packet_str_short = packet_str[2:]

        if self.packet_str:
            packet_str = self.packet_str + ' [SR] ' + packet_str
            packet_str_short = self.packet_str_short + ' [SR] ' + packet_str_short

        return packet_str, packet_str_short

    def handle_packet(self, start_repeat=False):
        if not len(self.packet_data):
            if not start_repeat:
                self.reset()
            return

        packet_str, packet_str_short = self.format_packet()

        ptype = 'PACKET READ' if self.read_sign else 'PACKET WRITE'
        self.putp(self.packet_part_ss, self.packet_es,
                  (ptype, (self.address, tuple(self.packet_data))))
        if not start_repeat:
            self.putp(self.packet_es, self.packet_es,
                      ('TRANSACTION END', None))

        if start_repeat:
            self.packet_data.clear()
            self.packet_str = packet_str
            self.packet_str_short = packet_str_short
        else:
            packet_ss = self.packet_ss
            self.putg(packet_ss, self.packet_es,
                      [Ann.DATA, [packet_str, packet_str_short]])
            self.reset()

    def decode(self, ss, es, data):
        ptype = data[0]
        if ptype.startswith('DATA'):
            self.packet_data.append(data[1])
            self.packet_es = es
        elif ptype.startswith('START'):
            # If there is still data in the reception buffer, put the packet annotation
            start_repeat = 'REPEAT' in ptype
            self.handle_packet(start_repeat=start_repeat)
            self.packet_part_ss = ss
            if not start_repeat:
                self.packet_ss = ss
        elif ptype.startswith('ADDRESS'):
            self.address = data[1]
            self.read_sign = 'READ' in ptype
            self.packet_es = es
        elif ptype.endswith('ACK'):
            self.packet_es = es
        elif ptype == 'STOP':
            self.packet_es = es
            self.handle_packet()
