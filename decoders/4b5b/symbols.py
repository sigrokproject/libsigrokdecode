##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2021
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

# 4B5B Data Symbols
sym_data = {
    0b11110: 0x0,
    0b01001: 0x1,
    0b10100: 0x2,
    0b10101: 0x3,
    0b01010: 0x4,
    0b01011: 0x5,
    0b01110: 0x6,
    0b01111: 0x7,
    0b10010: 0x8,
    0b10011: 0x9,
    0b10110: 0xA,
    0b10111: 0xB,
    0b11010: 0xC,
    0b11011: 0xD,
    0b11100: 0xE,
    0b11101: 0xF
}

# 4B5B Control Symbols
sym_ctrl = {
    0b00100: ["HALT",      "H"],   # Halt
    0b11111: ["IDLE",      "I"],   # Idle
    0b11000: ["J",         "J"],   # Start 1
    0b10001: ["K",         "K"],   # Start 2
    0b00110: ["L",         "L"],   # Start 3
    0b00000: ["QUIET",     "Q"],   # Quiet (LOS)
    0b00111: ["RESET",     "R"],   # Reset
    0b11001: ["SET",       "S"],   # Set
    0b01101: ["TERMINATE", "T"]    # Terminate
}
