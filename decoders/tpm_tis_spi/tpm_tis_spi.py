#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2020-2021 Tobias Peter <tobias.peter@infineon.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

import binascii

from collections import namedtuple


ANNOTATIONS = (
    ('rw-length', 'RW/Length'),
    ('address', 'Address'),
    ('wait-state', 'Wait State'),
    ('data', 'Data'),
    ('transaction', 'Transaction'),
    ('warning', 'Warning'),
)
ANN_RW_LENGTH = 0
ANN_ADDRESS = 1
ANN_WAIT_STATE = 2
ANN_DATA = 3
ANN_TRANSACTION = 4
ANN_WARNING = 5

Transaction = namedtuple('Transaction', ['reading', 'addr', 'data'])


def _finish_annotations(annotations):
    '''Depending on the amount of data read/written, sometimes the data-less formats (e.g. 'write 11 bytes') end up longer than the ones with data ('write 1234').
    In those cases, we remove them, because if we have the space to show the data, we don't want sigrok to pick the longer but less informative string.
    Assume :param annotations: is sorted by preference, and throw out any longer annotations following shorter ones.'''
    finished = [annotations[0]]
    for ann in annotations[1:]:
        if len(ann) < len(finished[-1]):
            finished.append(ann)
    return finished


def _warn_duplex(ss, es, ann, peer_byte):
    if peer_byte != 0:
        yield (ss, es, ann, [ANN_WARNING, ['unexpected duplex operation']])


def decoder(out_ann, out_py):
    '''A coroutine. Send in (ss, es, mosi_byte, miso_byte) tuples.
    Yields None when it wants data, and (ss, es, annotation, data) tuples when it has annotations.'''
    # Read/Write and Length Bit
    rwl_ss, rwl_es, rwl_mosi, rwl_miso = yield None
    yield from _warn_duplex(rwl_ss, rwl_es, out_ann, rwl_miso)
    reading = rwl_mosi & 0x80 == 0x80
    length = (rwl_mosi & 0x7f) + 1
    rw_char = 'R' if reading else 'W'
    yield (rwl_ss, rwl_es, out_ann, [ANN_RW_LENGTH, ['{rw_char} {length:d}'.format(rw_char=rw_char, length=length), '{rw_char}{length:d}'.format(rw_char=rw_char, length=length)]])

    # Address
    addr2_ss, addr2_es, addr2, addr2_miso = yield None
    addr1_ss, addr1_es, addr1, addr1_miso = yield None
    addr0_ss, addr0_es, addr0, addr0_miso = yield None
    yield from _warn_duplex(addr2_ss, addr2_es, out_ann, addr2_miso)
    yield from _warn_duplex(addr1_ss, addr1_es, out_ann, addr1_miso)
    yield from _warn_duplex(addr0_ss, addr0_es, out_ann, addr0_miso if addr0_miso != 1 else 0)  # miso high at end of addr0 is allowed
    wait_state = (addr0_miso == 0)

    addr_short = addr1 << 8 | addr0
    addr = addr2 << 16 | addr_short
    yield (addr2_ss, addr0_es, out_ann, [ANN_ADDRESS, _finish_annotations([
        '{addr:06X}'.format(addr=addr),
        '{addr:X}'.format(addr=addr),
        '{addr_short:04X}'.format(addr_short=addr_short),
        '{addr_short:X}'.format(addr_short=addr_short),
    ])])

    # Collect Data
    data = []
    data_ss, data_es = None, None
    for _ in range(length):
        ss, es, mosi_byte, miso_byte = yield None
        if data_ss is None:
            data_ss = ss
        data_es = es

        if reading:
            cross_byte, data_byte = mosi_byte, miso_byte
        else:
            data_byte, cross_byte = mosi_byte, miso_byte

        yield from _warn_duplex(ss, es, out_ann, cross_byte)
        data.append(data_byte)
    data = bytes(data)

    # Wait State
    if wait_state:
        yield (addr0_es, data_ss, out_ann, [ANN_WAIT_STATE, ['wait state', 'wait', 'w', '']])

    # Data annotation
    data_annotations = [
        binascii.hexlify(data).upper().decode(),
        '[{data_len} bytes]'.format(data_len=len(data))
    ]
    yield (data_ss, data_es, out_ann, [ANN_DATA, _finish_annotations(data_annotations)])

    # Transaction annotation
    transaction_op = '->' if reading else '<-'
    transaction_op_long = 'Read' if reading else 'Write'
    transaction_annotations = ['{addr:X} {transaction_op} '.format(addr=addr, transaction_op=transaction_op) + data_ann for data_ann in data_annotations] + [
        '{transaction_op_long} {addr:X}'.format(transaction_op_long=transaction_op_long, addr=addr),
        '{transaction_op_long[0]} {addr:X}'.format(transaction_op_long=transaction_op_long, addr=addr),
    ]
    yield (rwl_ss, data_es, out_ann, [ANN_TRANSACTION, _finish_annotations(transaction_annotations)])
    yield (rwl_ss, data_es, out_py, ['TRANSACTION', Transaction(reading, addr, data)])
