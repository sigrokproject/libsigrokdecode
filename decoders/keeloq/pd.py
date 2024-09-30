##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2024 Andrea Orazi <andrea.orazi@gmail.com>
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

class Ann:
        TE, LOGICAL_BIT, CODE_WORD, ENCRYP_DATA, FIXED_DATA = range(5)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'keyloq'
    name = 'KeyLoq'
    longname = 'KeeLoq CodeWord Decoder'
    desc = 'Keeloq CodeWord Decoder for Pulseview'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Security/crypto']
    channels = (
        {'id': 'pwm', 'name': 'PWM', 'desc': 'Code Word Channel'},
    )
    options = (
    
    )

    annotations = (
        ('te', 'TE'),
        ('logical_bit', 'Logical Bit'),
        ('Code_Word', 'Code Word'),
        ('encryp_data', 'Encrypted Data'),
        ('fixed_data', 'Fixed Data'),
    )
    annotation_rows = (
        ('bits', 'Bits', (Ann.TE,Ann.LOGICAL_BIT)),
        ('code word', 'Code Word', (Ann.CODE_WORD, )),
        ('data', 'Data', (Ann.ENCRYP_DATA, Ann.FIXED_DATA )),
    )
    
    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.TEcnt = 0 #TE counter
        self.Block_Init = 0 #Flag for each block of info
        #TE Timing - According to documentation a TE is typically 400 usecs
        #[0][1] - TE/Logical Bit 1 | [2][3] - Logical Bit 0 | [4][5] - Header Lenght 
        self.TE_Timing = [ 280e-6, 580e-6, 700e-6, 1000e-6, 3e-3, 6e-3 ]
        self.ssBlock = 0 #Sample number of a block of intormation
        self.Header_Completed = 0 #[ 0 = Not Complete 1 = Complete]
        self.n = 0 # Current Sample number
        self.prevN = 0 # Previous sample number
        self.Bitcnt = 0 # Bit counter in Data Portion
        self.trig_cond = '' #Wait - trigger condition
        self.BitString = '' # A string of Logical Bit Code Word
        self.KeyLoq = { "Encrypted" : "", "Serial-Number" : "", "S3" : "", "S0" : "", "S1" : "", "S2" : "", 
            "V-Low" : "", "RPT" : ""} #KeyLoq Code Word 

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
          if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    #Define the beginning of each useful block of information saving the Sample Number 
    def Start_Block(self):
        if (self.Block_Init == 0): 
                self.Block_Init = 1
                self.ssBlock = self.prevN

    #Shows Preable + Header
    def Decode_Preable(self,t):
        #According to documentation a TE is typically 400 usecs
        if ((t >= self.TE_Timing[0] and t <= self.TE_Timing[1] )):
            if (self.TEcnt < 23):
                self.put(self.prevN, self.samplenum, self.out_ann, [Ann.TE, [str(self.TEcnt)]])
                self.Start_Block()
        
            #Shows Preamble
            elif (self.TEcnt == 23):
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['Preamble']])
                self.put(self.prevN, self.samplenum, self.out_ann, [0, [str(self.TEcnt)]])

        # We have reached the last Rising Edge on TEcnt == 24 
        # This is not technically a TE . It is actually a period of 10 TEs known as Header
        # Header has usually a lenth of 3-6 msec 
        elif ( (t >= self.TE_Timing[4] and t <= self.TE_Timing[5] ) and (self.TEcnt == 24 ) ): 
            self.put(self.prevN, self.n, self.out_ann, [Ann.CODE_WORD, ['Header']])
            self.TEcnt = 0
            self.Block_Init = 0
            self.Header_Completed = 1 #Is 1 when the decoder successfully reached the end of Preable + Header
        
        else: #Reset Counters because this is not a TE
            self.TEcnt = 0
            self.Block_Init = 0
            
    #In Data Portion bits are encoded using PWM technique
    def Decode_LogicalBit(self,t): 
        # Logic Bit 0 = 2 TE at High Level + 1 TE at low level >> Tipically 800 usec (H) + 400 usec (L) <<
        # Logic Bit 1 = 1 TE at High Level + 2 TE at Low Level >> Tipically 400 usec (H) + 800 usec (L) <<
        #   Thus, To recognise a logical bit we have to read two subsequent Edges (or HalfBits)

        LogicalBit = '' #Either '0' or '1' encoded using PWM
        Valid_Bit = 0 

        #Check timing validity first
        if (( t >= self.TE_Timing[0] and t <= self.TE_Timing[1] ) or (t >= self.TE_Timing[2] and t <= self.TE_Timing[3] ) ):
            Valid_Bit = 1
            
            #Having got the next edge pointer n = first half of the Logical bit
            if (Valid_Bit):
                self.Start_Block() 
                
                #Gets the the next second half of the Logical bit to fully decode it
                if (self.Bitcnt == 65): #Last bit needs special care as definitely there is no valid edge nearby
                    self.n = self.samplenum + 8 #Arbitrary value after last sample# to complete this Logical Bit
                else:    
                    self.wait(self.trig_cond) 
                    self.n = self.samplenum

                #After time validity, it check wether it is '1' or '0'
                if ( t >= self.TE_Timing[0] and t <= self.TE_Timing[1] )  : 
                    LogicalBit = '1'
                else:
                    LogicalBit = '0'
                
                self.put(self.prevN, self.n, self.out_ann, [Ann.LOGICAL_BIT, ['Bit ' + LogicalBit ]])
                return (LogicalBit)

        else : #In case of Invalid bit, Reset all counters and conditions
            self.put(self.prevN, self.n, self.out_ann, [Ann.LOGICAL_BIT, ['>>> Invalid Bit <<< ' + LogicalBit ]])
            self.Reset_DP_Cnts()
            self.Header_Completed = 0
            self.Bitcnt = -1 #Will be set to 0 in the Main Cycle
            return("0")

    
    #Reset Data Portion counters at the end of each decoded block
    def Reset_DP_Cnts(self): 
        self.Block_Init = 0
        self.BitString =''

    #Convert a Binary string into the equivalent value in Hex 0x in string format
    def Bin2Hex (self):
        decimal_value = int(self.BitString, 2)
        # Convert integer to hexadecimal with leading zeroes
        hex_value = "0x{0:0{1}X}".format(decimal_value,7) 
        return ( hex_value )

    #Decode all Logical PWM Bit from 0 to 65 completing the CodeWord
    def Decode_DataPortion(self, t):  
        # Bits 0-31 : Encrypted Portion. It comes from the algorithm. 
        if (self.Bitcnt <= 31 ): 
            # According to the documentation LSB is transmitted first.
            #   However, decoding a bit string to Hex, requires that LSB must be the last bit in the string sequence
            #   to preserve bit significance.
            #   That's why --self.BitString-- is appended always as LSB, whereas the last transmitted bit
            #   is considered as MSB. This ensures the right interpretation and conversion to Hex 
            #   for both Encrypted and Fixed portion
            self.BitString = self.Decode_LogicalBit(t) + self.BitString

            if (self.Bitcnt == 31):
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['Encrypted Portion']])
                self.KeyLoq["Encrypted"] = self.Bin2Hex ()
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.ENCRYP_DATA, [ self.KeyLoq["Encrypted"] ]])
                self.Reset_DP_Cnts()

        # Here begins the cleartext portion known as Fixed Portion
        #   it is made by Serial Number + Button Code + Status (V-Low + Repeat\)
        elif (self.Bitcnt >= 32 and self.Bitcnt <= 59 ): # Bits 32-59 : Serial Number
            self.BitString = self.Decode_LogicalBit(t) + self.BitString

            if (self.Bitcnt == 59):
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['Serial Number']])
                self.KeyLoq["Serial-Number"] = self.Bin2Hex ()
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.FIXED_DATA, [ self.KeyLoq["Serial-Number"] ]])
                self.Reset_DP_Cnts()

        elif (self.Bitcnt >= 60 and self.Bitcnt <= 63 ): # Bits 60-63 : Button Code
            LogicalBit = self.Decode_LogicalBit(t)

            if ( self.Bitcnt == 60 ):
                self.KeyLoq["S3"] = LogicalBit
                self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ 'S3 = ' + self.KeyLoq["S3"] ]])
            elif ( self.Bitcnt == 61 ):
                self.KeyLoq["S0"] = LogicalBit
                self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ 'S0 = ' + self.KeyLoq["S0"] ]])
            elif ( self.Bitcnt == 62 ):
                self.KeyLoq["S1"] = LogicalBit
                self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ 'S1 = ' + self.KeyLoq["S1"] ]])
            elif (self.Bitcnt == 63):
                self.KeyLoq["S2"] = LogicalBit
                self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['Button Code']])
                self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ 'S2 = ' + self.KeyLoq["S2"] ]])
                self.Reset_DP_Cnts() 

        #Status
        elif (self.Bitcnt == 64 ): # Bits 64 : V-Low
            LogicalBit = self.Decode_LogicalBit(t)

            self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['V-Low']])
            if (LogicalBit == '0'):
                self.KeyLoq["V-Low"] =  "Battery High"
            else:
                self.KeyLoq["V-Low"] =  "Battery Low"
            
            self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ self.KeyLoq["V-Low"] ]])
            self.Reset_DP_Cnts()
        
        elif (self.Bitcnt == 65 ): # Bits 65 : Repeat
            LogicalBit = self.Decode_LogicalBit(t)

            self.put(self.ssBlock, self.n, self.out_ann, [Ann.CODE_WORD, ['RPT']])
            if (LogicalBit == '0'):
                self.KeyLoq["RPT"] = "No"
            else:
                self.KeyLoq["RPT"] = "Yes"

            self.put(self.prevN, self.n, self.out_ann, [Ann.FIXED_DATA, [ self.KeyLoq["RPT"] ]])
            self.Reset_DP_Cnts()
            self.Header_Completed = 0 #Looks for another new CodeWord
            self.Bitcnt = -1 #To start from 0 in the Main - decode() it needs to be negative

    # Main Loop    
    def decode(self):
        if self.samplerate is None:
            raise Exception('Cannot decode without samplerate.')
              
        t = 0 #Time between two edges

        #Each CodeWord begins with a Rising Edge.
        self.trig_cond = [{0: 'r'}] # Go and look for it
        self.wait(self.trig_cond) 
        self.prevN = self.samplenum 
        
        self.trig_cond = [{0: 'e'}] # Go to the next Edge

        while True:    

            self.wait(self.trig_cond)
            self.n = self.samplenum      

            #Get time (usec) between the current and the previous sample 
            t = (self.n - self.prevN) / self.samplerate
            
            #CodeWord decoding subfunctions
            if (self.Header_Completed == 0):
                self.TEcnt += 1
                self.Decode_Preable(t)
            else:
                self.Decode_DataPortion (t)
                self.Bitcnt += 1
        
            #Ready for the next cycle
            self.prevN = self.samplenum
