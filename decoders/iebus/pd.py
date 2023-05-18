#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2023 Maciej Grela <enki@fsck.pl>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

'''
IEBus data timings help to understand the bits() method.

This drawning documents Mode 2
Drawing not to scale
Bit 0 dominates on the bus


               │                                       │
     byte n-1  │                               byte n  │ byte n+1
    ◄───────── │                            ◄───────── │ ─────────►
               │                                       │
               │  prep.     synchronization      data  │  prep.
               │ period         period          period │ period
               │                                       │
               │        │                     │        │        │
     ──────────┼────────┼─────────────────────┼────────┼────────┼───────────────────────────────►
               │        │                     │        │        │

                                                                                  ▲ ΔV
                                                       │                          │
               │        ┌─────────────────────┐        │        ┌──────────────   │ > 120 mV
               │        │                     │        │        │                 │
               │        │                     │        │        │                 │
               │        │                     │        │        │                 │ Bus voltage
Bit 1          │        │                     │        │        │                 │ (differential)
               │        │                     │        │        │                 │
               │        │                     │        │        │                 │
                        │                     │        │        │                 │
         ───────────────┘                     └────────┼────────┘                 │  < 20 mV
                                                       │
               │                              │        │
               │                              │        │
               │                              │        │
               │                              │        │
               │                              │        │                          ▲ ΔV
               │                                                                  │
               │        ┌──────────────────────────────┐        ┌──────────────   │ > 120 mV
               │        │                              │        │                 │
               │        │                     │        │        │                 │
               │        │                     │        │        │                 │ Bus voltage
Bit 0          │        │                     │        │        │                 │ (differential)
               │        │                     │        │        │                 │
               │        │                     │        │        │                 │
                        │                     │        │        │                 │
         ───────────────┘                     │        └────────┘                 │ < 20 mV
                                              │
               │        │                     │        │        │
    ───────────┼────────┼─────────────────────┼────────┼────────┼────────────────────────────► t
               │        │                     │        │        │
                  7 µs         20 µs            12 µs     7 µs


The IEBus decoder uses the following OUTPUT_PYTHON format:

Frame:
[<ptype>, <pdata>]

<ptype>:
- 'HEADER' (Start bit + Broadcast bit, <pdata> is the Broadcast bit value)
- 'MASTER ADDRESS' (<pdata> is (address, parity_bit) )
- 'SLAVE ADDRESS' (<pdata> is (address, parity_bit, ack_bit) )
- 'CONTROL' (<pdata> is (control, parity_bit, ack_bit) )
- 'DATA LENGTH' (<pdata> is (data_length, parity_bit, ack_bit) )
- 'DATA' (<pdata> contains frame data bytes and their ss/es numbers formatted
            as follows: [ (data1, parity_bit, ack_bit, ss, es),
                          (data2,  parity_bit, ack_bit, ss, es), ...
                        ] )
- 'NAK' (<pdata> is None)

Parity errors and NAK conditions are annotated but otherwise all data
is passed to the output unchanged.
Control bits are either decoded to one of the names from the Commands enum or
left as integer if no match is found.
'''

from functools import reduce
from enum import IntEnum
import sigrokdecode as srd  # pylint: disable=import-error


class Commands(IntEnum):
    '''
    Valid values for the control bits if IEBus frames.

    Reference: https://en.wikipedia.org/wiki/IEBus
    Reference: http://softservice.com.pl/corolla/avc/avclan.php
    '''


    @classmethod
    def has_value(cls, value: int):
        '''Searches for a particular integer value in the enum'''
        return value in iter(cls)


    READ_STATUS = 0x00  # Reads slave status
    READ_DATA_LOCK = 0x03  # Reads data and locks unit
    READ_LOCK_ADDR_LO = 0x04  # Reads lock address (lower 8 bits)
    READ_LOCK_ADDR_HI = 0x05  # Reads lock address (higher 4 bits)
    READ_STATUS_UNLOCK = 0x06  # Reads slave status and unlocks unit
    READ_DATA = 0x07  # Reads data
    WRITE_CMD_LOCK = 0x0a  # Writes command and locks unit
    WRITE_DATA_LOCK = 0x0b  # Writes data and locks unit
    WRITE_CMD = 0x0e  # Writes command
    WRITE_DATA = 0x0f  # Writes data


def first_true(iterable, default=None, pred=None):
    """Returns the first true value in the iterable.

    If no true value is found, returns *default*

    If *pred* is not None, returns the first item
    for which pred(item) is true.

    Reference: https://docs.python.org/3/library/itertools.html
    """
    # first_true([a,b,c], x) --> a or b or c or x
    # first_true([a,b], x, f) --> a if f(a) else b if f(b) else x
    return next(filter(pred, iterable), default)


