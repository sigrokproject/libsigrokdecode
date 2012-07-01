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
ANN_LINK      = 0
ANN_NETWORK   = 1
ANN_TRANSPORT = 2

# a dictionary of ROM commands and their names
rom_command = {0x33: "READ ROM",
               0x0f: "CONDITIONAL READ ROM",
               0xcc: "SKIP ROM",
               0x55: "MATCH ROM",
               0xf0: "SEARCH ROM",
               0xec: "CONDITIONAL SEARCH ROM",
               0x3c: "OVERDRIVE SKIP ROM",
               0x6d: "OVERDRIVE MATCH ROM"}

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
        'overdrive' : ['Overdrive', 1],
        'cnt_normal_bit'        : ['Time (in samplerate periods) for normal mode sample bit'     , 0],
        'cnt_normal_presence'   : ['Time (in samplerate periods) for normal mode sample presence', 0],
        'cnt_normal_reset'      : ['Time (in samplerate periods) for normal mode reset'          , 0],
        'cnt_overdrive_bit'     : ['Time (in samplerate periods) for overdrive mode sample bit'     , 0],
        'cnt_overdrive_presence': ['Time (in samplerate periods) for overdrive mode sample presence', 0],
        'cnt_overdrive_reset'   : ['Time (in samplerate periods) for overdrive mode reset'          , 0],
    }
    annotations = [
        ['Link', 'Link layer events (reset, presence, bit slots)'],
        ['Network', 'Network layer events (device addressing)'],
        ['Transport', 'Transport layer events'],
    ]

    def __init__(self, **kwargs):
        # Common variables
        self.samplenum = 0
        # Link layer variables
        self.lnk_state   = 'WAIT FOR FALLING EDGE'
        self.lnk_event   = 'NONE'
        self.lnk_present = 0
        self.lnk_bit     = 0
        self.lnk_overdrive = 0
        # Event timing variables
        self.lnk_fall    = 0
        self.lnk_rise    = 0
        self.net_beg     = 0
        self.net_end     = 0
        # Network layer variables
        self.net_state   = 'IDLE'
        self.net_cnt     = 0
        self.net_search  = "P"
        self.net_data_p  = 0x0
        self.net_data_n  = 0x0
        self.net_data    = 0x0
        self.net_rom     = 0x0000000000000000

    def start(self, metadata):
        self.out_proto = self.add(srd.OUTPUT_PROTO, 'onewire')
        self.out_ann   = self.add(srd.OUTPUT_ANN  , 'onewire')

        # check if samplerate is appropriate
        self.samplerate = metadata['samplerate']
        if (self.options['overdrive']):
            self.put(0, 0, self.out_ann, [ANN_LINK, ['NOTE: Sample rate checks assume overdrive mode.']])
            if   (self.samplerate < 2000000):
                self.put(0, 0, self.out_ann, [ANN_LINK, ['ERROR: Sampling rate is too low must be above 2MHz for proper overdrive mode decoding.']])
            elif (self.samplerate < 5000000):
                self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: Sampling rate is suggested to be above 5MHz for proper overdrive mode decoding.']])
        else:
            self.put(0, 0, self.out_ann, [ANN_LINK, ['NOTE: Sample rate checks assume normal mode only.']])
            if   (self.samplerate <  400000):
                self.put(0, 0, self.out_ann, [ANN_LINK, ['ERROR: Sampling rate is too low must be above 400kHz for proper normal mode decoding.']])
            elif (self.samplerate < 1000000):
                self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: Sampling rate is suggested to be above 1MHz for proper normal mode decoding.']])

        # The default 1-Wire time base is 30us, this is used to calculate sampling times.
        if (self.options['cnt_normal_bit']):      self.cnt_normal_bit      = self.options['cnt_normal_bit']
        else:                                     self.cnt_normal_bit      = int(float(self.samplerate) * 0.000015) - 1 # 15ns
        if (self.options['cnt_normal_presence']): self.cnt_normal_presence = self.options['cnt_normal_presence']
        else:                                     self.cnt_normal_presence = int(float(self.samplerate) * 0.000075) - 1 # 75ns
        if (self.options['cnt_normal_reset']):    self.cnt_normal_reset    = self.options['cnt_normal_reset']
        else:                                     self.cnt_normal_reset    = int(float(self.samplerate) * 0.000480) - 1 # 480ns
        if (self.options['cnt_overdrive_bit']):      self.cnt_overdrive_bit      = self.options['cnt_overdrive_bit']
        else:                                        self.cnt_overdrive_bit      = int(float(self.samplerate) * 0.000002) - 1 # 2ns
        if (self.options['cnt_overdrive_presence']): self.cnt_overdrive_presence = self.options['cnt_overdrive_presence']
        else:                                        self.cnt_overdrive_presence = int(float(self.samplerate) * 0.000010) - 1 # 10ns
        if (self.options['cnt_overdrive_reset']):    self.cnt_overdrive_reset    = self.options['cnt_overdrive_reset']
        else:                                        self.cnt_overdrive_reset    = int(float(self.samplerate) * 0.000048) - 1 # 48ns

        # Check if sample times are in the allowed range
        time_min = float(self.cnt_normal_bit  ) / self.samplerate
        time_max = float(self.cnt_normal_bit+1) / self.samplerate
        if ( (time_min < 0.000005) or (time_max > 0.000015) ) :
           self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: The normal mode data sample time interval (%2.1fus-%2.1fus) should be inside (5.0us, 15.0us).' % (time_min*1000000, time_max*1000000)]])
        time_min = float(self.cnt_normal_presence  ) / self.samplerate
        time_max = float(self.cnt_normal_presence+1) / self.samplerate
        if ( (time_min < 0.0000681) or (time_max > 0.000075) ) :
           self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: The normal mode presence sample time interval (%2.1fus-%2.1fus) should be inside (68.1us, 75.0us).' % (time_min*1000000, time_max*1000000)]])
        time_min = float(self.cnt_overdrive_bit  ) / self.samplerate
        time_max = float(self.cnt_overdrive_bit+1) / self.samplerate
        if ( (time_min < 0.000001) or (time_max > 0.000002) ) :
           self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: The overdrive mode data sample time interval (%2.1fus-%2.1fus) should be inside (1.0us, 2.0us).' % (time_min*1000000, time_max*1000000)]])
        time_min = float(self.cnt_overdrive_presence  ) / self.samplerate
        time_max = float(self.cnt_overdrive_presence+1) / self.samplerate
        if ( (time_min < 0.0000073) or (time_max > 0.000010) ) :
           self.put(0, 0, self.out_ann, [ANN_LINK, ['WARNING: The overdrive mode presence sample time interval (%2.1fus-%2.1fus) should be inside (7.3us, 10.0us).' % (time_min*1000000, time_max*1000000)]])

    def report(self):
        pass

    def decode(self, ss, es, data):
        for (self.samplenum, (owr, pwr)) in data:

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
            elif self.lnk_state == 'WAIT FOR DATA SAMPLE':
                # Sample data bit
                if (self.lnk_overdrive): cnt = self.cnt_overdrive_bit
                else                   : cnt = self.cnt_normal_bit
                if (self.samplenum - self.lnk_fall == cnt):
                    self.lnk_bit  = owr & 0x1
                    self.lnk_event = "DATA BIT"
                    if (self.lnk_bit):  self.lnk_state = 'WAIT FOR FALLING EDGE'
                    else             :  self.lnk_state = 'WAIT FOR RISING EDGE'
                    self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_LINK, ['BIT: %01x' % self.lnk_bit]])
            elif self.lnk_state == 'WAIT FOR RISING EDGE':
                # The end of a cycle is a rising edge.
                if (owr == 1):
                    # Check if this was a reset cycle
                    if (self.samplenum - self.lnk_fall > self.cnt_normal_reset):
                        # Save the sample number for the falling edge.
                        self.lnk_rise = self.samplenum
                        # Send a reset event to the next protocol layer.
                        self.lnk_event = "RESET"
                        self.lnk_state = "WAIT FOR PRESENCE DETECT"
                        self.put(self.lnk_fall, self.samplenum, self.out_proto, ['RESET'])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_LINK     , ['RESET']])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_NETWORK  , ['RESET']])
                        # Reset the timer.
                        self.lnk_fall = self.samplenum
                    elif ((self.samplenum - self.lnk_fall > self.cnt_overdrive_reset) and (self.lnk_overdrive)):
                        # Save the sample number for the falling edge.
                        self.lnk_rise = self.samplenum
                        # Send a reset event to the next protocol layer.
                        self.lnk_event = "RESET"
                        self.lnk_state = "WAIT FOR PRESENCE DETECT"
                        self.put(self.lnk_fall, self.samplenum, self.out_proto, ['RESET OVERDRIVE'])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_LINK     , ['RESET OVERDRIVE']])
                        self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_NETWORK  , ['RESET OVERDRIVE']])
                        # Reset the timer.
                        self.lnk_fall = self.samplenum
                    # Otherwise this is assumed to be a data bit.
                    else :
                        self.lnk_state = "WAIT FOR FALLING EDGE"
            elif self.lnk_state == 'WAIT FOR PRESENCE DETECT':
                # Sample presence status
                if (self.lnk_overdrive): cnt = self.cnt_overdrive_presence
                else                   : cnt = self.cnt_normal_presence
                if (self.samplenum - self.lnk_rise == cnt):
                    self.lnk_present = owr & 0x1
                    # Save the sample number for the falling edge.
                    if not (self.lnk_present) :  self.lnk_fall = self.samplenum
                    # create presence detect event
                    #self.lnk_event   = "PRESENCE DETECT"
                    if (self.lnk_present) :  self.lnk_state = 'WAIT FOR FALLING EDGE'
                    else                  :  self.lnk_state = 'WAIT FOR RISING EDGE'
                    present_str = "False" if self.lnk_present else "True"
                    self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_LINK   , ['PRESENCE: ' + present_str]])
                    self.put(self.lnk_fall, self.samplenum, self.out_ann, [ANN_NETWORK, ['PRESENCE: ' + present_str]])
            else:
                raise Exception('Invalid lnk_state: %d' % self.lnk_state)

            # Network layer

            # State machine.
            if (self.lnk_event == "RESET"):
                self.net_state = "COMMAND"
                self.net_search = "P"
                self.net_cnt    = 0
            elif (self.net_state == "IDLE"):
                pass
            elif (self.net_state == "COMMAND"):
                # Receiving and decoding a ROM command
                if (self.onewire_collect(8)):
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK, ['ROM COMMAND: 0x%02x \'%s\'' % (self.net_data, rom_command[self.net_data])]])
                    if   (self.net_data == 0x33):  # READ ROM
                        self.net_state = "GET ROM"
                    elif (self.net_data == 0x0f):  # CONDITIONAL READ ROM
                        self.net_state = "GET ROM"
                    elif (self.net_data == 0xcc):  # SKIP ROM
                        self.net_state = "TRANSPORT"
                    elif (self.net_data == 0x55):  # MATCH ROM
                        self.net_state = "GET ROM"
                    elif (self.net_data == 0xf0):  # SEARCH ROM
                        self.net_state = "SEARCH ROM"
                    elif (self.net_data == 0xec):  # CONDITIONAL SEARCH ROM
                        self.net_state = "SEARCH ROM"
                    elif (self.net_data == 0x3c):  # OVERDRIVE SKIP ROM
                        self.lnk_overdrive = 1
                        self.net_state = "TRANSPORT"
                    elif (self.net_data == 0x69):  # OVERDRIVE MATCH ROM
                        self.lnk_overdrive = 1
                        self.net_state = "GET ROM"
            elif (self.net_state == "GET ROM"):
                # A 64 bit device address is selected
                # family code (1B) + serial number (6B) + CRC (1B)
                if (self.onewire_collect(64)):
                    self.net_rom = self.net_data & 0xffffffffffffffff
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK, ['ROM: 0x%016x' % self.net_rom]])
                    self.net_state = "TRANSPORT"
            elif (self.net_state == "SEARCH ROM"):
                # A 64 bit device address is searched for
                # family code (1B) + serial number (6B) + CRC (1B)
                if (self.onewire_search(64)):
                    self.net_rom = self.net_data & 0xffffffffffffffff
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK, ['ROM: 0x%016x' % self.net_rom]])
                    self.net_state = "TRANSPORT"
            elif (self.net_state == "TRANSPORT"):
                # The transport layer is handled in byte sized units
                if (self.onewire_collect(8)):
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_NETWORK  , ['TRANSPORT: 0x%02x' % self.net_data]])
                    self.put(self.net_beg, self.net_end, self.out_ann, [ANN_TRANSPORT, ['TRANSPORT: 0x%02x' % self.net_data]])
                    self.put(self.net_beg, self.net_end, self.out_proto, ['transfer', self.net_data])
                    # TODO: Sending translort layer data to 1-Wire device models
            else:
                raise Exception('Invalid net_state: %s' % self.net_state)


    # Link/Network layer data collector
    def onewire_collect (self, length):
        if (self.lnk_event == "DATA BIT"):
            # Storing the sampe this sequence begins with
            if (self.net_cnt == 1):
                self.net_beg  = self.samplenum
            self.net_data = self.net_data & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
            self.net_cnt  = self.net_cnt + 1
            # Storing the sampe this sequence ends with
            # In case the full length of the sequence is received, return 1
            if (self.net_cnt == length):
                self.net_end  = self.samplenum
                self.net_data = self.net_data & ((1<<length)-1)
                self.net_cnt  = 0
                return (1)
            else:
                return (0)
        else:
            return (0)

    # Link/Network layer search collector
    def onewire_search (self, length):
        if (self.lnk_event == "DATA BIT"):
            # Storing the sampe this sequence begins with
            if ((self.net_cnt == 0) and (self.net_search == "P")):
                self.net_beg  = self.samplenum
            # Master receives an original address bit
            if   (self.net_search == "P"):
              self.net_data_p = self.net_data_p & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
              self.net_search = "N"
            # Master receives a complemented address bit
            elif (self.net_search == "N"):
              self.net_data_n = self.net_data_n & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
              self.net_search = "D"
            # Master transmits an address bit
            elif (self.net_search == "D"):
              self.net_data   = self.net_data   & ~(1 << self.net_cnt) | (self.lnk_bit << self.net_cnt)
              self.net_search = "P"
              self.net_cnt    = self.net_cnt + 1
            # Storing the sampe this sequence ends with
            # In case the full length of the sequence is received, return 1
            if (self.net_cnt == length):
                self.net_end  = self.samplenum
                self.net_data_p = self.net_data_p & ((1<<length)-1)
                self.net_data_n = self.net_data_n & ((1<<length)-1)
                self.net_data   = self.net_data   & ((1<<length)-1)
                self.net_search = "P"
                self.net_cnt    = 0
                return (1)
            else:
                return (0)
        else:
            return (0)
