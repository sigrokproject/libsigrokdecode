##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Marco Geisler <m-sigrok@mageis.de>
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

## ToDo:
## - are hex values supposed to be printed with '0x'? SPI decoder does not...
## - example data and screenshots
## - decode the status register


import sigrokdecode as srd
from .lists import *


class Decoder(srd.Decoder):
    api_version = 3
    id = 'cc1101'
    name = 'CC1101'
    longname = 'Texas Instruments CC1101'
    desc = 'Low-Power Sub-1GHz RF Transceiver Chip.'
    license = 'gplv2+'
    inputs = ['spi']
    outputs = ['cc1101']
    tags = ['IC', 'Wireless/RF']
    annotations = (
        ('strobe',        'Command strobe'),
        ('single_read',   'Single register read'),
        ('single_write',  'Single register write'),
        ('burst_read',    'Burst register read'),
        ('burst_write',   'Burst register write'),
        ('status',        'Status register'),
        ('warning',       'Warnings'),
    )
    ann_strobe        = 0
    ann_single_read   = 1
    ann_single_write  = 2
    ann_burst_read    = 3
    ann_burst_write   = 4
    ann_status_read   = 5
    ann_status        = 6
    ann_warn          = 7
    annotation_rows = (
        ('cmd', 'Commands', (ann_strobe, )),
         ('data', 'Data', (ann_single_read, ann_single_write, ann_burst_read, ann_burst_write, ann_status_read)),
        ('status', 'Status register', (ann_status,)),
        ('warnings', 'Warnings', (ann_warn,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.next()
        self.requirements_met = True
        self.cs_was_released = False

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def warn(self, pos, msg):
        '''Put a warning message 'msg' at 'pos'.'''
        self.put(pos[0], pos[1], self.out_ann, [self.ann_warn, [msg]])

    def putp(self, pos, ann, msg):
        '''Put an annotation message 'msg' at 'pos'.'''
        self.put(pos[0], pos[1], self.out_ann, [ann, [msg]])

    def next(self):
        '''Resets the decoder after a complete command was decoded.'''
        # 'True' for the first byte after CS went low.
        self.first = True

        # The current command, and the minimum and maximum number
        # of data bytes to follow.
        self.cmd = None
        self.min = 0
        self.max = 0

        # Used to collect the bytes after the command byte
        # (and the start/end sample number).
        self.mb = []
        self.mb_s = -1
        self.mb_e = -1

    def mosi_bytes(self):
        '''Returns the collected MOSI bytes of a multi byte command.'''
        return [b[0] for b in self.mb]

    def miso_bytes(self):
        '''Returns the collected MISO bytes of a multi byte command.'''
        return [b[1] for b in self.mb]

    def decode_command(self, pos, b):
        '''Decodes the command byte 'b' at position 'pos' and prepares
        the decoding of the following data bytes.'''
        c = self.parse_command(b)
        if c is None:
            self.warn(pos, 'unknown command')
            return

        self.cmd, self.dat, self.min, self.max = c

        if self.cmd in ('STROBE_CMD', ):
            self.putp(pos, self.ann_strobe, self.format_command())
        else:
            # Don't output anything now, the command is merged with
            # the data bytes following it.
            self.mb_s = pos[0]

    def format_command(self):
        '''Returns the label for the current command.'''
        if self.cmd == 'SINGLE_READ':
            reg = regs[self.dat] if self.dat in regs else 'unknown register'
            return 'Read'
        if self.cmd == 'BURST_READ':
            reg = regs[self.dat] if self.dat in regs else 'unknown register'
            return 'Burst read'
        if self.cmd == 'SINGLE_WRITE':
            reg = regs[self.dat] if self.dat in regs else 'unknown register'
            return 'Write'
        if self.cmd == 'BURST_WRITE':
            reg = regs[self.dat] if self.dat in regs else 'unknown register'
            return 'Burst write'
        if self.cmd == 'STATUS_READ':
            reg = regs[self.dat] if self.dat in regs else 'unknown register'
            return 'Status read'
        if self.cmd == 'STROBE_CMD':
            reg = strobes[self.dat] if self.dat in strobes else 'unknown strobe'
            return 'STROBE "{}"'.format(reg)
        else:
            return 'TODO Cmd {}'.format(self.cmd)

    def parse_command(self, b):
        '''Parses the command byte.

        Returns a tuple consisting of:
        - the name of the command
        - additional data needed to dissect the following bytes
        - minimum number of following bytes
        - maximum number of following bytes (None for infinite)
        '''

        addr = b & 0x3F
        if (addr < 0x30) or (addr == 0x3E) or (addr == 0x3F):
            if (b & 0xC0) == 0x00:
                return ('SINGLE_WRITE', addr, 1, 1)
            if (b & 0xC0) == 0x40:
                return ('BURST_WRITE', addr, 1, 99999)
            if (b & 0xC0) == 0x80:
                return ('SINGLE_READ', addr, 1, 1)
            if (b & 0xC0) == 0xC0:
                return ('BURST_READ', addr, 1, 99999)
            else:
                self.warn(pos, 'unknown address/command combination')
        else:
            if (b & 0x40) == 0x00:
                return ('STROBE_CMD', addr, 0, 0)
            if (b & 0xC0) == 0xC0:
                return ('STATUS_READ', addr, 1, 99999)
            else:
                self.warn(pos, 'unknown address/command combination')


    def decode_register(self, pos, ann, regid, data):
        '''Decodes a register.

        pos   -- start and end sample numbers of the register
        ann   -- is the annotation number that is used to output the register.
        regid -- may be either an integer used as a key for the 'regs'
                 dictionary, or a string directly containing a register name.'
        data  -- is the register content.
        '''

        if type(regid) == int:
            # Get the name of the register.
            if regid not in regs:
                self.warn(pos, 'unknown register')
                return
            name = '{} (0x{:02X})'.format(regs[regid], regid)
        else:
            name = regid

        if regid == 'STATUS' and ann == self.ann_status:
            label = 'Status'
        elif self.cmd in ('SINGLE_WRITE', 'SINGLE_READ', 'STATUS_READ', 'BURST_READ', 'BURST_WRITE'):
            label = '{}: {}'.format(self.format_command(), name)
        else:
            label = 'Reg ({}) {}'.format(self.cmd, name)

        self.decode_mb_data(pos, ann, data, label)

    def decode_mb_data(self, pos, ann, data, label):
        '''Decodes the data bytes 'data' of a multibyte command at position
        'pos'. The decoded data is prefixed with 'label'. '''

        def escape(b):
            return '{:02X}'.format(b)

        data = ' '.join([escape(b) for b in data])
        text = '{} = "0x{}"'.format(label, data)
        self.putp(pos, ann, text)

    def finish_command(self, pos):
        '''Decodes the remaining data bytes at position 'pos'.'''

        if self.cmd == 'SINGLE_WRITE':
            self.decode_register(pos, self.ann_single_write,
                                 self.dat, self.mosi_bytes())
        elif self.cmd == 'BURST_WRITE':
            self.decode_register(pos, self.ann_burst_write,
                                self.dat, self.mosi_bytes())
        elif self.cmd == 'SINGLE_READ':
            self.decode_register(pos, self.ann_single_read,
                                 self.dat, self.miso_bytes())
        elif self.cmd == 'BURST_READ':
            self.decode_register(pos, self.ann_burst_read,
                                self.dat, self.miso_bytes())
        elif self.cmd == 'STROBE_CMD':
            self.decode_register(pos, self.ann_strobe,
                                 self.dat, self.mosi_bytes())
        elif self.cmd == 'STATUS_READ':
            self.decode_register(pos, self.ann_status_read,
                                 self.dat, self.miso_bytes())
        else:
            self.warn(pos, 'unhandled command')


    def decode(self, ss, es, data):
        if not self.requirements_met:
            return

        ptype, data1, data2 = data

        if ptype == 'CS-CHANGE':
            if data1 is None:
                if data2 is None:
                    self.requirements_met = False
                    raise ChannelError('CS# pin required.')
                elif data2 == 1:
                    self.cs_was_released = True

            if data1 == 0 and data2 == 1:
                # Rising edge, the complete command is transmitted, process
                # the bytes that were send after the command byte.
                if self.cmd:
                    # Check if we got the minimum number of data bytes
                    # after the command byte.
                    if len(self.mb) < self.min:
                        self.warn((ss, ss), 'missing data bytes')
                    elif self.mb:
                        self.finish_command((self.mb_s, self.mb_e))

                self.next()
                self.cs_was_released = True
                
        elif ptype == 'DATA' and self.cs_was_released:
            mosi, miso = data1, data2
            pos = (ss, es)

            if miso is None or mosi is None:
                self.requirements_met = False
                raise ChannelError('Both MISO and MOSI pins required.')

            if self.first:
                self.first = False
                # First MOSI byte is always the command.
                self.decode_command(pos, mosi)
                # First MISO byte is always the status register.
                self.decode_register(pos, self.ann_status, 'STATUS', [miso])
            else:
                if not self.cmd or len(self.mb) >= self.max:
                    self.warn(pos, 'excess byte')
                else:
                    # Collect the bytes after the command byte.
                    if self.mb_s == -1:
                        self.mb_s = ss
                    self.mb_e = es
                    self.mb.append((mosi, miso))