class Decoder(srd.Decoder):
    '''IEBus decoder class for usage by libsigrokdecode.'''

    api_version = 3
    id = 'iebus'
    name = 'IEBus'
    longname = 'Inter-Equipment Bus'
    desc = 'Inter-Equipment Bus is an automotive communication bus used in Toyota and Honda vehicles'  # pylint: disable=line-too-long
    license = 'gplv3+'
    inputs = ['logic']
    outputs = ['iebus']
    tags = ['Automotive']
    channels = (
        {'id': 'bus', 'name': 'BUS', 'desc': 'Bus input'},
    )
    options = (
        {'id': 'mode', 'desc': 'Mode', 'values': (
            'Mode 2', ), 'default': 'Mode 2'},
    )
    annotations = (
        ('start-bit', 'Start bit'),         # 0
        ('bit', 'Bit'),                     # 1
        ('parity', 'Parity'),               # 2
        ('ack', 'Acknowledge'),             # 3

        ('broadcast', 'Broadcast flag'),    # 4
        ('maddr', 'Master address'),        # 5
        ('saddr', 'Slave address'),         # 6
        ('control', 'Control'),             # 7
        ('datalen', 'Data Length'),         # 8
        ('byte', 'Data Byte'),              # 9

        ('warning', 'Warning')
    )

    annotation_rows = (
        ('bits', 'Bits', (0, 1, 2, 3)),
        ('fields', 'Raw Fields', (4, 5, 6, 7, 8, 9)),
        ('warnings', 'Warnings', (10,))
    )


    def __init__(self):
        self.out_ann = self.out_python = None
        self.samplerate = None
        self.broadcast_bit = None
        self.bits_begin = self.bits_end = None


    def reset(self):
        '''Reset decoder state.'''


    def start(self):
        '''Start decoder.'''
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_python = self.register(srd.OUTPUT_PYTHON)


    def metadata(self, key, value):
        '''Handle metadata input from libsigrokdecode.'''
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value


    def reduce_bus(self, bus: list):
        '''Reduce a list of bit values to an integer (MSB bit order).'''
        return reduce(lambda a, b: (a << 1) | b, bus)


    def bits(self, n: int):
        '''
        Read n bits from the bus.
        Only Mode 2 is currently supported.

        
        '''
        self.bits_begin = None
        self.bits_end = None

        bits = []
        while n > 0:
            self.wait({0: 'r'})
            if self.bits_begin is None:
                self.bits_begin = self.samplenum
            bit_start = self.samplenum

            # In Mode 2 synchronization phase is 20µs, data phase is 13µs,
            # sample bit state 27µs after the synchronization edge
            # (approx. 20µs + 13µs / 2)

            pins = self.wait({'skip': int(27e-6 * self.samplerate)})
            bit = (pins[0] + 1) % 2

            # Assume full 33µs bit length after sync edge
            bit_end = bit_start + int(33e-6 * self.samplerate)

            bits.append(bit)
            self.put(bit_start, bit_end, self.out_ann,
                     [1, [str(bit)]])

            self.bits_end = bit_end

            n -= 1

        return bits


    def bit(self):
        '''Read one bit from the bus.'''
        return self.bits(1)[0]


    def value(self, num_bits: int):
        '''Read a value from the bus having num_bits bits (MSB first)'''
        v = self.reduce_bus(self.bits(num_bits))
        return (v, self.bits_begin, self.bits_end)


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

    def header(self):
        '''
        Read the header from the bus and add appropriate annotations.
        Returns the header bits.
        '''

        # Start bit
        #
        self.wait({0: 'r'})
        ss = self.samplenum
        self.wait({0: 'f'})
        es = self.samplenum

        if (es - ss) / self.samplerate < 100e-6:
            self.putx('warning', ss, es,
                        ['Startbit too short', 'Too short'])

            return (None, None, ss, es)

        self.putx('start-bit', ss, es, ['Start bit', 'Start', 'S'])

        # Broadcast bit
        #
        broadcast_bit = self.read_broadcast_bit()
        es = self.samplenum

        return (1, broadcast_bit, ss, es)


    def read_broadcast_bit(self):
        '''Read the broadcast bit from the bus and add appropriate annotations.'''
        broadcast_bit = self.bit()

        if broadcast_bit == 1:
            broadcast_anno = ['Unicast', 'Uni', 'U']
        elif broadcast_bit == 0:
            # Broadcast traffic has bit 0 here in order to
            # dominate on the bus.
            broadcast_anno = ['Broadcast', 'Bro', 'B']
        else:
            raise RuntimeError(f'Unexpected broadcast bit value {broadcast_bit}')

        self.putx('broadcast', self.bits_begin, self.bits_end, broadcast_anno)

        return broadcast_bit


    def ack_bit(self):
        '''Read the ACK/NAK bit from the bus and add appropriate annotations.'''
        ack_bit = self.bit()
        if self.broadcast_bit == 1:
            # Non-broadcast traffic
            if ack_bit == 0:
                # ACK needs to dominate on the bus
                self.putx('ack', self.bits_begin, self.bits_end, ['ACK', 'A'])
            elif ack_bit == 1:
                self.putx('ack', self.bits_begin, self.bits_end, ['NAK', 'N'])
            else:
                raise RuntimeError('Unexpected value {ack_bit} for the acknowledge bit')

        return ack_bit


    def parity_bit(self, value: int):
        '''Read the parity bit from the bus and add appropriate annotations.'''
        parity_bit = self.bit()
        self.putx('parity', self.bits_begin,
                  self.bits_end, ['Parity', 'Par', 'P'])
        expected_parity = bin(value).count('1') % 2
        if expected_parity != parity_bit:
            self.putx('warning', self.bits_begin,
                      self.bits_end, ['Parity error'])

        return parity_bit


    def handle_data_bytes(self, data_len: int):
        '''
        Read a specified amount of data bytes from the bus, add appropriate
        annotations, record sample counts for each byte and return a list.
        '''
        data_bytes = []

        while data_len > 0:
            (b, ss, es) = self.value(8)

            self.putx('byte', ss, es,
                        [f'Data: 0x{b:02x}', f'0x{b:02x}'])

            parity_bit = self.parity_bit(b)
            ack_bit = self.ack_bit()

            data_bytes.append((b, parity_bit, ack_bit, ss, es))

            data_len -= 1

            # We don't care about the value of these bits, just annotations
            if self.broadcast_bit == 1 and ack_bit == 1:
                # NAK condition, restart search for start bit
                break

        return data_bytes


    def decode(self):
        '''Decode samples, main function called by the libsigrokdecode framework'''
        while True:

            (start_bit, broadcast_bit, ss, es) = self.header()

            if start_bit is None:
                # Header was not valid, search for next one
                continue

            # Store broadcast bit for later checks of NAK conditions
            self.broadcast_bit = broadcast_bit

            self.put(ss, es, self.out_python, ['HEADER', self.broadcast_bit])

            # Master adddress
            #
            (master_addr, ss, es) = self.value(12)

            self.putx('maddr', ss, es, [ f'Master: 0x{master_addr:03x}', f'0x{master_addr:03x}' ])

            parity_bit = self.parity_bit(master_addr)
            self.put(ss, es, self.out_python, [
                'MASTER ADDRESS', (master_addr, parity_bit) ])

            # Slave adddress
            #
            (slave_addr, ss, es) = self.value(12)

            self.putx('saddr', ss, es, [ f'Slave: 0x{slave_addr:03x}', f'0x{slave_addr:03x}'])

            parity_bit = self.parity_bit(slave_addr)
            ack_bit = self.ack_bit()
            self.put(ss, es, self.out_python, [
                'SLAVE ADDRESS', (slave_addr, parity_bit, ack_bit)
            ])
            if self.broadcast_bit == 1 and ack_bit == 1:
                # NAK condition, restart search for start bit
                self.put(self.bits_begin, self.bits_end, self.out_python, ['NAK', None])
                continue

            # Control bits
            #
            (control, ss, es) = self.value(4)

            if Commands.has_value(control):
                control = Commands(control)
                self.putx('control', ss, es, [ f'Control: {control.name}', f'{control.name}' ])
            else:
                self.putx('control', ss, es, [ f'Control: 0x{control:01x}' ])

            parity_bit = self.parity_bit(control.value)
            ack_bit = self.ack_bit()
            self.put(ss, es, self.out_python, [ 'CONTROL', (control.name, parity_bit, ack_bit) ])

            if self.broadcast_bit == 1 and ack_bit == 1:
                # NAK condition, restart search for start bit
                self.put(self.bits_begin, self.bits_end, self.out_python, ['NAK', None])
                continue

            # Data length
            #
            (data_len, ss, es) = self.value(8)

            if data_len == 0:  # 0x00 is 256 bytes
                data_len = 256

            self.putx('datalen', ss, es, [ f'Data Length: {data_len}', f'{data_len}', 'Len' ])

            if data_len > 128:
                self.putx('warning', ss, es,
                          ['Message too long, mode 2 allows only for 128 bytes maximum',
                           'Message too long', 'Too long'])

            parity_bit = self.parity_bit(data_len)
            ack_bit = self.ack_bit()
            self.put(ss, es, self.out_python, [ 'DATA LENGTH', (data_len, parity_bit, ack_bit) ])

            if self.broadcast_bit == 1 and ack_bit == 1:
                # NAK condition, restart search for start bit
                self.put(self.bits_begin, self.bits_end, self.out_python, ['NAK', None])
                continue

            # Data bytes
            #
            ss = self.samplenum
            data_bytes = self.handle_data_bytes(data_len)
            es = self.samplenum

            self.put(ss, es, self.out_python, [ 'DATA', data_bytes ])
