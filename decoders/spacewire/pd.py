##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2022 Theo Hussey <husseytg@gmail.com>
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

CHAR_LEN_CONTROL = 3
PACKET_MASK_CONTROL = 0b111
CHAR_LEN_DATA = 9

FCT = 0x1
EOP = 0x5
EEP = 0x3
ESC = 0x7

ANN_DATA = 0
ANN_PARITY = 1
ANN_DCF = 2
ANN_CTRL_CHAR = 3
ANN_DATA_CHR = 4
ANN_CODE = 5
ANN_TIME = 6
ANN_WARN = 7

class Decoder(srd.Decoder):
    api_version = 3
    id = 'spacewire'
    name = 'Spacewire'
    longname = 'Spacewire'
    desc = 'High speed data transfer protocol used for communication between spacecraft subsystems'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['spacewire']
    tags = ['Aerospace']
    channels = (
        {'id': 'data','name': 'Data', 'desc': 'Data line'},
        {'id': 'strobe','name': 'Strobe', 'desc': 'Strobe line'},
    )
    options = (
        
    )
    annotations = (
        ('D', 'Data'),
        ('P', 'Parity'),
        ('DCF', 'Data Control Flag'),
        ('ctrl-char', 'Control Character'),
        ('data-char', 'Data Character'),
        ('code', 'Control Code'),
        ('time', 'Control Code'),
        ('warning', 'Warning'),
    )
    annotation_rows = (
        ('bits', 'Bits', (0,1,2)),
        ('characters', 'Characters', (3,4)),
        ('codes', 'Control Codes', (5,6)),
        ('warnings', 'Warnings', (7,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "IDLE"

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self):
        last_len = 0
        last_samplenums = [0]*(CHAR_LEN_CONTROL + CHAR_LEN_DATA + 3)
        data_val = 0
        last_data_val = 0
        index = 0
        char_len = 3
        while True:
            data,strobe = self.wait([{0: 'e'}, {1: 'e'}])

            last_samplenums.insert(0,self.samplenum)
            if len(last_samplenums) > CHAR_LEN_CONTROL + CHAR_LEN_DATA + 3:
                last_samplenums.pop()
            
            if self.state == "IDLE":
                # Search for NULL code to sync to
                if (data_val & 0b1111111) == 0b1110100:
                    self.put(last_samplenums[7+1], last_samplenums[7], self.out_ann, [ANN_PARITY, [f"{(data_val >> 7) & 1}"]])
                    for i in reversed(range(0,7)):
                        self.put(last_samplenums[i+1], last_samplenums[i], self.out_ann, [ANN_DATA, [f"{(data_val >> i) & 1}"]])
                    self.put(last_samplenums[7+1], last_samplenums[0], self.out_ann, [ANN_CODE, ["NULL"]])
                    self.state = "SYNC"
                    last_len = 3
                    index = 0
            elif self.state == "SYNC":
                if index == 1 :
                    if data_val & 0b1:
                        char_len = CHAR_LEN_CONTROL
                    else:
                        char_len = CHAR_LEN_DATA
                    # data control bit
                    self.put(last_samplenums[1], last_samplenums[0], self.out_ann, [ANN_DCF, [f"{data_val & 1}"]])
                    #parity
                    parity = 0
                    # parity consists of the last packet aside from the parity and DCF bits
                    for i in range(0,last_len-1):
                        parity ^= (last_data_val >> i) & 1
                    # and also the current DCF
                    parity ^= data_val & 1
                    # invert it as parity is odd
                    parity ^= 0b1
                    self.put(last_samplenums[2], last_samplenums[1], self.out_ann, [ANN_PARITY, [f"{(data_val >> 1) & 1}"]])
                    if parity != (data_val >> 1) & 1:
                        self.put(last_samplenums[2], last_samplenums[1], self.out_ann, [ANN_WARN, ['PE', f"Parity Error"]])
                    index += 1
                elif index == char_len:
                    # Display data bit values
                    for i in range(0,char_len-1):
                        self.put(last_samplenums[i+1], last_samplenums[i], self.out_ann, [ANN_DATA, [f"{(data_val >> i) & 1}"]])
                    # Display control characters
                    if char_len == CHAR_LEN_CONTROL:
                        control_char = int('{:03b}'.format(data_val & PACKET_MASK_CONTROL)[::-1], 2)
                        if control_char == FCT:
                           self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_CTRL_CHAR, ["FCT"]]) 
                        elif control_char == ESC:
                           self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_CTRL_CHAR, ["ESC"]]) 
                        elif control_char == EEP:
                           self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_CTRL_CHAR, ["EEP"]]) 
                        elif control_char == EOP:
                           self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_CTRL_CHAR, ["EOP"]])
                        else:
                            self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_CTRL_CHAR, [f"{control_char} {data_val & PACKET_MASK_CONTROL}"]])
                        
                        # Detect Null control codes
                        if last_len == CHAR_LEN_CONTROL:
                            last_control_char = int('{:03b}'.format(last_data_val & PACKET_MASK_CONTROL)[::-1], 2)
                            if last_control_char == ESC:
                                if control_char == FCT:
                                    self.put(last_samplenums[CHAR_LEN_CONTROL*2+2], last_samplenums[0], self.out_ann, [ANN_CODE, ["NULL"]]) 
                    # Dislay Data characters
                    elif char_len == CHAR_LEN_DATA:
                        data_val_reversed = int('{:08b}'.format(data_val & 0xff)[::-1], 2)
                        self.put(last_samplenums[char_len+1], last_samplenums[0], self.out_ann, [ANN_DATA_CHR, [f"0x{data_val_reversed:02x}"]])
                        # Detect time codes
                        if last_len == CHAR_LEN_CONTROL:
                            last_control_char = int('{:03b}'.format(last_data_val & PACKET_MASK_CONTROL)[::-1], 2)
                            if last_control_char == ESC:
                                    self.put(last_samplenums[CHAR_LEN_CONTROL+char_len+2], last_samplenums[0], self.out_ann, [ANN_TIME, ["Time"]]) 

                    last_len = char_len
                    last_data_val = data_val
                    index = 0
                else:
                    index += 1

            # Shift in the data
            data_val <<= 1
            data_val |= data

