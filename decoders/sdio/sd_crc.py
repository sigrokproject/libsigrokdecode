##
## This file is part of the sigrok project.
##
## Copyright (C) 2019 XIAO Xufeng <xiaoxufeng@espressif.com>
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

def BIT(data, n):
    return 1 if data & (1<<n) != 0 else 0

def crc7(bin_array):
    init_value = 0
    data = init_value
    for bit in bin_array:
        di = bit ^ BIT(data, 6)
        data = (data & 0x07) | ((data & 0x38)<<1) | ((di^BIT(data,2))<<3)
        data = (data & 0x78) | ((data & 0x03)<<1) | di
    return data

def crc16(bin_array):
    init_value = 0
    data = init_value
    for bit in bin_array:
        di = bit ^ BIT(data, 15)
        data = (data & 0x0FFF) | ((data & 0x7000)<<1) | ((di^BIT(data,11))<<12)
        data = (data & 0xF01F) | ((data & 0x07E0)<<1) | ((di^BIT(data,4))<<5)
        data = (data & 0xFFE0) | ((data & 0x000F)<<1) | di
    return data


if __name__ == "__main__":
    #test CRC16
    if False:
        data = []
        for i in range (512*8):
            data.append(1)
        output = crc16(data)
        print(hex(output))

    #test CRC7
    if True:
        argv = sys.argv[1]
    #   data = [ (1 if argv[i] == '1' else 0) for i in range(len(argv)) ]
        
        data = []
        input_len = 40
        input_data = int(argv,16)
        print(input_data)
        for i in range(input_len):
            if (input_data >>(input_len-1))&1:
                data.append(1)
            else:
                data.append(0)
            input_data <<= 1
    
        print(data)
        output = crc7(data)
        print(bin(output))

