##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Jiahao Li <reg@ljh.me>
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

import sigrokdecode as srd

OPCODE_MASK = 0b11100000
REG_ADDR_MASK = 0b00011111

OPCODE_HANDLERS = {
    0b00000000: '_process_rcr',
    0b00100000: '_process_rbm',
    0b01000000: '_process_wcr',
    0b01100000: '_process_wbm',
    0b10000000: '_process_bfs',
    0b10100000: '_process_bfc',
    0b11100000: '_process_src',
}

ANN_RCR = 0
ANN_RBM = 1
ANN_WCR = 2
ANN_WBM = 3
ANN_BFS = 4
ANN_BFC = 5
ANN_SRC = 6

ANN_DATA = 7
ANN_REG_ADDR = 8

ANN_WARNING = 9

REG_ADDR_ECON1 = 0x1F
BIT_ECON1_BSEL0 = 0b00000001
BIT_ECON1_BSEL1 = 0b00000010

REGS = [
    [
        'ERDPTL',
        'ERDPTH',
        'EWRPTL',
        'EWRPTH',
        'ETXSTL',
        'ETXSTH',
        'ETXNDL',
        'ETXNDH',
        'ERXSTL',
        'ERXSTH',
        'ERXNDL',
        'ERXNDH',
        'ERXRDPTL',
        'ERXRDPTH',
        'ERXWRPTL',
        'ERXWRPTH',
        'EDMASTL',
        'EDMASTH',
        'EDMANDL',
        'EDMANDH',
        'EDMADSTL',
        'EDMADSTH',
        'EDMACSL',
        'EDMACSH',
        '—',
        '—',
        'Reserved',
        'EIE',
        'EIR',
        'ESTAT',
        'ECON2',
        'ECON1',
    ],
    [
        'EHT0',
        'EHT1',
        'EHT2',
        'EHT3',
        'EHT4',
        'EHT5',
        'EHT6',
        'EHT7',
        'EPMM0',
        'EPMM1',
        'EPMM2',
        'EPMM3',
        'EPMM4',
        'EPMM5',
        'EPMM6',
        'EPMM7',
        'EPMCSL',
        'EPMCSH',
        '—',
        '—',
        'EPMOL',
        'EPMOH',
        'Reserved',
        'Reserved',
        'ERXFCON',
        'EPKTCNT',
        'Reserved',
        'EIE',
        'EIR',
        'ESTAT',
        'ECON2',
        'ECON1',
    ],
    [
        'MACON1',
        'Reserved',
        'MACON3',
        'MACON4',
        'MABBIPG',
        '—',
        'MAIPGL',
        'MAIPGH',
        'MACLCON1',
        'MACLCON2',
        'MAMXFLL',
        'MAMXFLH',
        'Reserved',
        'Reserved',
        'Reserved',
        '—',
        'Reserved',
        'Reserved',
        'MICMD',
        '—',
        'MIREGADR',
        'Reserved',
        'MIWRL',
        'MIWRH',
        'MIRDL',
        'MIRDH',
        'Reserved',
        'EIE',
        'EIR',
        'ESTAT',
        'ECON2',
        'ECON1',
    ],
    [
        'MAADR5',
        'MAADR6',
        'MAADR3',
        'MAADR4',
        'MAADR1',
        'MAADR2',
        'EBSTSD',
        'EBSTCON',
        'EBSTCSL',
        'EBSTCSH',
        'MISTAT',
        '—',
        '—',
        '—',
        '—',
        '—',
        '—',
        '—',
        'EREVID',
        '—',
        '—',
        'ECOCON',
        'Reserved',
        'EFLOCON',
        'EPAUSL',
        'EPAUSH',
        'Reserved',
        'EIE',
        'EIR',
        'ESTAT',
        'ECON2',
        'ECON1',
    ],
]

