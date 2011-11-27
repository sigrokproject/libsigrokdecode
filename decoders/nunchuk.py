##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

#
# Nintendo Wii Nunchuk decoder
#

# TODO: Description

# FIXME: This is just some example input for testing purposes...
example_packets = [
    # START condition.
    {'type': 'S',  'range': (10, 11), 'data': None, 'ann': ''},

    # Nunchuk init: Write 0x40,0x00 to slave address 0x54.
    {'type': 'AW', 'range': (12, 13), 'data': 0x54, 'ann': ''},
    {'type': 'DW', 'range': (14, 15), 'data': 0x40, 'ann': ''},
    {'type': 'AW', 'range': (16, 17), 'data': 0x54, 'ann': ''},
    {'type': 'DW', 'range': (18, 19), 'data': 0x00, 'ann': ''},

    # Get data: Read 6 bytes of data.
    {'type': 'DR', 'range': (20, 21), 'data': 0x11, 'ann': ''},
    {'type': 'DR', 'range': (22, 23), 'data': 0x22, 'ann': ''},
    {'type': 'DR', 'range': (24, 25), 'data': 0x33, 'ann': ''},
    {'type': 'DR', 'range': (26, 27), 'data': 0x44, 'ann': ''},
    {'type': 'DR', 'range': (28, 29), 'data': 0x55, 'ann': ''},
    {'type': 'DR', 'range': (30, 31), 'data': 0x66, 'ann': ''},

    # STOP condition.
    {'type': 'P',  'range': (32, 33), 'data': None, 'ann': ''},
]

def decode(l):
    print(l)
    sigrok.put(l)


def decode2(inbuf):
    """Nintendo Wii Nunchuk decoder"""

    # FIXME: Get the data in the correct format in the first place.
    inbuf = [ord(x) for x in inbuf]
    out = []
    o = {}

    # TODO: Pass in metadata.

    # States
    IDLE, START, NUNCHUK_SLAVE, INIT, INITIALIZED = range(5)
    state = IDLE # TODO: Can we assume a certain initial state?

    sx = sy = ax = ay = az = bz = bc = 0

    databytecount = 0

    # Loop over all I2C packets.
    for p in example_packets:
        if p['type'] == 'S': # TODO: Handle 'Sr' here, too?
            state = START

        elif p['type'] == 'Sr':
            pass # FIXME

        elif p['type'] == 'AR':
            # TODO: Error/Warning, not supported, I think.
            pass

        elif p['type'] == 'AW':
            # The Wii Nunchuk always has slave address 0x54.
            # TODO: Handle this stuff more correctly.
            if p['data'] == 0x54:
                pass # TODO
            else:
                pass # TODO: What to do here? Ignore? Error?

        elif p['type'] == 'DR' and state == INITIALIZED:
            if databytecount == 0:
                sx = p['data']
            elif databytecount == 1:
                sy = p['data']
            elif databytecount == 2:
                ax = p['data'] << 2
            elif databytecount == 3:
                ay = p['data'] << 2
            elif databytecount == 4:
                az = p['data'] << 2
            elif databytecount == 5:
                bz =  (p['data'] & (1 << 0)) >> 0
                bc =  (p['data'] & (1 << 1)) >> 1
                ax |= (p['data'] & (3 << 2)) >> 2
                ay |= (p['data'] & (3 << 4)) >> 4
                az |= (p['data'] & (3 << 6)) >> 6
                # del o
                o = {'type': 'D', 'range': (0, 0), 'data': []}
                o['data'] = [sx, sy, ax, ay, az, bz, bc]
                # sx = sy = ax = ay = az = bz = bc = 0
            else:
                pass # TODO

            if 0 <= databytecount <= 5:
                databytecount += 1

            # TODO: If 6 bytes read -> save and reset

        # TODO
        elif p['type'] == 'DR' and state != INITIALIZED:
            pass

        elif p['type'] == 'DW':
            if p['data'] == 0x40 and state == START:
                state = INIT
            elif p['data'] == 0x00 and state == INIT:
                o = {'type': 'I', 'range': (0, 0), 'data': []}
                o['data'] = [0x40, 0x00]
                out.append(o)
                state = INITIALIZED
            else:
                pass # TODO

        elif p['type'] == 'P':
            out.append(o)
            state = INITIALIZED
            databytecount = 0

    print out

    # FIXME
    return ''

register = {
    'id': 'nunchuk',
    'name': 'Nunchuk',
    'longname': 'Nintendo Wii Nunchuk decoder',
    'desc': 'Decodes the Nintendo Wii Nunchuk I2C-based protocol.',
    'longdesc': '...',
    'author': 'Uwe Hermann',
    'email': 'uwe@hermann-uwe.de',
    'license': 'gplv2+',
    'in': ['i2c'],
    'out': ['nunchuck'],
    'probes': [
        # TODO
    ],
    'options': {
        # TODO
    },
    # 'start': start,
    # 'report': report,
}

