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

import sigrokdecode as srd

from common.srdhelper import SrdIntEnum, bitpack_lsb
from .lists import (
    POINTER_BYTE_MAP,
    REGISTER_DESCRIPTOR_MAP,
    Field,
    Register,
)
from typing import List


(OPERATION_WRITE, OPERATION_READ) = range(2)
Ann = SrdIntEnum.from_str("Ann", "REGISTER FIELD POINTER_BYTE SLAVE_ADDR DATA_BYTE WARNING")


class Decoder(srd.Decoder):
    api_version = 3
    id = "ad5593r"
    name = "AD5593R"
    longname = "Analog Devices AAD5593"
    desc = "Analog Devices AD5593R 12-bit configurable ADC/DAC."
    license = "gplv3+"
    inputs = ["i2c"]
    outputs = []
    tags = ["IC", "Analog/digital"]
    options = ({"id": "Vref", "desc": "Reference voltage (V)", "default": 2.5},)
    annotations = (
        ("register", "Register"),
        ("field", "Field"),
        ("ptr_byte", "Pointer Byte"),
        ("slave_addr", "Slave Address"),
        ("data_byte", "Data Byte"),
        ("warning", "Warning"),
    )
    annotation_rows = (
        ("packet", "Packets", (Ann.POINTER_BYTE, Ann.SLAVE_ADDR, Ann.WARNING, Ann.DATA_BYTE)),
        ("registers", "Registers", (Ann.REGISTER,)),
        ("fields", "Fields", (Ann.FIELD,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "IDLE"
        # Delimiter of 8b I2C block
        self.ss = -1
        self.es = -1
        # I2C transaction over multiple 8b blocks
        self.ss_block = -1
        self.es_block = -1
        # Internal buffer
        self.bits = []
        self.IO_operation_type = -1
        # Databyte format which is determined by the pointer byte
        self.databyte_register = ""

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putg(self, ss, es, ann_idx, data):
        # Annotates a bit field of an I²C packet
        self.put(ss, es, self.out_ann, [ann_idx, data])

    def decode_field(self, bits, name, offset, width, parser=None):
        val, (ss, es) = self.bit_slice_to_int(bits, offset, width)
        formatted = parser(val) if parser else "{}".format(val)
        if formatted is not None and formatted != "":
            text = "{name}: {val}".format(name=name, val=formatted)
        else:
            text = "{name}".format(name=name)
        self.putg(ss, es, Ann.FIELD, [text])

    def handle_slave_addr(self, data):
        if data not in (0b0010000, 0b0010001):
            ann = "I²C slave is not compatible."
            self.putg(self.ss, self.es, Ann.WARNING, [ann])
        else:
            ann = ["I²C Slave address", "I²C Slave"]
            self.putg(self.ss, self.es, Ann.SLAVE_ADDR, ann)

    def handle_databyte_decode_state(self, register: Register, data: List[int]):
        # Handle state and determine how to parse the incomming data byte
        if register.name == "CONFIG_MODE_POINTER":
            # Only 1 match is expected in the list of fields. Then we extract the field from the list.
            CONFIG_MODE_BIT_FIELD = [field for field in register.fields if field.name == "CONFIG_MODE_BITS"][0]
            field_val, (_, _) = self.bit_slice_to_int(
                data, CONFIG_MODE_BIT_FIELD.start_bit, CONFIG_MODE_BIT_FIELD.width
            )
            self.databyte_register = (
                CONFIG_MODE_BIT_FIELD.parser(field_val) if CONFIG_MODE_BIT_FIELD.parser is not None else "UNKNOWN"
            )
            if self.databyte_register == "UNKNOWN":
                raise ValueError("Unknown CONFIG_MODE_BITS value")
        elif register.name == "DAC_WR_POINTER":
            self.databyte_register = "DAC_WR"
        elif register.name == "ADC_RD_POINTER":
            self.databyte_register = "ADC_RESULT"
        elif register.name == "DAC_RD_POINTER":
            self.databyte_register = "DAC_DATA_RD"
        elif register.name == "GPIO_RD_POINTER":
            if self.IO_operation_type == OPERATION_WRITE:
                self.databyte_register = "GPIO_INPUT"
            if self.IO_operation_type == OPERATION_READ:
                self.databyte_register = "GPIO_OUTPUT"
        elif register.name == "REG_RD_POINTER":
            # Only 1 match is expected in the list of fields. Then we extract the filed from the list.
            REG_SEL_RD_FIELD = [field for field in register.fields if field.name == "CONFIG_MODE_BITS"][0]
            field_val, (_, _) = self.bit_slice_to_int(data, REG_SEL_RD_FIELD.start_bit, REG_SEL_RD_FIELD.width)
            self.databyte_register = (
                REG_SEL_RD_FIELD.parser(field_val) if REG_SEL_RD_FIELD.parser is not None else "UNKNOWN"
            )
            if self.databyte_register == "UNKNOWN":
                raise ValueError("Unknown CONFIG_MODE_BITS value")

    def handle_pointer_byte(self, bits: List):
        opcode_field: Field = POINTER_BYTE_MAP.get_pointer_byte_register()
        opcode, (_, _) = self.bit_slice_to_int(bits, offset=opcode_field.start_bit, width=opcode_field.width)
        self.putg(self.ss, self.es, Ann.POINTER_BYTE, ["Pointer Byte", "Ptr Byte"])
        try:
            register: Register = POINTER_BYTE_MAP[opcode]
            self.putg(self.ss, self.es, Ann.REGISTER, [register.name])
            # Handle annotations
            for field in register.fields:
                self.decode_field(bits, field.name, field.start_bit, field.width, field.parser)
            self.handle_databyte_decode_state(register, bits)
        except Exception as e:
            return

    def handle_data_bytes(self, bits: List[int]) -> None:
        try:
            register: Register = REGISTER_DESCRIPTOR_MAP[self.databyte_register]
            self.putg(self.ss_block, self.es_block, Ann.REGISTER, [register.name])

            for field in register.fields:
                self.decode_field(bits, field.name, field.start_bit, field.width, field.parser)
        except Exception as e:
            return

    def store_bits(self, bits: List[int]):
        """
        Bits are stored in the decoder's data buffer in MSB order, index 0 corresponding to the MSB.
        This storage order facilitates extension with new 8-bit chunks.
        For annotation, we parse from LSB (Least Significant Bit) to MSB, which involves reversing the list again.
        """
        copy_bits = bits.copy()
        copy_bits.reverse()
        self.bits.extend(copy_bits)

    def bit_slice_to_int(self, bits, offset, width):
        bits = bits[offset:][:width]  # take a slice of the bits
        ss, es = bits[-1][1], bits[0][2]
        value = bitpack_lsb(bits, 0)
        return (
            value,
            (
                ss,
                es,
            ),
        )

    def process_IO_operation(self, bits):
        # Extracted from the address slave packet.
        LSB, _, _ = bits[0]
        return LSB

    def get_start_sample(self, bits, idx=0):
        bit, ss, es = bits[idx]
        return ss

    def get_end_sample(self, bits, idx=-1):
        bit, ss, es = bits[idx]
        return es

    def decode(self, ss, es, data):
        ptype, pdata = data

        # STOP resets the state machine
        if ptype == "STOP":
            self.state = "IDLE"
            self.bits = []
            return

        # State machine
        if self.state == "IDLE":
            if ptype not in ("START"):
                self.state = "IDLE"
                return
            self.state = "GET SLAVE ADDR"
        elif self.state == "GET SLAVE ADDR":
            if ptype == "BITS":
                self.ss = self.get_start_sample(pdata, idx=-1)
                self.es = self.get_end_sample(pdata, idx=1)
                self.IO_operation_type = self.process_IO_operation(pdata)
            if ptype in ("ADDRESS READ", "ADDRESS WRITE"):
                self.handle_slave_addr(pdata)
            if ptype == "ACK" and self.IO_operation_type == OPERATION_WRITE:
                self.state = "GET POINTER BYTE"
            if ptype == "ACK" and self.IO_operation_type == OPERATION_READ:
                self.state = "GET DATA HIGH"
        elif self.state == "GET POINTER BYTE":
            if ptype == "BITS":
                self.ss = self.get_start_sample(pdata, idx=-1)
                self.es = self.get_end_sample(pdata, idx=0)
                self.store_bits(pdata)
            if ptype in ("DATA WRITE", "DATA READ"):
                self.bits.reverse()
                self.handle_pointer_byte(self.bits)
                self.bits = []
            if ptype == "ACK":
                self.state = "GET DATA HIGH"
        elif self.state == "GET DATA HIGH":
            if ptype == "BITS":
                self.ss_block = self.get_start_sample(pdata, idx=-1)
                self.store_bits(pdata)
            if ptype == "ACK":
                self.state = "GET DATA LOW"
        elif self.state == "GET DATA LOW":
            if ptype == "BITS":
                self.es_block = self.get_end_sample(pdata, idx=0)
                self.putg(
                    self.ss_block,
                    self.es_block,
                    Ann.DATA_BYTE,
                    [
                        "Data Bytes",
                    ],
                )
                self.store_bits(pdata)
                self.bits.reverse()
                # Decode and clear buffer for repeated data byte packets
                self.handle_data_bytes(self.bits)
                self.bits = []
            if ptype in ("ACK", "NACK"):
                self.state = "GET DATA HIGH"