class Decoder(srd.Decoder):
    api_version = 3
    id = 'enc28j60'
    name = 'ENC28J60'
    longname = 'Microchip ENC28J60'
    desc = 'Microchip ENC28J60 10Base-T Ethernet controller protocol.'
    license = 'mit'
    inputs = ['spi']
    outputs = ['enc28j60']
    tags = ['Embedded/industrial', 'Networking']
    annotations = (
        ('rcr', 'Read Control Register'),
        ('rbm', 'Read Buffer Memory'),
        ('wcr', 'Write Control Register'),
        ('wbm', 'Write Buffer Memory'),
        ('bfs', 'Bit Field Set'),
        ('bfc', 'Bit Field Clear'),
        ('src', 'System Reset Command'),
        ('data', 'Data'),
        ('reg-addr', 'Register Address'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('commands', 'Commands',
            (ANN_RCR, ANN_RBM, ANN_WCR, ANN_WBM, ANN_BFS, ANN_BFC, ANN_SRC)),
        ('fields', 'Fields', (ANN_DATA, ANN_REG_ADDR)),
        ('warnings', 'Warnings', (ANN_WARNING,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.mosi = []
        self.miso = []
        self.ranges = []
        self.command_start = None
        self.command_end = None
        self.active = False
        self.bsel0 = None
        self.bsel1 = None

    def start(self):
        self.ann = self.register(srd.OUTPUT_ANN)

    def _process_command(self):
        if len(self.mosi) == 0:
            self.active = False
            return

        header = self.mosi[0]
        opcode = header & OPCODE_MASK

        if opcode not in OPCODE_HANDLERS:
            self._put_command_warning("Unknown opcode.")
            self.active = False
            return

        getattr(self, OPCODE_HANDLERS[opcode])()

        self.active = False

    def _get_register_name(self, reg_addr):
        if (self.bsel0 is None) or (self.bsel1 is None):
            # We don't know the bank we're in yet.
            return None
        else:
            bank = (self.bsel1 << 1) + self.bsel0
            return REGS[bank][reg_addr]

    def _put_register_header(self):
        reg_addr = self.mosi[0] & REG_ADDR_MASK
        reg_name = self._get_register_name(reg_addr)

        if reg_name is None:
            # We don't know the bank we're in yet.
            self.put(self.command_start, self.ranges[1][0], self.ann, [
                     ANN_REG_ADDR,
                     [
                        'Reg Bank ? Addr 0x{0:02X}'.format(reg_addr),
                        '?:{0:02X}'.format(reg_addr),
                     ]])
            self.put(self.command_start, self.ranges[1][0], self.ann, [
                     ANN_WARNING,
                     [
                        'Warning: Register bank not known yet.',
                        'Warning',
                     ]])
        else:
            self.put(self.command_start, self.ranges[1][0], self.ann, [
                     ANN_REG_ADDR,
                     [
                        'Reg {0}'.format(reg_name),
                        '{0}'.format(reg_name),
                     ]])

            if (reg_name == '-') or (reg_name == 'Reserved'):
                self.put(self.command_start, self.ranges[1][0], self.ann, [
                         ANN_WARNING,
                         [
                            'Warning: Invalid register accessed.',
                            'Warning',
                         ]])

    def _put_data_byte(self, data, byte_index, binary=False):
        if byte_index == len(self.mosi) - 1:
            end_sample = self.command_end
        else:
            end_sample = self.ranges[byte_index + 1][0]

        if binary:
            self.put(self.ranges[byte_index][0], end_sample, self.ann, [
                     ANN_DATA,
                     [
                        'Data 0b{0:08b}'.format(data),
                        '{0:08b}'.format(data),
                     ]])
        else:
            self.put(self.ranges[byte_index][0], end_sample, self.ann, [
                     ANN_DATA,
                     [
                        'Data 0x{0:02X}'.format(data),
                        '{0:02X}'.format(data),
                     ]])

    def _put_command_warning(self, reason):
        self.put(self.command_start, self.command_end, self.ann, [
                 ANN_WARNING,
                 [
                    'Warning: {0}'.format(reason),
                    'Warning',
                 ]])

    def _process_rcr(self):
        self.put(self.command_start, self.command_end,
                 self.ann, [ANN_RCR, ['Read Control Register', 'RCR']])

        if (len(self.mosi) != 2) and (len(self.mosi) != 3):
            self._put_command_warning('Invalid command length.')
            return

        self._put_register_header()

        reg_name = self._get_register_name(self.mosi[0] & REG_ADDR_MASK)
        if reg_name is None:
            # We can't tell if we're accessing MAC/MII registers or not
            # Let's trust the user in this case.
            pass
        else:
            if (reg_name[0] == 'M') and (len(self.mosi) != 3):
                self._put_command_warning('Attempting to read a MAC/MII '
                    + 'register without using the dummy byte.')
                return

            if (reg_name[0] != 'M') and (len(self.mosi) != 2):
                self._put_command_warning('Attempting to read a non-MAC/MII '
                                          + 'register using the dummy byte.')
                return

        if len(self.mosi) == 2:
            self._put_data_byte(self.miso[1], 1)
        else:
            self.put(self.ranges[1][0], self.ranges[2][0], self.ann, [
                     ANN_DATA,
                     [
                        'Dummy Byte',
                        'Dummy',
                     ]])
            self._put_data_byte(self.miso[2], 2)

    def _process_rbm(self):
        if self.mosi[0] != 0b00111010:
            self._put_command_warning('Invalid header byte.')
            return

        self.put(self.command_start, self.command_end, self.ann, [
                 ANN_RBM,
                 [
                    'Read Buffer Memory: Length {0}'.format(
                        len(self.mosi) - 1),
                    'RBM',
                 ]])

        for i in range(1, len(self.miso)):
            self._put_data_byte(self.miso[i], i)

    def _process_wcr(self):
        self.put(self.command_start, self.command_end,
                 self.ann, [ANN_WCR, ['Write Control Register', 'WCR']])

        if len(self.mosi) != 2:
            self._put_command_warning('Invalid command length.')
            return

        self._put_register_header()
        self._put_data_byte(self.mosi[1], 1)

        if self.mosi[0] & REG_ADDR_MASK == REG_ADDR_ECON1:
            self.bsel0 = (self.mosi[1] & BIT_ECON1_BSEL0) >> 0
            self.bsel1 = (self.mosi[1] & BIT_ECON1_BSEL1) >> 1

    def _process_wbm(self):
        if self.mosi[0] != 0b01111010:
            self._put_command_warning('Invalid header byte.')
            return

        self.put(self.command_start, self.command_end, self.ann, [
                 ANN_WBM,
                 [
                    'Write Buffer Memory: Length {0}'.format(
                        len(self.mosi) - 1),
                    'WBM',
                 ]])

        for i in range(1, len(self.mosi)):
            self._put_data_byte(self.mosi[i], i)

    def _process_bfc(self):
        self.put(self.command_start, self.command_end,
                 self.ann, [ANN_BFC, ['Bit Field Clear', 'BFC']])

        if len(self.mosi) != 2:
            self._put_command_warning('Invalid command length.')
            return

        self._put_register_header()
        self._put_data_byte(self.mosi[1], 1, True)

        if self.mosi[0] & REG_ADDR_MASK == REG_ADDR_ECON1:
            if self.mosi[1] & BIT_ECON1_BSEL0:
                self.bsel0 = 0
            if self.mosi[1] & BIT_ECON1_BSEL1:
                self.bsel1 = 0

    def _process_bfs(self):
        self.put(self.command_start, self.command_end,
                 self.ann, [ANN_BFS, ['Bit Field Set', 'BFS']])

        if len(self.mosi) != 2:
            self._put_command_warning('Invalid command length.')
            return

        self._put_register_header()
        self._put_data_byte(self.mosi[1], 1, True)

        if self.mosi[0] & REG_ADDR_MASK == REG_ADDR_ECON1:
            if self.mosi[1] & BIT_ECON1_BSEL0:
                self.bsel0 = 1
            if self.mosi[1] & BIT_ECON1_BSEL1:
                self.bsel1 = 1

    def _process_src(self):
        self.put(self.command_start, self.command_end,
                 self.ann, [ANN_SRC, ['System Reset Command', 'SRC']])

        if len(self.mosi) != 1:
            self._put_command_warning('Invalid command length.')
            return

        self.bsel0 = 0
        self.bsel1 = 0

    def decode(self, ss, es, data):
        ptype, data1, data2 = data

        if ptype == 'CS-CHANGE':
            new_cs = data2

            if new_cs == 0:
                self.active = True
                self.command_start = ss
                self.mosi = []
                self.miso = []
                self.ranges = []
            elif new_cs == 1:
                if self.active:
                    self.command_end = es
                    self._process_command()
        elif ptype == 'DATA':
            mosi, miso = data1, data2

            self.mosi.append(mosi)
            self.miso.append(miso)
            self.ranges.append((ss, es))
