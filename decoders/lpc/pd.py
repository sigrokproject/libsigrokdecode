##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
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

# ...
fields = {
    # START field (indicates start or stop of a transaction)
    'START': {
        0b0000: 'Start of cycle for a target',
        0b0001: 'Reserved',
        0b0010: 'Grant for bus master 0',
        0b0011: 'Grant for bus master 1',
        0b0100: 'Reserved',
        0b0101: 'TPM',
        0b0110: 'Reserved',
        0b0111: 'Reserved',
        0b1000: 'Reserved',
        0b1001: 'Reserved',
        0b1010: 'Reserved',
        0b1011: 'Reserved',
        0b1100: 'Reserved',
        0b1101: 'Start of cycle for a Firmware Memory Read cycle',
        0b1110: 'Start of cycle for a Firmware Memory Write cycle',
        0b1111: 'Stop/abort (end of a cycle for a target)',
    },
    # Cycle type / direction field
    # Bit 0 (LAD[0]) is unused, should always be 0.
    # Neither host nor peripheral are allowed to drive 0b11x0.
    'CT_DR': {
        0b0000: 'I/O read',
        0b0010: 'I/O write',
        0b0100: 'Memory read',
        0b0110: 'Memory write',
        0b1000: 'DMA read',
        0b1010: 'DMA write',
        0b1100: 'Reserved / not allowed',
        0b1110: 'Reserved / not allowed',
    },
    # SIZE field (determines how many bytes are to be transferred)
    # Bits[3:2] are reserved, must be driven to 0b00.
    # Neither host nor peripheral are allowed to drive 0b0010.
    'SIZE': {
        0b0000: '8 bits (1 byte)',
        0b0001: '16 bits (2 bytes)',
        0b0010: 'Reserved / not allowed',
        0b0011: '32 bits (4 bytes)',
    },
    # CHANNEL field (bits[2:0] contain the DMA channel number)
    'CHANNEL': {
        0b0000: '0',
        0b0001: '1',
        0b0010: '2',
        0b0011: '3',
        0b0100: '4',
        0b0101: '5',
        0b0110: '6',
        0b0111: '7',
    },
    # SYNC field (used to add wait states)
    'SYNC': {
        0b0000: 'Ready',
        0b0001: 'Reserved',
        0b0010: 'Reserved',
        0b0011: 'Reserved',
        0b0100: 'Reserved',
        0b0101: 'Short wait',
        0b0110: 'Long wait',
        0b0111: 'Reserved',
        0b1000: 'Reserved',
        0b1001: 'Ready more (DMA only)',
        0b1010: 'Error',
        0b1011: 'Reserved',
        0b1100: 'Reserved',
        0b1101: 'Reserved',
        0b1110: 'Reserved',
        0b1111: 'Reserved',
    },
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'lpc'
    name = 'LPC'
    longname = 'Low Pin Count'
    desc = 'Protocol for low-bandwidth devices on PC mainboards.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['PC']
    options = (
        {'id': 'sample_point', 'desc': 'Sample Point', 'default': 'raising-edge',
            'values': ('raising-edge', 'falling-edge')},
    )
    channels = (
        {'id': 'lframe', 'name': 'LFRAME#', 'desc': 'Frame'},
        {'id': 'lclk',   'name': 'LCLK',    'desc': 'Clock'},
        {'id': 'lad0',   'name': 'LAD[0]',  'desc': 'Addr/control/data 0'},
        {'id': 'lad1',   'name': 'LAD[1]',  'desc': 'Addr/control/data 1'},
        {'id': 'lad2',   'name': 'LAD[2]',  'desc': 'Addr/control/data 2'},
        {'id': 'lad3',   'name': 'LAD[3]',  'desc': 'Addr/control/data 3'},
    )
    optional_channels = (
        {'id': 'lreset', 'name': 'LRESET#', 'desc': 'Reset'},
        {'id': 'ldrq',   'name': 'LDRQ#',   'desc': 'Encoded DMA / bus master request'},
        {'id': 'serirq', 'name': 'SERIRQ',  'desc': 'Serialized IRQ'},
        {'id': 'clkrun', 'name': 'CLKRUN#', 'desc': 'Clock run'},
        {'id': 'lpme',   'name': 'LPME#',   'desc': 'LPC power management event'},
        {'id': 'lpcpd',  'name': 'LPCPD#',  'desc': 'Power down'},
        {'id': 'lsmi',   'name': 'LSMI#',   'desc': 'System Management Interrupt'},
    )
    annotations = (
        ('warning', 'Warning'),
        ('start', 'Start'),
        ('cycle-type', 'Cycle-type/direction'),
        ('addr', 'Address'),
        ('tar1', 'Turn-around cycle 1'),
        ('sync', 'Sync'),
        ('data', 'Data'),
        ('tar2', 'Turn-around cycle 2'),
    )
    annotation_rows = (
        ('data-vals', 'Data', (1, 2, 3, 4, 5, 6, 7)),
        ('warnings', 'Warnings', (0,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'IDLE'
        self.lad = -1
        self.addr = 0
        self.cur_nibble = 0
        self.cycle_type = -1
        self.databyte = 0
        self.tarcount = 0
        self.synccount = 0
        self.oldpins = None
        self.ss_block = self.es_block = None
        self.prev_data = []
        self.first_annotation = True


    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def store_annotation(self, data):
        self.prev_data.append(data)

    def display_stored_annotation(self):
        for msg in self.prev_data:
            self.put(self.ss_block, self.es_block, self.out_ann, msg)
        self.prev_data = []

    def handle_get_start(self, lad, lad_bits, lframe):
        # LAD[3:0]: START field (1 clock cycle).

        # The last value of LAD[3:0] before LFRAME# gets de-asserted is what
        # the peripherals must use. However, the host can keep LFRAME# asserted
        # multiple clocks, and we output all START fields that occur, even
        # though the peripherals are supposed to ignore all but the last one.

        self.store_annotation([1, [fields['START'][lad], 'START', 'St', 'S']])
        self.ss_block = self.samplenum

        # Output a warning if LAD[3:0] changes while LFRAME# is low.
        # TODO
        if (self.lad != -1 and self.lad != lad):
            self.store_annotation([0, ['LAD[3:0] changed while LFRAME# was asserted']])

        if (lframe == 1):
            self.store_annotation([0, ['LFRAME# is asserted too early, frame might be malformed']])



        self.start_field = self.lad

        self.state = 'GET CT/DR'

    def handle_get_ct_dr(self, lad, lad_bits, lframe):

        self.es_block = self.samplenum
        self.display_stored_annotation()
        # LFRAME# is asserted (low). Wait until it gets de-asserted again
        # (the host is allowed to keep it asserted multiple clocks).
        if lframe != 1:
            return

        self.ss_block = self.samplenum
        self.cycle_type = fields['CT_DR'].get(lad, 'Reserved / unknown')

        # TODO: Warning/error on invalid cycle types.
        if 'Reserved' in self.cycle_type:
            self.store_annotation([0, ['Invalid cycle type (%s)' % lad_bits]])


        self.store_annotation([2, ['Cycle type: %s' % self.cycle_type]])


        self.state = 'GET ADDR'
        self.addr = 0
        self.cur_nibble = 0

    def handle_get_addr(self, lad, lad_bits):
        # LAD[3:0]: ADDR field (4/8/0 clock cycles).
        if self.cur_nibble == 0:
            self.es_block = self.samplenum
            self.display_stored_annotation()
            self.ss_block = self.samplenum

        # I/O cycles: 4 ADDR clocks. Memory cycles: 8 ADDR clocks.
        # DMA cycles: no ADDR clocks at all.
        if self.cycle_type in ('I/O read', 'I/O write'):
            addr_nibbles = 4 # Address is 16bits.
        elif self.cycle_type in ('Memory read', 'Memory write'):
            addr_nibbles = 8 # Address is 32bits.
        else:
            addr_nibbles = 4 # TODO: How to handle later on? add warning

        # Addresses are driven MSN-first.
        offset = ((addr_nibbles - 1) - self.cur_nibble) * 4
        self.addr |= (lad << offset)

        # Continue if we haven't seen all ADDR cycles, yet.
        if (self.cur_nibble < addr_nibbles - 1):
            self.cur_nibble += 1
            return


        s = 'Address: 0x%%0%dx' % addr_nibbles
        self.store_annotation([3, [s % self.addr]])



        if self.cycle_type in ('I/O write', 'Memory write'):
            self.state = 'WRITE DATA'
        elif self.cycle_type in ('Memory read', 'I/O read'):
            self.state = 'GET TAR'
        else:
            self.state = 'END_FRAME'

        self.tar_count = 0

    def handle_get_tar(self, lad, lad_bits):
        # LAD[3:0]: First TAR (turn-around) field (2 clock cycles).

        self.es_block = self.samplenum
        self.display_stored_annotation()
        self.ss_block = self.samplenum

        self.store_annotation([4, ['TAR1, cycle %d: %s' % (self.tarcount, lad_bits)]])


        # On the first TAR clock cycle LAD[3:0] is driven to 1111 by
        # either the host or peripheral. On the second clock cycle,
        # the host or peripheral tri-states LAD[3:0], but its value
        # should still be 1111, due to pull-ups on the LAD lines.
        if lad_bits != '1111':
            self.store_annotation([0, ['TAR1, cycle %d: %s (expected 1111)' % \
                           (self.tarcount, lad_bits)]])

        if (self.tarcount != 1):
            self.tarcount += 1
            return

        self.tarcount = 0
        self.state = 'GET SYNC'

    def handle_get_sync(self, lad, lad_bits):
        # LAD[3:0]: SYNC field (1-n clock cycles).
        self.es_block = self.samplenum
        self.display_stored_annotation()
        self.ss_block = self.samplenum

        self.sync_val = lad_bits

        self.store_annotation([5, ['SYNC: %s' %  self.sync_val]])

        # TODO
        if self.cycle_type in ('I/O write', 'Memory write'):
            self.state = 'GET TAR2'
        elif self.cycle_type in ('Memory read', 'I/O read'):
            self.state = 'GET DATA'
        else:
            self.state = 'END_FRAME'

        self.cycle_type = fields['SYNC'].get(lad, 'Reserved / unknown')
        # TODO: Warnings if reserved value are seen?
        if 'Reserved' in self.cycle_type:
            self.store_annotation([0, ['SYNC: %s (reserved value)' % self.sync_val]])

        self.cycle_count = 0

    def handle_get_data(self, lad, lad_bits):
        # LAD[3:0]: DATA field (2 clock cycles).
        if self.cycle_count == 0:
            self.es_block = self.samplenum
            self.display_stored_annotation()
            self.ss_block = self.samplenum

        # Data is driven LSN-first.
        if (self.cycle_count == 0):
            self.databyte = lad
        elif (self.cycle_count == 1):
            self.databyte |= (lad << 4)
        else:
            raise Exception('Invalid cycle_count: %d' % self.cycle_count)

        if (self.cycle_count != 1):
            self.cycle_count += 1
            return

        self.store_annotation([6, ['DATA: 0x%02x' % self.databyte]])

        self.cycle_count = 0
        self.state = 'GET TAR2'

    def handle_write_data(self, lad, lad_bits):

        # LAD[3:0]: DATA field (2 clock cycles).
        if self.cycle_count == 0:
            self.es_block = self.samplenum
            self.display_stored_annotation()
            self.ss_block = self.samplenum
        # Data is driven LSN-first.
        if (self.cycle_count == 0):
            self.databyte = lad
        elif (self.cycle_count == 1):
            self.databyte |= (lad << 4)
        else:
            raise Exception('Invalid cycle_count: %d' % self.cycle_count)

        if (self.cycle_count != 1):
            self.cycle_count += 1
            return

        self.store_annotation([6, ['DATA: 0x%02x' % self.databyte]])

        self.cycle_count = 0
        self.state = 'GET TAR'

    def handle_get_tar2(self, lad, lad_bits):
        # LAD[3:0]: Second TAR field (2 clock cycles).

        self.es_block = self.samplenum
        self.display_stored_annotation()
        self.ss_block = self.samplenum


        self.store_annotation([7, ['TAR2, cycle %d: %s' % (self.tarcount, lad_bits)]])

        # On the first TAR clock cycle LAD[3:0] is driven to 1111 by
        # either the host or peripheral. On the second clock cycle,
        # the host or peripheral tri-states LAD[3:0], but its value
        # should still be 1111, due to pull-ups on the LAD lines.
        if lad_bits != '1111':
            self.store_annotation([0, ['Warning: TAR2, cycle %d: %s (expected 1111)'
                           % (self.tarcount, lad_bits)]])

        if (self.tarcount != 1):
            self.tarcount += 1
            return

        self.tarcount = 0
        self.state = 'END_FRAME'

    def handle_end_frame(self):
        self.es_block = self.samplenum
        self.display_stored_annotation()
        self.state = 'IDLE'
    def decode(self):
        lclk_condition = {1: 'f'} if self.options['sample_point'] == 'falling-edge' else {1: 'r'}

        while True:
            if self.state == 'IDLE':
                # A valid LPC cycle starts with LFRAME# being asserted (low).
                self.wait({0: "l"})
            elif self.state == 'GET CT/DR':
                # lframe shall go back up before proceeding
                self.wait({0: "h"})

            pins = self.wait(lclk_condition)

            # Store current pin values for the next round.
            self.oldpins = pins

            # Get individual pin values into local variables.
            (lframe, lclk, lad0, lad1, lad2, lad3) = pins[:6]
            (lreset, ldrq, serirq, clkrun, lpme, lpcpd, lsmi) = pins[6:]



            # Store LAD[3:0] bit values (one nibble) in local variables.
            # Most (but not all) states need this.

            lad = (lad3 << 3) | (lad2 << 2) | (lad1 << 1) | lad0
            lad_bits = '{:04b}'.format(lad)

            # TODO: Only memory read/write is currently supported/tested.

            # State machine
            if self.state == 'IDLE':
                self.ss_block = self.samplenum
                self.state = 'GET START'
                self.lad = -1
                self.handle_get_start(lad, lad_bits, lframe)
            elif self.state == 'GET CT/DR':
                self.handle_get_ct_dr(lad, lad_bits, lframe)
            elif self.state == 'GET ADDR':
                self.handle_get_addr(lad, lad_bits)
            elif self.state == 'GET TAR':
                self.handle_get_tar(lad, lad_bits)
            elif self.state == 'GET SYNC':
                self.handle_get_sync(lad, lad_bits)
            elif self.state == 'GET DATA':
                self.handle_get_data(lad, lad_bits)
            elif self.state == 'WRITE DATA':
                self.handle_write_data(lad, lad_bits)
            elif self.state == 'GET TAR2':
                self.handle_get_tar2(lad, lad_bits)
            elif self.state == 'END_FRAME':
                self.handle_end_frame()

