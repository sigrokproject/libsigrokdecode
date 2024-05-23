##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 Analog Devices Inc.
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
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

from dataclasses import dataclass
from typing import Callable, List, Optional, Union

CONFIG_MODE_BITS_MAP = {
    0b0000: "NOP",
    0b0010: "ADC_SEQ",
    0b0011: "GEN_CTRL_REG",
    0b0100: "ADC_CONFIG",
    0b0101: "DAC_CONFIG",
    0b0110: "PULLDWN_CONFIG",
    0b0111: "LDAC_MODE",
    0b1000: "GPIO_CONFIG",
    0b1001: "GPIO_OUTPUT",
    0b1010: "GPIO_INPUT",
    0b1011: "PD_REF_CTRL",
    0b1100: "GPIO_OPENDRAIN_CONFIG",
    0b1101: "IO_TS_CONFIG",
    0b1111: "SW_RESET",
}

REG_SEL_RD_MAP = {
    0b0000: "NOP",
    0b0010: "ADC_SEQ",
    0b0011: "GEN_CTRL_REG",
    0b0100: "ADC_CONFIG",
    0b0101: "DAC_CONFIG",
    0b0110: "PULLDWN_CONFIG",
    0b0111: "LDAC mode",
    0b1000: "GPIO_CONFIG",
    0b1001: "GPIO_OUTPUT",
    0b1010: "GPIO_INPUT",
    0b1011: "PD_REF_CTRL",
    0b1100: "GPIO_OPENDRAIN_CONFIG",
    0b1101: "IO_TS_CONFIG",
}


# Utility functions: parse register fields
def DAC_chn(x: int) -> str:
    return f"DAC{x}"


def ADC_chn(x: int) -> str:
    return f"ADC{x}"


def decimal_to_hex(x: int) -> str:
    return f"0x{x:02X}"


def empty_str(x: int) -> str:
    return ""


def disabled_enabled(x: int) -> str:
    return ["Disabled", "Enabled"][x]


def vref_range(x: int) -> str:
    return "0V to {text}".format(text=["Vref", "2xVref"][x])


def bit_indices(num: int):
    """Given an number this function extracts the bit indices where the bits are set to 1 and returns them as a string.
    LSB has index 0.
    """
    res = []
    i = 0
    while num:
        if num & 1:
            res.append(str(i))
        num >>= 1
        i += 1
    if res:
        return ",".join(res)
    else:
        return "NONE"


@dataclass
class Field:
    start_bit: int
    width: int
    name: str
    parser: Optional[Callable[[int], str]]


@dataclass
class Register:
    opcode: Union[str, int]
    name: str
    fields: List[Field]


# Stores register objects which can be retrieved by the opcode as a key.
# The opcode can be extracted from the raw byte.
class RegisterDict(dict):
    def __setitem__(self, opcode, register):
        if not isinstance(register, Register):
            raise ValueError("Value must be an instance of Register")
        super().__setitem__(opcode, register)

    def __getitem__(self, opcode):
        register = super().__getitem__(opcode)
        return register

    def get_pointer_byte_register(self) -> Field:
        return Field(start_bit=4, width=4, name="Pointer byte bits", parser=None)


# 8b registers used to determine the type of operation to be performed by the AD5593R when subsequent data bytes arrive
POINTER_BYTE_MAP = RegisterDict()

POINTER_BYTE_MAP[0x00] = Register(
    opcode=0x00,
    name="CONFIG_MODE_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="CONFIG_MODE_BITS",
            parser=lambda x: CONFIG_MODE_BITS_MAP.get(x, "UNKNOWN"),
        ),
        Field(
            start_bit=4,
            width=4,
            name="CONFIG_MODE_SEL",
            parser=decimal_to_hex,
        ),
    ],
)

POINTER_BYTE_MAP[0x01] = Register(
    opcode=0x01,
    name="DAC_WR_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="DAC_CH_SEL_WR",
            parser=DAC_chn,
        ),
        Field(
            start_bit=4,
            width=4,
            name="DAC_WR_SEL",
            parser=decimal_to_hex,
        ),
    ],
)

POINTER_BYTE_MAP[0x04] = Register(
    opcode=0x04,
    name="ADC_RD_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="RESERVED",
            parser=empty_str,
        ),
        Field(
            start_bit=4,
            width=4,
            name="ADC_RD_SEL",
            parser=decimal_to_hex,
        ),
    ],
)

POINTER_BYTE_MAP[0x05] = Register(
    opcode=0x05,
    name="DAC_RD_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="DAC_CH_SEL_RD",
            parser=DAC_chn,
        ),
        Field(
            start_bit=4,
            width=4,
            name="DAC_RD_SEL",
            parser=decimal_to_hex,
        ),
    ],
)

POINTER_BYTE_MAP[0x06] = Register(
    opcode=0x06,
    name="GPIO_RD_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="RESERVED",
            parser=empty_str,
        ),
        Field(
            start_bit=4,
            width=4,
            name="GPIO_RD_SEL",
            parser=decimal_to_hex,
        ),
    ],
)

POINTER_BYTE_MAP[0x07] = Register(
    opcode=0x07,
    name="REG_RD_POINTER",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="DAC_CH_SEL_WR",  # Select control register for readback
            parser=lambda x: REG_SEL_RD_MAP.get(x, "UNKNOWN"),
        ),
        Field(
            start_bit=4,
            width=4,
            name="REG_RD_SEL",
            parser=decimal_to_hex,
        ),
    ],
)


