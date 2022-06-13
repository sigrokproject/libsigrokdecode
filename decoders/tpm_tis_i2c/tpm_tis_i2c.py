#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2022 Johannes Holland <johannes.holland@infineon.com>
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
    ('address', 'Address'),
    ('data_read', 'Data (Read)'),
    ('data_write', 'Data (Write)'),
    ('transaction', 'Transaction'),
    ('warning', 'Warning'),
)
ANN_ADDRESS = 0
ANN_DATA_READ = 1
ANN_DATA_WRITE = 2
ANN_TRANSACTION = 3
ANN_WARNING = 4

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


def decoder(out_ann, out_py):
    '''A coroutine. Send in (ss, es, ptype, pdata) tuples.
    Yields None when it wants data, and (ss, es, annotation, data) tuples when it has annotations.'''
    transition_ss = 0

    def get_next(ptype_exp=None, warn_ss=None, warn=True, raises_error=True):
        '''A coroutine. Send in a (ss, es, ptype, pdata) tuple.
        Yields None when it wants data, and a tuple (ss, es, annotation, data) when a warning must be shown.
        Returns (ss, es, ptype, pdata) on success or yields a warning annotation and raises ValueError() otherwise.'''
        if warn_ss is None:
            warn_ss = transition_ss
        if isinstance(ptype_exp, str):
            ptype_exp = [ptype_exp]

        ss, es, ptype, pdata = yield None

        error = ptype_exp is not None and ptype not in ptype_exp
        if error:
            warn_msg = 'got I2C {ptype} but expected one of {ptype_exp}'.format(ptype=ptype, ptype_exp=ptype_exp)
            if warn:
                yield (warn_ss, es, out_ann, [ANN_WARNING, [warn_msg]])
            if raises_error:
                raise ValueError(warn_msg)
        return ss, es, ptype, pdata

    # Transition start
    transition_ss, _, _, _ = yield from get_next("START", warn=False)
    addr_ss, _, _, _i2c_addr = yield from get_next("ADDRESS WRITE", warn=False)
    yield from get_next("ACK")

    # TIS register address
    data_ss, _, _, addr = yield from get_next("DATA WRITE")
    _, data_es, _, _ = yield from get_next("ACK")

    yield (addr_ss, data_es, out_ann, [ANN_ADDRESS, _finish_annotations([
        '{addr:02X}'.format(addr=addr),
    ])])

    # TIS read or write
    ss, es, ptype, pdata = yield from get_next(('START REPEAT', 'STOP', 'DATA WRITE'))
    if ptype in ('START REPEAT', 'STOP'):
        # TIS data read
        if ptype == 'STOP':
            yield from get_next("START")

        data_ss, _, _, _i2c_addr = yield from get_next("ADDRESS READ")
        yield from get_next("ACK")

        # multiple DATA READ until master NACKs
        data = []
        data_es = None
        while True:
            _, _, _, data_byte = yield from get_next("DATA READ")
            _, es, ptype, _ = yield from get_next(("ACK", "NACK"))

            data_es = es
            data.append(data_byte)

            if ptype == "NACK":
                break
        data = bytes(data)

        data_annotations = [
            '{data}'.format(data=binascii.hexlify(data).upper().decode()),
            '[{data_len} bytes]'.format(data_len=len(data)),
        ]
        yield (data_ss, data_es, out_ann, [ANN_DATA_READ, _finish_annotations(data_annotations)])

        yield from get_next("STOP")

        reading = True

    else:
        # TIS data write
        # multiple DATA WRITEs until STOP
        data = []
        data_ss, data_es = None, None
        while ptype == 'DATA WRITE':
            data_byte = pdata
            # ACK
            _, es, _, _ = yield from get_next("ACK")

            data_ss = data_ss or ss
            data_es = es
            data.append(data_byte)

            ss, _, ptype, pdata = yield from get_next(('DATA WRITE', 'STOP'))
        data = bytes(data)

        data_annotations = [
            '{data}'.format(data=binascii.hexlify(data).upper().decode()),
            '[{data_len} bytes]'.format(data_len=len(data)),
        ]
        yield (data_ss, data_es, out_ann, [ANN_DATA_WRITE, _finish_annotations(data_annotations)])

        reading = False

    # Transaction annotation
    transaction_op = '->' if reading else '<-'
    transaction_op_long = 'Read' if reading else 'Write'
    transaction_annotations = ['{addr:02X} {transaction_op} '.format(addr=addr, transaction_op=transaction_op) + data_ann for data_ann in data_annotations] + [
        '{transaction_op_long} {addr:02X}'.format(transaction_op_long=transaction_op_long, addr=addr),
        '{transaction_op_long[0]} {addr:02X}'.format(transaction_op_long=transaction_op_long, addr=addr),
    ]
    yield (addr_ss, data_es, out_ann, [ANN_TRANSACTION, _finish_annotations(transaction_annotations)])
    yield (addr_ss, data_es, out_py, ['TRANSACTION', Transaction(reading, addr, data)])
