##
## This file is part of the sigrok project.
##
## Copyright (C) 2011-2012 Uwe Hermann <uwe@hermann-uwe.de>
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

# 1-Wire protocol decoder

import sigrokdecode as srd

# Annotation feed formats
ANN_ASCII = 0
ANN_DEC = 1
ANN_HEX = 2
ANN_OCT = 3
ANN_BITS = 4

class Decoder(srd.Decoder):
    api_version = 1
    id = 'onewire'
    name = '1-Wire'
    longname = ''
    desc = '1-Wire bus and MicroLan'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['onewire']
    probes = [
        {'id': 'owr', 'name': 'OWR', 'desc': '1-Wire bus'},
    ]
    optional_probes = [
        {'id': 'pwr', 'name': 'PWR', 'desc': '1-Wire power'},
    ]
    options = {
        'overdrive': ['Overdrive', 0],
    }
    annotations = [
        ['ASCII', 'Data bytes as ASCII characters'],
        ['Decimal', 'Databytes as decimal, integer values'],
        ['Hex', 'Data bytes in hex format'],
        ['Octal', 'Data bytes as octal numbers'],
        ['Bits', 'Data bytes in bit notation (sequence of 0/1 digits)'],
    ]

    def __init__(self, **kwargs):
        # Common variables
        self.samplenum = 0
        # Link layer variables
        self.lnk_state   = 'WAIT FOR FALLING EDGE'
        self.lnk_event   = 'NONE'
        self.lnk_fall    = 0
        self.lnk_present = 0
        self.lnk_bit     = 0
        # Network layer variables
        self.net_state   = 'ROM COMMAND'
        self.net_event   = 'NONE'
        self.net_cnt     = 0
        self.net_search  = "P"
        self.net_data_p  = 0x0
        self.net_data_n  = 0x0
        self.net_data    = 0x0
        # Transport layer variables
        self.trn_state   = 'WAIT FOR EVENT'
        self.trn_event   = 'NONE'

    def start(self, metadata):
        self.samplerate = metadata['samplerate']
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire')
        self.out_ann   = self.add(srd.OUTPUT_ANN  , 'onewire')

        # The width of the 1-Wire time base (30us) in number of samples.
        # TODO: optimize this value
        self.time_base = float(self.samplerate) * float(0.000030)
        print ("DEBUG: samplerate = %d, time_base = %d" % (self.samplerate, self.time_base))

    def report(self):
        pass

    def decode(self, ss, es, data):
        for (self.samplenum, (owr, pwr)) in data:
