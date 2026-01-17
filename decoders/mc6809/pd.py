##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2026, fjkraan@electrickery.nl
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
## Version 1.2, 2026-01-17

import sigrokdecode as srd
from functools import reduce

class Ann:
    ADDR, MEMRD, MEMWR, INSTR, ROP, WOP, WARN = range(7)  # 0, 1, 2, 3, 4, 5, 6

class Row:
    ADDRBUS, DATABUS, INSTRUCTIONS, OPERANDS, WARNINGS = range(5)  # 0, 1, 2, 3, 4
    
class Cycle:
    NONE, MEMRD, MEMWR = range(3)
    
ann_data_cycle_map = {
    Cycle.MEMRD:  Ann.MEMRD,
    Cycle.MEMWR:  Ann.MEMWR,
}

class Pin:
    RW, E, Q = range(0, 3)      # 0, 1, 2
    D0, D7 = 3, 10              # 3, 4, 5, 6, 7, 8, 9, 10
    A0, A15 = 11, 27            # 11, 12, 13, 14, 15, 16, 17, 18,  19, 20, 21, 22, 23, 24, 25, 26

def reduce_bus(bus):
    if 0xFF in bus:
        return None # unassigned bus channels
    else:
        return reduce(lambda a, b: (a << 1) | b, reversed(bus))

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'mc6809'
    name = 'MC6809'
    longname = 'Motorola MC6809'
    desc = 'Decoder for the Motorola MC6809 microprocessor can be loaded by sigrok.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Retro computing']
    channels = (
        {'id': 'rw', 'name': 'R/W', 'desc': 'Read / not Write'},                # 0
        {'id': 'e', 'name': 'E', 'desc': 'Bus timing / enable clock'},          # 1
        {'id': 'q', 'name': 'Q', 'desc': 'Bus timing / quadrature clock'},      # 2
    ) + tuple({
        'id': 'd%d' % i,                                                        # 3-10
        'name': 'D%d' % i,
        'desc': 'CPU data line %d' % i
        } for i in range(0, 8)
    ) + tuple({
        'id': 'a%d' % i,                                                        # 11-26
        'name': 'A%d' % i,
        'desc': 'CPU address line %d' % i
        } for i in range(0, 16)
    )
    optional_channels = (
        {'id': 'ba', 'name': 'BA', 'desc': 'Bus enable'},
        {'id': 'bs', 'name': 'BS', 'desc': 'Bus status'},
    ) + (
        {'id': 'nmi', 'name': '/NMI', 'desc': 'not Non-Maskable Interrupt'},
        {'id': 'irq', 'name': '/IRQ', 'desc': 'not Interrupt'},
        {'id': 'firq', 'name': '/FIRQ', 'desc': 'not Fast Interrupt'},
        {'id': 'dmabrq', 'name': '/DMA/BREQ', 'desc': 'not Direct Memory Access / not Bus Request'},
        {'id': 'mrdy', 'name': 'MRDY', 'desc': 'Memory Ready'},
        {'id': 'rst', 'name': '/RESET', 'desc': 'not Reset'},
        {'id': 'halt', 'name': '/HALT', 'desc': 'not Halt'},
    )
    annotations = (
        ('addr', 'Memory address'),           #
        ('memrd', 'Byte read from memory'),   #
        ('memwr', 'Byte written to memory'),  #
        ('instr', '6809 CPU instruction'),    #
        ('rop', 'Value of input operand'),    #
        ('wop', 'Value of output operand'),   #
        ('warning', 'Warning'),               #
    )
    annotation_rows = (
        ('addrbus', 'Addr.', (Ann.ADDR,)),          # 0
        ('databus', 'Data', (Ann.MEMRD, Ann.MEMWR)),  # 1
        ('instructions', 'Instructions', (Ann.INSTR,)),   # 2
        ('operands', 'Operands', (Ann.ROP, Ann.WOP)),     # 3
        ('warnings', 'Warnings', (Ann.WARN,))             # 4
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.prev_cycle = Cycle.NONE
        self.op_state   = self.state_IDLE

    def start(self):
        self.out_ann    = self.register(srd.OUTPUT_ANN)
        self.bus_data   = None
        self.samplenum  = None
        self.addr_start = None
        self.data_start = None
        self.dasm_start = None
        self.pend_addr  = None
        self.pend_data  = None
        self.ann_data   = None
        self.ann_dasm   = None
        self.prev_cycle = Cycle.NONE
        self.op_state   = self.state_IDLE
        self.instr_len  = 0

    def decode(self):
        while True:
            pins = self.wait()
            cycle = Cycle.NONE
            if pins[Pin.Q] == 1 and pins[Pin.E] == 0: # default to asserted
                if pins[Pin.RW] == 0:
                    cycle = Cycle.MEMWR #
                else:
                    cycle = Cycle.MEMRD #

            if cycle != Cycle.NONE:
                self.bus_data = reduce_bus(pins[Pin.D0:Pin.D7+1])
            if cycle != self.prev_cycle:
                if self.prev_cycle == Cycle.NONE:
                    self.on_cycle_begin(reduce_bus(pins[Pin.A0:Pin.A15+1]))
                elif cycle == Cycle.NONE:
                    self.on_cycle_end()
                else:
                    self.on_cycle_trans()
            self.prev_cycle = cycle

    def state_IDLE(self):
        self.want_dis   = 0
        self.want_imm   = 0
        self.want_read  = 0
        self.want_write = 0
        self.want_wr_be = False
        self.op_repeat  = False
        self.arg_dis    = 0
        self.arg_imm    = 0
        self.arg_read   = 0
        self.arg_write  = 0
        self.arg_reg    = ''
        self.mnemonic   = ''
        self.instr_pend = False
        self.read_pend  = False
        self.write_pend = False
        self.dasm_start = self.samplenum
        self.op_prefix  = 0
        self.instr_len  = 0

    def on_cycle_begin(self, bus_addr):
        if self.pend_addr is not None:
            self.put_text(self.addr_start, Ann.ADDR,
                          '{:04X}'.format(self.pend_addr))
        self.addr_start = self.samplenum
        self.pend_addr  = bus_addr

    def on_cycle_end(self):
        self.instr_len += 1
        if self.ann_dasm is not None:
            self.put_disasm()
        if self.op_state == self.state_RESTART:
            self.op_state = self.state_IDLE()

        if self.ann_data is not None:
            self.put_text(self.data_start, self.ann_data,
                          '{:02X}'.format(self.pend_data))
        self.data_start = self.samplenum
        self.pend_data  = self.bus_data
        self.ann_data   = ann_data_cycle_map[self.prev_cycle]

    def on_cycle_trans(self):
        self.put_text(self.samplenum - 1, Ann.WARN,
                      'Illegal transition between control states')
        self.pend_addr = None
        self.ann_data  = None
        self.ann_dasm  = None

    def state_RESTART(self):
        return self.state_IDLE

    def put_text(self, ss, ann_idx, ann_text):
        self.put(ss, self.samplenum, self.out_ann, [ann_idx, [ann_text]])

    def put_disasm(self):
        text = formatter.format(self.mnemonic, r=self.arg_reg, d=self.arg_dis,
                                j=self.arg_dis+self.instr_len, i=self.arg_imm,
                                ro=self.arg_read, wo=self.arg_write)
        self.put_text(self.dasm_start, self.ann_dasm, text)
        self.ann_dasm   = None
        self.dasm_start = self.samplenum
