##
## This file could become part of the libsigrokdecode project.
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
## Version 1.3, 2026-01-17

import sigrokdecode as srd

class Ann:
    ADDR, MEMRD, MEMWR, WARN = range(4)
class Row:
    ADDRBUS, DATABUS, INSTRUCTIONS, OPERANDS, WARNINGS = range(5)
class Pin:
    AD0, AD7         = 0, 7       #
    A8, A15          = 8, 15      # 
    RD_WR, ENA, ALE  = 16, 17, 18 # 

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'tms7k'
    name = 'TMS7000'
    longname = 'Texas Instruments TMS7000'
    desc = 'Texas Instruments TMS7000 family, MC-mode.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Retro computing']
    channels = (
        {'id': 'rw', 'name': 'RW', 'desc': 'Read/notWrite'},           # 0
        {'id': 'en', 'name': 'EN', 'desc': 'Memory enable strobe'},    # 1
        {'id': 'ale', 'name': 'ALE', 'desc': 'Read/notWrite strobe'},  # 2
    ) + tuple({
        'id': 'ad%d' % i,
        'name': 'AD%d' % i,
        'desc': 'CPU data/addr. line %d' % i
        } for i in range(0, 8)    # Here the number is for formatting labels
    ) + tuple({
        'id': 'a%d' % i,
        'name': 'A%d' % i,
        'desc': 'CPU address line %d' % i
        } for i in range(8, 16)   # Here the number is for formatting labels
    )
    optional_channels = (
        {'id': 'clk', 'name': 'CLK', 'desc': 'Internal clockout'},
        {'id': 'rst', 'name': '/RESET', 'desc': 'RESET'},
        {'id': 'int1', 'name': '/INT1', 'desc': 'Interrupt 1'},
        {'id': 'int3', 'name': '/INT3', 'desc': 'Interrupt 3'},
        {'id': 'mc', 'name': 'MC', 'desc': 'Microcontroller Mode'}    
    ) + tuple({
        'id': 'ap%d' % i,
        'name': 'AP%d' % i,
        'desc': 'CPU A port %d' % i
        } for i in range(0, 8)
    ) + tuple({
        'id': 'bp%d' % i,
        'name': 'BP%d' % i,
        'desc': 'CPU B port %d' % i
        } for i in range(0, 4)
    )
    annotations = (
        ('address', 'Address'),        # 0
        ('memrd',   'Memory Read'),    # 1
        ('memwr',   'Memory Write'),   # 2
        ('data',    'Data Bus'),       # 3
        ('addrdata', 'Address:Data'),  # 4
    )
    annotation_rows = (
        ('addrbus', 'Addr.', (Ann.ADDR,)),
        ('databus', 'Data', (Ann.MEMRD, Ann.MEMWR)),
    )
    
    OFF_RW, OFF_EN, OFF_ALE = 0, 1, 2		# 0, 1, 2
    OFF_DATA_BOT, OFF_DATA_TOP = 3, 10  	# 3, 4, 5, 6, 7, 8, 9, 10
    OFF_ADDR_BOT, OFF_ADDR_TOP = 11, 18		# 11, 12, 13, 14, 15, 16, 17, 18

    def __init__(self):
        self.reset()

    def reset(self):
        self.addr = 0
        self.prev_addr_samplenum = 0
        self.data = 0
        self.prev_data_samplenum = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_bin = self.register(srd.OUTPUT_BINARY)

    def decode(self):
        while True:
            pins = self.wait([{self.OFF_ALE: 'f'}, {self.OFF_EN: 'r'}])
            if self.matched[0]:  # self.OFF_ALE: 'f'
                if self.OFF_EN == 0:
                    continue
                addrPins = pins[self.OFF_ADDR_BOT:self.OFF_ADDR_TOP + 1]
                dataPins = pins[self.OFF_DATA_BOT:self.OFF_DATA_TOP + 1]
                addrV = sum([bit << i for i, bit in enumerate(addrPins)])
                dataV = sum([bit << i for i, bit in enumerate(dataPins)])
                self.addr = addrV * 256 + dataV
                anntext = '{:04X}'.format(self.addr)
                self.put(self.prev_addr_samplenum, self.samplenum, self.out_ann, [Ann.ADDR, [anntext]])
                self.prev_addr_samplenum = self.samplenum
            if self.matched[1]:  # self.OFF_EN: 'r'
                dataPins = pins[self.OFF_DATA_BOT:self.OFF_DATA_TOP + 1]
                dataV = sum([bit << i for i, bit in enumerate(dataPins)])
                self.data = dataV
                anntext = '{:02X}'.format(self.data)
                if pins[self.OFF_RW] == 1:
                    self.put(self.prev_data_samplenum, self.samplenum, self.out_ann, [Ann.MEMRD, [anntext]])
                else:
                    self.put(self.prev_data_samplenum, self.samplenum, self.out_ann, [Ann.MEMWR, [anntext]])
                self.prev_data_samplenum = self.samplenum