#            print ("DEBUG: sample = %d, owr = %d, pwr = %d, lnk_fall = %d, lnk_state = %s" % (self.samplenum, owr, pwr, self.lnk_fall, self.lnk_state))

            # Data link layer

            # Clear events.
            self.lnk_event = "NONE"
            # State machine.
            if self.lnk_state == 'WAIT FOR FALLING EDGE':
                # The start of a cycle is a falling edge.
                if (owr == 0):
                    # Save the sample number for the falling edge.
                    self.lnk_fall = self.samplenum
                    # Go to waiting for sample time
                    self.lnk_state = 'WAIT FOR DATA SAMPLE'
                    self.put(self.lnk_fall, self.samplenum, self.out_ann,
                             [ANN_DEC, ['LNK: NEGEDGE: ']])
            elif self.lnk_state == 'WAIT FOR DATA SAMPLE':
                # Data should be sample one 'time unit' after a falling edge
                if (self.samplenum - self.lnk_fall == 0.5*self.time_base):
                    self.lnk_bit  = owr & 0x1
                    self.lnk_event = "DATA BIT"
                    if (self.lnk_bit) :  self.lnk_state = 'WAIT FOR FALLING EDGE'
                    else              :  self.lnk_state = 'WAIT FOR RISING EDGE'
                    self.put(self.lnk_fall, self.samplenum, self.out_ann,
                             [ANN_DEC, ['LNK: BIT: ' + str(self.lnk_bit)]])
            elif self.lnk_state == 'WAIT FOR RISING EDGE':
                # The end of a cycle is a rising edge.
                if (owr == 1):
                    # A reset cycle is longer than 8T.
                    if (self.samplenum - self.lnk_fall > 8*self.time_base):
                        # Save the sample number for the falling edge.
                        self.lnk_rise = self.samplenum
                        # Send a reset event to the next protocol layer.
                        self.lnk_event = "RESET"
                        self.lnk_state = "WAIT FOR PRESENCE DETECT"
                        self.put(self.lnk_fall, self.samplenum, self.out_proto,
                                 ['RESET'])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann,
                                 [ANN_DEC, ['LNK: RESET: ']])
                        print ("DEBUG: RESET t0=%d t+=%d" % (self.lnk_fall, self.samplenum))
                        # Reset the timer.
                        self.lnk_fall = self.samplenum
                    # Otherwise this is assumed to be a data bit.
                    else :
                        self.lnk_state = "WAIT FOR FALLING EDGE"
            elif self.lnk_state == 'WAIT FOR PRESENCE DETECT':
                # Data should be sample one 'time unit' after a falling edge
                if (self.samplenum - self.lnk_rise == 2.5*self.time_base):
                    self.lnk_present = owr & 0x1
                    # Save the sample number for the falling edge.
                    if not (self.lnk_present) :  self.lnk_fall = self.samplenum
                    # create presence detect event
                    #self.lnk_event   = "PRESENCE DETECT"
                    if (self.lnk_present) :  self.lnk_state = 'WAIT FOR FALLING EDGE'
                    else                  :  self.lnk_state = 'WAIT FOR RISING EDGE'
                    self.put(self.lnk_fall, self.samplenum, self.out_ann,
                             [ANN_DEC, ['LNK: PRESENCE: ' + str(self.lnk_present)]])
                    print ("DEBUG: PRESENCE=%d t0=%d t+=%d" % (self.lnk_present, self.lnk_fall, self.samplenum))
            else:
                raise Exception('Invalid lnk_state: %d' % self.lnk_state)

            # Network layer
            
            # Clear events.
            self.net_event = "RESET"
            # State machine.
            if (self.lnk_event == "RESET"):
                self.net_state = "ROM COMMAND"
                self.net_search = "P"
                self.net_cnt    = 0
            elif (self.lnk_event == "DATA BIT"):
                if (self.net_state == "ROM COMMAND"):
                    if (self.collect_data(8)):
#                        self.put(self.lnk_fall, self.samplenum,
#                                 self.out_proto, ['LNK: COMMAND', self.net_data])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann,
                                 [ANN_DEC, ['NET: ROM COMMAND: 0x' + hex(self.net_data)]])
                        print ("DEBUG: ROM_COMMAND=0x%02x t0=%d t+=%d" % (self.net_data, self.lnk_fall, self.samplenum))
                        if   (self.net_data in [0x33, 0x0f]):
                            # READ ROM
                            self.net_state = "ADDRESS"
                        elif (self.net_data == 0xcc):
                            # SKIP ROM
                            self.net_state = "CONTROL COMMAND"
                        elif (self.net_data == 0x55):
                            # MATCH ROM
                            self.net_state = "ADDRESS"
                        elif (self.net_data == 0xf0):
                            # SEARCH ROM
                            self.net_state = "SEARCH"
                        elif (self.net_data == 0x3c):
                            # OVERDRIVE SKIP ROM
                            self.net_state = "CONTROL COMMAND"
                        elif (self.net_data == 0x69):
                            # OVERDRIVE MATCH ROM
                            self.net_state = "ADDRESS"
                elif (self.net_state == "ADDRESS"):
                    # family code (1B) + serial number (6B) + CRC (1B)
                    if (self.collect_data((1+6+1)*8)):
                        self.net_family_code   = (self.net_data >> ((  0)*8)) & 0xff
                        self.net_serial_number = (self.net_data >> ((  1)*8)) & 0xffffffffffff
                        self.net_crc           = (self.net_data >> ((6+1)*8)) & 0xff
                        print ("DEBUG: net_family_code  =0x%001x" % (self.net_family_code  ))
                        print ("DEBUG: net_serial_number=0x%012x" % (self.net_serial_number))
                        print ("DEBUG: net_crc          =0x%001x" % (self.net_crc          ))
                        self.net_state = "CONTROL COMMAND"
                elif (self.net_state == "SEARCH"):
                    # family code (1B) + serial number (6B) + CRC (1B)
                    if (self.collect_search((1+6+1)*8)):
                        self.net_family_code   = (self.net_data >> ((  0)*8)) & 0xff
                        self.net_serial_number = (self.net_data >> ((  1)*8)) & 0xffffffffffff
                        self.net_crc           = (self.net_data >> ((6+1)*8)) & 0xff
                        print ("DEBUG: net_family_code  =0x%001x" % (self.net_family_code  ))
                        print ("DEBUG: net_serial_number=0x%012x" % (self.net_serial_number))
                        print ("DEBUG: net_crc          =0x%001x" % (self.net_crc          ))
                        self.net_state = "CONTROL COMMAND"
                elif (self.net_state == "CONTROL COMMAND"):
                    if (self.collect_data(8)):