REGISTER_DESCRIPTOR_MAP = RegisterDict()

REGISTER_DESCRIPTOR_MAP["NOOP"] = Register(
    opcode="NOOP",
    name="NOOP",
    fields=[
        Field(
            start_bit=0,
            width=11,
            name="No operation",
            parser=empty_str,
        ),
        Field(
            start_bit=11,
            width=5,
            name="RESERVED",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["ADC_SEQ"] = Register(
    opcode="ADC_SEQ",
    name="ADC_SEQ",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="ADC channels",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=1,
            name="Temperature Indicator",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=9,
            width=1,
            name="Repeat",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=10,
            width=6,
            name="RESERVED",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["GEN_CTRL_REG"] = Register(
    opcode="GEN_CTRL_REG",
    name="GEN_CTRL_REG",
    fields=[
        Field(
            start_bit=0,
            width=4,
            name="RESERVED",
            parser=empty_str,
        ),
        Field(
            start_bit=4,
            width=1,
            name="DAC_RANGE",
            parser=vref_range,
        ),
        Field(
            start_bit=5,
            width=1,
            name="ADC_RANGE",
            parser=vref_range,
        ),
        Field(
            start_bit=6,
            width=1,
            name="ALL_DAC",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=7,
            width=1,
            name="IO_LOCK",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=8,
            width=1,
            name="ADC_BUF_EN",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=9,
            width=1,
            name="ADC_BUF_PRECH",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=10,
            width=6,
            name="RESERVED",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["ADC_CONFIG"] = Register(
    opcode="ADC_CONFIG",
    name="ADC_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="ADC input pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["DAC_CONFIG"] = Register(
    opcode="DAC_CONFIG",
    name="DAC_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="DAC output pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["PULLDWN_CONFIG"] = Register(
    opcode="PULLDWN_CONFIG",
    name="PULLDWN_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="Weak-pulldown output pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["LDAC_MODE"] = Register(
    opcode="LDAC_MODE",
    name="LDAC_MODE",
    fields=[
        Field(
            start_bit=0,
            width=2,
            name="LDAC_MODE",
            parser=decimal_to_hex,
        ),
        Field(
            start_bit=2,
            width=14,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["GPIO_CONFIG"] = Register(
    opcode="GPIO_CONFIG",
    name="GPIO_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="GPIO output pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["GPIO_OUTPUT"] = Register(
    opcode="GPIO_OUTPUT",
    name="GPIO_OUTPUT",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="GPIO high pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["GPIO_INPUT"] = Register(
    opcode="GPIO_INPUT",
    name="GPIO_INPUT",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="GPIO input pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["PD_REF_CTRL"] = Register(
    opcode="PD_REF_CTRL",
    name="PD_REF_CTRL",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="DAC power-down pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=1,
            name="RESERVED",
            parser=empty_str,
        ),
        Field(
            start_bit=9,
            width=1,
            name="EN_REF",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=10,
            width=1,
            name="PD_ALL",
            parser=disabled_enabled,
        ),
        Field(
            start_bit=11,
            width=5,
            name="RESERVED",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["GPIO_OPENDRAIN_CONFIG"] = Register(
    opcode="GPIO_OPENDRAIN_CONFIG",
    name="GPIO_OPENDRAIN_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="GPIO open-drain pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["IO_TS_CONFIG"] = Register(
    opcode="IO_TS_CONFIG",
    name="IO_TS_CONFIG",
    fields=[
        Field(
            start_bit=0,
            width=8,
            name="Three-state output pins",
            parser=bit_indices,
        ),
        Field(
            start_bit=8,
            width=8,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["SW_RESET"] = Register(
    opcode="SW_RESET",
    name="SW_RESET",
    fields=[
        Field(
            start_bit=0,
            width=11,
            name="Reset command",
            parser=decimal_to_hex,
        ),
        Field(
            start_bit=11,
            width=5,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["DAC_WR"] = Register(
    opcode="DAC_WR",
    name="DAC_WR",
    fields=[
        Field(start_bit=0, width=12, name="DAC data", parser=None),
        Field(
            start_bit=12,
            width=4,
            name="RESERVERD",
            parser=empty_str,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["DAC_DATA_RD"] = Register(
    opcode="DAC_DATA_RD",
    name="DAC_DATA_RD",
    fields=[
        Field(start_bit=0, width=12, name="DAC_DATA", parser=None),
        Field(
            start_bit=12,
            width=3,
            name="DAC_ADDR",
            parser=DAC_chn,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["ADC_RESULT"] = Register(
    opcode="ADC_RESULT",
    name="ADC_RESULT",
    fields=[
        Field(start_bit=0, width=12, name="ADC_DATA", parser=None),
        Field(
            start_bit=12,
            width=3,
            name="ADC_ADDR",
            parser=ADC_chn,
        ),
    ],
)

REGISTER_DESCRIPTOR_MAP["TMP_SENSE_RESULT"] = Register(
    opcode="TMP_SENSE_RESULT",
    name="TMP_SENSE_RESULT",
    fields=[
        Field(start_bit=0, width=12, name="ADC_DATA", parser=None),
        Field(
            start_bit=12,
            width=4,
            name="TMPSENSE_ADDR",
            parser=decimal_to_hex,
        ),
    ],
)
