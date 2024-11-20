##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Angus Gratton <gus@projectgus.com>
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
import re

'''
OUTPUT_PYTHON format:

Packet:
[<ptype>, <pdata>]

<ptype>:
 - 'AP_READ' (AP read)
 - 'DP_READ' (DP read)
 - 'AP_WRITE' (AP write)
 - 'DP_WRITE' (DP write)
 - 'LINE_RESET' (line reset sequence)

<pdata>:
  - tuple of address, ack state, data for the given sequence
'''

# Regexes for matching SWD data out of bitstring ('1' / '0' characters) format
RE_SWDSWITCH = re.compile(bin(0xE79E)[:1:-1] + '$')
RE_SWDREQ = re.compile(r'1(?P<apdp>.)(?P<rw>.)(?P<addr>..)(?P<parity>.)01$')
RE_IDLE = re.compile('0' * 50 + '$')

# is this RP2040 special?
RE_FROM_DORMANT = re.compile('1' + '01001001' + '11001111' + '10010000' + '01000110' + '10101001' + '10110100' + '10100001' +
                                   '01100001' + '10010111' + '11110101' + '10111011' + '11000111' + '01000101' + '01110000' + 
                                   '00111101' + '10011000' + '0000'     + '01011000' + '$')

# Sample edges
RISING = 1
FALLING = 0

ADDR_DP_SELECT = 0x8
ADDR_DP_CTRLSTAT = 0x4

BIT_SELECT_CTRLSEL = 1
BIT_SELECT_APBANKSEL = 0xf0
BIT_CTRLSTAT_ORUNDETECT = 1

ANNOTATIONS = ['bitr', 'bitw', 'turnaround', 'parity', 'reset', 'enable', 'read', 'write', 'ack', 'datar', 'dataw']