#                        self.put(self.lnk_fall, self.samplenum,
#                                 self.out_proto, ['LNK: COMMAND', self.net_data])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann,
                                 [ANN_DEC, ['NET: FUNCTION COMMAND: 0x' + hex(self.net_data)]])
                        print ("DEBUG: FUNCTION_COMMAND=0x%02x t0=%d t+=%d" % (self.net_data, self.lnk_fall, self.samplenum))
                        if   (self.net_data == 0x44):
                            # CONVERT TEMPERATURE
                            self.net_state = "TODO"
                        elif (self.net_data == 0x48):
                            # COPY SCRATCHPAD
                            self.net_state = "TODO"
                        elif (self.net_data == 0x4e):
                            # WRITE SCRATCHPAD
                            self.net_state = "TODO"
                        elif (self.net_data == 0xbe):
                            # READ SCRATCHPAD
                            self.net_state = "TODO"
                        elif (self.net_data == 0xb8):
                            # RECALL E2
                            self.net_state = "TODO"
                        elif (self.net_data == 0xb4):
                            # READ POWER SUPPLY
                            self.net_state = "TODO"
                else:
                    raise Exception('Invalid net_state: %s' % self.net_state)
            elif (self.lnk_event != "NONE"):
                raise Exception('Invalid lnk_event: %s' % self.lnk_event)


    # Link/Network layer data collector
    def collect_data (self, length):
        #print ("DEBUG: BIT=%d t0=%d t+=%d" % (self.lnk_bit, self.lnk_fall, self.samplenum))
        self.net_data = self.net_data & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
        self.net_cnt  = self.net_cnt + 1
        if (self.net_cnt == length):
            self.net_data = self.net_data & ((1<<length)-1)
            self.net_cnt  = 0
            print ("DEBUG: DATA=0x%0x t0=%d t+=%d" % (self.net_data, self.lnk_fall, self.samplenum))
            return (1)
        else:
            return (0)

    # Link/Network layer search collector
    def collect_search (self, length):
        #print ("DEBUG: SEARCH=%s BIT=%d t0=%d t+=%d" % (self.net_search, self.lnk_bit, self.lnk_fall, self.samplenum))
        if   (self.net_search == "P"):
          self.net_data_p = self.net_data_p & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
          self.net_search = "N"
        elif (self.net_search == "N"):
          self.net_data_n = self.net_data_n & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
          self.net_search = "D"
        elif (self.net_search == "D"):
          self.net_data   = self.net_data   & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
          self.net_search = "P"
          self.net_cnt    = self.net_cnt + 1
        if (self.net_cnt == length):
            self.net_data_p = self.net_data_p & ((1<<length)-1)
            self.net_data_n = self.net_data_n & ((1<<length)-1)
            self.net_data   = self.net_data   & ((1<<length)-1)
            self.net_search = "P"
            self.net_cnt    = 0
            print ("DEBUG: SEARCH_P=0x%0x t0=%d t+=%d" % (self.net_data_p, self.lnk_fall, self.samplenum))
            print ("DEBUG: SEARCH_N=0x%0x t0=%d t+=%d" % (self.net_data_n, self.lnk_fall, self.samplenum))
            print ("DEBUG: SEARCH  =0x%0x t0=%d t+=%d" % (self.net_data  , self.lnk_fall, self.samplenum))
            return (1)
        else:
            return (0)
