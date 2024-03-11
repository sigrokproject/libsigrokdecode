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
import warnings


def is_power_of_two(value):
    return value > 0 and (value & (value - 1) == 0)


def _reserved_zero(value, reading, field, **kwargs):
    '''A reserved field that is zero.
    On reading, warn on nonzero and drop to None.
    On writing, warn on nonzero and drop to None.'''
    if value != 0:
        if reading:
            warnings.warn('Reserved field {name!r}: should return 0; returned {value!r} instead'.format(name=field["name"], value=value))
        else:
            warnings.warn('Reserved field {name!r}: should not be written to; value {value!r} will be ignored'.format(name=field["name"], value=value))
    return None


def _check_write_single_1bit(value, field, **kwargs):
    if not is_power_of_two(value):
        warnings.warn('Only writes with a single bit set are allowed for field {name!r}'.format(name=field["name"]))
    return value


def _reg_read_only(value, reading, field, **kwargs):
    if not reading:
        warnings.warn('The entire register {name!r} is read-only; value {value!r} will be ignored'.format(name=field["name"], value=value))
        return None
    return value


_REG_TPM_ACCESS = [
    {'bits': 7, 'name': 'tpmRegValidSts', 'w': [_reserved_zero]},
    {'bits': 6, 'name': 'Reserved', 'rw': [_reserved_zero]},
    {'bits': 5, 'name': 'activeLocality',
        'r': [{0: None}],
        'w': [{1: '1 (relinquish)', 0: None}],
    },
    {'bits': 4, 'name': 'beenSeized',
        'r': [{0: None}],
        'w': [{1: '1 (clear)', 0: None}]
    },
    {'bits': 3, 'name': 'Seize',
        'r': [_reserved_zero],
        'w': [{1: '1 (seize)', 0: None}],
    },
    {'bits': 2, 'name': 'pendingRequest',
        'r': [{0: None}],
        'w': [_reserved_zero],
    },
    {'bits': 1, 'name': 'requestUse',
        'r': [{0: None}],
        'w': [{1: '1 (request)', 0: None}],
    },
    {'bits': 0, 'name': 'tpmEstablishment',
        'r': [{0: None}],
        'w': [_reserved_zero]
    },
]

_REG_TPM_STATUS = [
    {'bits': (31, 0), 'name': "TPM_STS_x",  # covering the entire register, to enforce this requirement
        'w': [_check_write_single_1bit, None],
        'r': [None],
    },
    {'bits': (31, 28), 'name': 'reserved', 'rw': [_reserved_zero]},
    {'bits': (27, 26), 'name': 'tpmFamily',
        'r': [{0: 'TPM1_2', 1: 'TPM2_0', None: '<undefined>'}],
        'w': [_reserved_zero],
    },
    {'bits': 25, 'name': 'resetEstablishmentBit',
        'r': [_reserved_zero],
        'w': [{0: None, 1: '1 (reset)'}],
    },
    {'bits': 24, 'name': 'commandCancel',
        'r': [_reserved_zero],
        'w': [{0: None, 1: '1 (cancel)'}],
    },
    {'bits': (23, 8), 'name': 'burstCount', 'w': [_reserved_zero]},
    {'bits': 7, 'name': 'stsValid', 'w': [_reserved_zero]},
    {'bits': 6, 'name': 'commandReady', 'rw': [{0: None}]},
    {'bits': 5, 'name': 'tpmGo',
        'r': [_reserved_zero],
        'w': [{0: None}],
    },
    {'bits': 4, 'name': 'dataAvail',
        'r': [{0: None}],
        'w': [_reserved_zero],
    },
    {'bits': 3, 'name': 'Expect',
        'r': [{0: None}],
        'w': [_reserved_zero],
    },
    {'bits': 2, 'name': 'selfTestDone', 'w': [_reserved_zero]},
    {'bits': 1, 'name': 'responseRetry',
        'r': [_reserved_zero],
        'w': [{1: '1 (resend)', 0: None}],
    },
    {'bits': 0, 'name': 'Reserved', 'rw': [_reserved_zero]},
]