class Decoder(srd.Decoder):
    api_version = 3
    id = 'swd'
    name = 'SWD'
    longname = 'Serial Wire Debug'
    desc = 'Two-wire protocol for debug access to ARM CPUs.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['swd']
    tags = ['Debug/trace']
    channels = (
        {'id': 'swclk', 'name': 'SWCLK', 'desc': 'Master clock'},
        {'id': 'swdio', 'name': 'SWDIO', 'desc': 'Data input/output'},
    )
    options = (
        {'id': 'strict_start',
         'desc': 'Wait for a line reset before starting to decode',
         'default': 'no', 'values': ('yes', 'no')},
    )
    annotations = (
        ('bitr', 'BIT RCV'),
        ('bitw', 'BIT XMT'),
        ('turnaround', 'TURN AROUND'),
        ('parity', 'PARITY'),
        ('reset', 'RESET'),
        ('enable', 'ENABLE'),
        ('read', 'READ'),
        ('write', 'WRITE'),
        ('ack', 'ACK'),
        ('datar', 'DATA READ'),
        ('dataw', 'DATA WRITE'),
    )
    annotation_rows = (
        ('bits', 'Samples', (0,1,2)),
        ('fields', 'Fields', (3,4,5,6,7,8,9,10))
    )


    def __init__(self):
        self.reset()


    def reset(self):
        # SWD data/clock state
        self.state = 'UNKNOWN'
        self.sample_edge = RISING
        self.ack = None           # Ack state of the current phase
        self.ss_req = 0           # Start sample of current req
        self.turnaround = 0       # Number of turnaround edges to ignore before continuing
        self.turnround = 1        # this is the configured turnaround value (named form the doc)
        self.bits = ''            # Bits from SWDIO are accumulated here, matched against expected sequences
        self.samplenums = []      # Sample numbers that correspond to the samples in self.bits
        self.linereset_count = 0

        # SWD debug port state
        self.data = None
        self.addr = None
        self.rw = None            # Are we inside an SWD read or a write?
        self.apdp = None
        self.ctrlsel = 0          # 'ctrlsel' is bit 0 in the SELECT register.
        self.apbanksel = 0        # 'apbanksel' are bits [7:4] in the SELECT register
        self.orundetect = 0       # 'orundetect' is bit 0 in the CTRLSTAT register.
        

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        if self.options['strict_start'] == 'no':
            self.state = 'REQ' # No need to wait for a LINE RESET.


    def putx(self, ann, length, data):
        '''Output annotated data.'''
        ann = ANNOTATIONS.index(ann)
        try:
            ss = self.samplenums[-(2 * length)]
            ss_next_edge = self.samplenums[-(2 * length - 1)]
            ss -= (ss_next_edge - ss)
            if ss < self.samplenums[0]:
                ss = self.samplenums[0]
        except IndexError:
            ss = self.samplenums[0]
        if self.state == 'REQ':
            self.ss_req = ss
        es = self.samplenum
        self.put(ss, es, self.out_ann, [ann, [data]])


    def putp(self, ptype, pdata):
        self.put(self.ss_req, self.samplenum, self.out_python, [ptype, pdata])


    def put_python_data(self):
        '''Emit Python data item based on current SWD packet contents.'''
        try:
            ptype = {
                ('AP', 'R'): 'AP_READ',
                ('AP', 'W'): 'AP_WRITE',
                ('DP', 'R'): 'DP_READ',
                ('DP', 'W'): 'DP_WRITE',
            }[(self.apdp, self.rw)]
        except Exception:
            ptype = 'LINE_RESET'
        self.putp(ptype, (self.addr, self.data, self.ack))


    def decode(self):
        while True:
            # Wait for any clock edge.
            clk, dio = self.wait({0: 'e'})

            # Count rising edges with DIO held high,
            # as a line reset (50+ high edges) can happen from any state.
            if clk == RISING:
                if dio == 1:
                    self.linereset_count += 1
                else:
                    if self.linereset_count >= 50:
                        self.putx('reset', self.linereset_count, 'LINERESET')
                        self.putp('LINE_RESET', None)
                        self.reset_state()
                    self.linereset_count = 0

            if True:
                # Debugging
                if self.turnaround > 0:
                    if clk == RISING:
                        self.put(self.samplenum, self.samplenum, self.out_ann, [ANNOTATIONS.index('turnaround'), ['X']])
                elif clk == self.sample_edge:
                    if clk == RISING:
                        self.put(self.samplenum, self.samplenum, self.out_ann, [ANNOTATIONS.index('bitw'), [str(dio)]])
                    else:
                        self.put(self.samplenum, self.samplenum, self.out_ann, [ANNOTATIONS.index('bitr'), [str(dio)]])

            self.samplenums.append(self.samplenum)
            if self.turnaround > 0:
                if clk == RISING:
                    self.turnaround -= 1
                    self.samplenums = [self.samplenum]
            elif clk == self.sample_edge:
                self.bits += str(dio)
            else:
                {
                    'UNKNOWN': self.handle_unknown_edge,
                    'REQ': self.handle_req_edge,
                    'ACK': self.handle_ack_edge,
                    'DATAR': self.handle_data_edge,
                    'DATAW': self.handle_data_edge,
                    'DPARITY': self.handle_dparity_edge,
                }[self.state]()


    def next_state(self):
        '''Step to the next SWD state, reset internal counters accordingly.'''
        self.bits = ''
        self.samplenums = [self.samplenum]
        self.linereset_count = 0
        if self.state == 'UNKNOWN':
            self.state = 'REQ'
            self.sample_edge = RISING
            self.turnaround = 0
        elif self.state == 'REQ':
            self.state = 'ACK'
            self.sample_edge = FALLING
            self.turnaround = self.turnround
        elif self.state == 'ACK':
            if self.rw == 'R':
                self.state = 'DATAR'
                self.sample_edge = FALLING
                self.turnaround = 0
            else:
                self.state = 'DATAW'
                self.sample_edge = RISING
                self.turnaround = self.turnround
        elif self.state == 'DATAR':
            self.state = 'DPARITY'
        elif self.state == 'DATAW':
            self.state = 'DPARITY'
        elif self.state == 'DPARITY':
            self.put_python_data()
            self.state = 'REQ'
            self.sample_edge = RISING
            if self.rw == 'R':
                self.turnaround = self.turnround
            else:
                self.turnaround = 0


    def reset_state(self):
        '''Line reset (or equivalent), wait for a new pending SWD request.'''
        if self.state != 'REQ': # Emit a Python data item.
            self.put_python_data()
        # Clear state.
        self.bits = ''
        self.samplenums = []
        self.linereset_count = 0
        self.turnaround = 0
        self.sample_edge = RISING
        self.data = ''
        self.ack = None
        self.state = 'REQ'


    def handle_unknown_edge(self):
        '''
        Clock edge in the UNKNOWN state.
        In the unknown state, clock edges get ignored until we see a line
        reset (which is detected in the decode method, not here.)
        '''
        m = re.search(RE_FROM_DORMANT, self.bits)
        if m is not None:
            self.putx('reset', 148, 'FROM DORMANT')
            self.reset_state()
            return
        pass


    def handle_req_edge(self):
        '''Clock edge in the REQ state (waiting for SWD r/w request).'''
        # Check for a JTAG->SWD enable sequence.
        m = re.search(RE_SWDSWITCH, self.bits)
        if m is not None:
            self.putx('enable', 16, 'JTAG->SWD')
            self.reset_state()
            return

        # Or a valid SWD Request packet.
        m = re.search(RE_SWDREQ, self.bits)
        if m is not None:
            calc_parity = sum([int(x) for x in m.group('rw') + m.group('apdp') + m.group('addr')]) % 2
            parity = '' if str(calc_parity) == m.group('parity') else 'E'
            self.rw = 'R' if m.group('rw') == '1' else 'W'
            self.apdp = 'AP' if m.group('apdp') == '1' else 'DP'
            self.addr = int(m.group('addr')[::-1], 2) << 2
            self.putx('read' if self.rw == 'R' else 'write', 8, self.get_address_description())
            self.next_state()
            return


    def handle_ack_edge(self):
        '''Clock edge in the ACK state (waiting for complete ACK sequence).'''
        if len(self.bits) < 3:
            return
        if self.bits == '100':
            self.putx('ack', 3, 'OK')
            self.ack = 'OK'
            self.next_state()
        elif self.bits == '001':
            self.putx('ack', 3, 'FAULT')
            self.ack = 'FAULT'
            if self.orundetect == 1:
                self.next_state()
            else:
                self.reset_state()
            self.turnaround = self.turnround
        elif self.bits == '010':
            self.putx('ack', 3, 'WAIT')
            self.ack = 'WAIT'
            if self.orundetect == 1:
                self.next_state()
            else:
                self.reset_state()
            self.turnaround = self.turnround
        elif self.bits == '111':
            self.putx('ack', 3, 'NOREPLY')
            self.ack = 'NOREPLY'
            self.reset_state()
        else:
            self.putx('ack', 3, 'ERROR')
            self.ack = 'ERROR'
            self.reset_state()


    def handle_data_edge(self):
        '''Clock edge in the DATA state (waiting for 32 bits to clock past).'''
        if len(self.bits) < 32:
            return
        self.data = 0
        self.dparity = 0
        for x in range(32):
            if self.bits[x] == '1':
                self.data += (1 << x)
                self.dparity += 1
        self.dparity = self.dparity % 2

        self.putx('datar' if self.rw == 'R' else 'dataw', 32, '0x%08x' % self.data)
        self.next_state()


    def handle_dparity_edge(self):
        '''Clock edge in the DPARITY state (clocking in parity bit).'''
        if str(self.dparity) != self.bits:
            self.putx('parity', 1, str(self.dparity) + self.bits) # PARITY ERROR
        else:
            self.putx('parity', 1, 'P')                           # PARITY OK
            if self.rw == 'W':
                self.handle_completed_write()
        self.next_state()


    def handle_completed_write(self):
        '''
        Update internal state of the debug port based on a completed
        write operation.
        '''
        if self.apdp != 'DP':
            return
        elif self.addr == ADDR_DP_SELECT:
            self.ctrlsel = self.data & BIT_SELECT_CTRLSEL
            self.apbanksel = self.data & BIT_SELECT_APBANKSEL
        elif self.addr == ADDR_DP_CTRLSTAT:
            if self.ctrlsel == 0:
                self.orundetect = self.data & BIT_CTRLSTAT_ORUNDETECT
            else:
                self.turnround = ((self.data >> 8) & 0x03) + 1


    def get_address_description(self):
        '''
        Return a human-readable description of the currently selected address,
        for annotated results.
        '''
        if self.apdp == 'DP':
            if self.rw == 'R':
                # Tables 2-4 & 2-5 in ADIv5.2 spec ARM document IHI 0031C
                return {
                    0x0: 'DP IDCODE',
                    0x4: 'DP CTRL/STAT' if self.ctrlsel == 0 else 'DP R WCR',
                    0x8: 'DP RESEND',
                    0xC: 'DP RDBUFF'
                }[self.addr]
            elif self.rw == 'W':
                # Tables 2-4 & 2-5 in ADIv5.2 spec ARM document IHI 0031C
                return {
                    0x0: 'DP ABORT',
                    0x4: 'DP CTRL/STAT' if self.ctrlsel == 0 else 'DP W WCR',
                    0x8: 'DP SELECT',
                    0xC: 'DP RESERVED'
                }[self.addr]
        elif self.apdp == 'AP':
            addr = self.apbanksel + self.addr
            if addr == 0x00:
                s = "CSW"
            elif addr == 0x04:
                s = "TAR"
            elif addr == 0x0c:
                s = "DRW"
            elif addr == 0x10:
                s = "BD0"
            elif addr == 0x14:
                s = "BD1"
            elif addr == 0x18:
                s = "BD2"
            elif addr == 0x1c:
                s = "BD3"
            elif addr == 0xf4:
                s = "CFG"
            elif addr == 0xf8:
                s = "BASE"
            elif addr == 0xfc:
                s = "IDR"
            else:
                s = "%02x" % addr
            return 'AP %s' % s

        # Any legitimate operations shouldn't fall through to here, probably
        # a decoder bug.
        return '? %s%s%x' % (self.rw, self.apdp, self.addr)