_REG_TPM_I2C_INTERFACE_CAPABILITY = [
    {'bits': 31, 'name': 'Reserved', 'r': [_reserved_zero]},
    {'bits': 30, 'name': 'GT_SR', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 29, 'name': 'TPM_STS.burstCount', 'r': [{1: 'static', 0: 'dyn.'}]},
    {'bits': (27, 28), 'name': 'i2c_addr', 'r': [{3: 'mutable (prop.)', 1: 'mutable (TCG)', 0: 'fixed', None: "<undefined>"}]},
    {'bits': (25, 26), 'name': 'localities', 'r': [{2: '[0-255]', 1: '[0-4]', 0: '[0]', None: "<undefined>"}]},
    {'bits': 24, 'name': 'HS', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 23, 'name': 'Fm+', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 22, 'name': 'Fm', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 21, 'name': 'Sm', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 20, 'name': 'GT_RR', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 19, 'name': 'GT_RW', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 18, 'name': 'GT_WR', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': 17, 'name': 'GT_WW', 'r': [{1: 'y', 0: 'n'}]},
    {'bits': (9, 16), 'name': 'GT', 'r': []},
    {'bits': (7, 8), 'name': 'family', 'r': [{0: '1.2', 1: '2.0', None: '<undefined>'}]},
    {'bits': (4, 6), 'name': 'vers_i', 'r': [{0: 'TCG', None: '<undefined>'}]},
    {'bits': (0, 3), 'name': 'type_i', 'r': [{2: 'FIFO'}]},
]

# TCG TPM Vendor ID Registry
# Version 1.01 Revision 1.00 18th October 2017
_TPM_VENDOR_IDS = {
    0x1022: 'AMD',
    0x1114: 'Atmel',
    0x14E4: 'Broadcom',
    0x1590: 'HPE',
    0x1014: 'IBM',
    0x15D1: 'Infineon',
    0x8086: 'Intel',
    0x17AA: 'Lenovo',
    0x1414: 'Microsoft',
    0x100B: 'National Semi',
    0x1B4E: 'Nationz',
    0x1011: 'Qualcomm',
    0x1055: 'SMSC',
    0x104A: 'STMicroelectronics',
    0x144D: 'Samsung',
    0x19FA: 'Sinosun',
    0x104C: 'Texas Instruments',
    0x1050: 'Nuvoton Technology',
    0x232A: 'Fuzhou Rockchip',
    0x6666: 'Google',
    None: '<unknown>'
}

_REG_TPM_DID_VID = [
    {'bits': (31, 0), 'name': 'TPM_DID_VID_x', 'w': [_reg_read_only], 'r': [None]},
    {'bits': (31, 16), 'name': 'DID', 'w': [None]},
    {'bits': (15, 0), 'name': 'VID', 'r': [_TPM_VENDOR_IDS], 'w': [None]},
]

_REG_TPM_RID = [
    {'bits': (7, 0), 'name': 'TPM_RID_x', 'w': [_reg_read_only], 'r': [None]},
    {'bits': (7, 0), 'name': 'VID', 'w': [None]},
]

_I2C_TPM_REGISTERS = {
    0x00: ('TPM_LOC_SEL', 1),
    0x04: ('TPM_ACCESS', 1, _REG_TPM_ACCESS),
    0x08: ('TPM_INT_ENABLE', 4),
    0x10: ('TPM_INT_STATUS', 4),
    0x14: ('TPM_INT_CAPABILITY', 4),
    0x18: ('TPM_STS', 4, _REG_TPM_STATUS),
    0x20: ('TPM_HASH_END', 1),
    0x24: ('TPM_DATA_FIFO', 4),
    0x28: ('TPM_HASH_START', 1),
    0x30: ('TPM_I2C_INTERFACE_CAPABILITY', 4, _REG_TPM_I2C_INTERFACE_CAPABILITY),
    0x38: ('TPM_I2C_DEVICE_ADDRESS', 2),
    0x40: ('TPM_DATA_CSUM_ENABLE', 1),
    0x44: ('TPM_DATA_CSUM', 2),
    0x48: ('TPM_DID_VID', 4, _REG_TPM_DID_VID),
    0x4C: ('TPM_DID_RID', 1, _REG_TPM_RID),
}

_SPI_TPM_REGISTERS = {
    0xD40000: ('TPM_ACCESS_{locality}', 1, _REG_TPM_ACCESS),
    0xD40008: ('TPM_INT_ENABLE_{locality}', 4),
    0xD4000c: ('TPM_INT_VECTOR_{locality}', 1),
    0xD40010: ('TPM_INT_STATUS_{locality}', 4),
    0xD40014: ('TPM_INTF_CAPABILITY_{locality}', 5),
    0xD40018: ('TPM_STS_{locality}', 6, _REG_TPM_STATUS),
    0xD40024: ('TPM_DATA_FIFO_{locality}', 4),
    0xD40030: ('TPM_INTERFACE_ID_{locality}', 4),
    0xD40080: ('TPM_XDATA_FIFO_{locality}', 4),
    0xD40F00: ('TPM_DID_VID_{locality}', 4, _REG_TPM_DID_VID),
    0xD40F04: ('TPM_RID_{locality}', 1, _REG_TPM_RID),
    0xD40F90: ('vendor-defined', 0x70),
}


def _bits_mask(bits):
    ''':param Union[Tuple[int, int], int] bits: tuple of high and low bits (inclusive), or index of a single bit
    :return int: mask selecting those bits'''
    if isinstance(bits, int):  # single bit mask
        bits = (bits, bits)
    hi_bit, lo_bit = bits
    hi_mask = (1 << (hi_bit + 1)) - 1
    lo_mask = (1 << lo_bit) - 1
    return hi_mask ^ lo_mask


def _extract_bits(bits, data):
    mask = _bits_mask(bits)
    shift = bits if isinstance(bits, int) else bits[1]
    return (data & mask) >> shift


def decode_register(data, regspec, reading=True):
    data_bits = len(data) * 8
    data = int.from_bytes(data, 'little')
    parts = []
    for field in regspec:
        bits = field['bits']
        bit_lo = bits if isinstance(bits, int) else bits[1]
        if bit_lo >= data_bits:
            continue
        value = _extract_bits(bits, data)

        # specialization for reading/writing, so we can have separate checks/conversions
        if 'reading' in field and reading:
            field = dict(field)
            field.update(field['reading'])
        elif 'writing' in field and not reading:
            field = dict(field)
            field.update(field['writing'])

        pipeline = field.get('rw', [])
        if reading:
            pipeline.extend(field.get('r', []))
        else:
            pipeline.extend(field.get('w', []))

        # Pipeline - perform steps with the value, e.g. checking/transforming
        for step in pipeline:
            if isinstance(step, (type(None), str)):  # short form to drop a value
                value = None
            elif isinstance(step, dict):  # translation table
                value = step.get(value, step.get(None, value))
            else:  # conversion function
                try:
                    value = step(value=value, field=field, reading=reading)
                except TypeError:
                    print("\n\nTYPE ERROR\n\n", value, field, reading, step)

        if value is not None:
            name = field['name']
            format_str = field.get('format', '{name}={value}')
            format_str = {  # short forms
                'X': '{name}={value:X}',
                'B': '{name}={value:b}',
                'N': '{name}',
                'V': '{value}',
            }.get(format_str, format_str)
            part = format_str.format(name=name, value=value)
            parts.append(part)
    return '{' + ','.join(parts) + '}'


def xfer_annotations(xfer):
    if xfer.addr & 0xffff0000 == 0x00d40000:
        reg = xfer.addr & 0x0fff
        reg_name, reg_size, *reg_extra = _SPI_TPM_REGISTERS.get(xfer.addr, ('{xfer_addr:08X} (resvd)'.format(xfer_addr=xfer.addr), 0))
        locality = (xfer.addr & 0xf000) >> 12
        reg_name = reg_name.format(locality=locality)
    else:
        reg = xfer.addr & 0xff
        reg_name, reg_size, *reg_extra = _I2C_TPM_REGISTERS.get(xfer.addr, ('{xfer_addr:08X} (resvd)'.format(xfer_addr=xfer.addr), 0))
    annotations = [reg_name + '=' + binascii.hexlify(xfer.data).decode()]
    if len(reg_extra) > 0:
        annotations.insert(0, reg_name + '=' + decode_register(xfer.data, reg_extra[0], xfer.reading) + "(" + str(len(xfer.data)) + "b)")
    return annotations
