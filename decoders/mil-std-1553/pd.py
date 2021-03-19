##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2020 Maxim Korzhavin <litlager@mail.ru>
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
from functools import reduce
from math import ceil

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'mil-std-1553'
    name = 'mil-std-1553'
    longname = 'mil std 1553 decoder'
    desc = 'Asynchronous.'
    license = 'gplv3+'
    inputs = ['logic']
    outputs = []
    tags = ['Embedded/industrial']

    channels = (
        {'id': 'DP', 'name': 'PD', 'desc': 'Data positive signal'},
    )
    options = (
        {'id': 'language', 'desc': 'Language', 'default': 'ru',
            'values': ('ru', 'en')},
        {'id': 'device_type', 'desc': 'Type of device', 'default': 'master',
            'values': ('master', 'slave')},
    )
    annotations = (
        ('cw', 'CW'),
        ('dw', 'DW'),
        ('warning', 'WARNING'),
        ('error', 'ERROR'),
        ('cw_details', 'CW DETAILS'),
        ('dw_details', 'DW DETAILS'),
        ('aw_details', 'AW DETAILS'),
    )
    annotation_rows = (
        ('data', 'Data', (0,1,2)),
        ('details', 'Details', (3,4,5,6,)),
    )

    e_parity = ['parity error', 'ошибка паритета']
    e_count = ['error bit count', 'ошибка числа бит']

    e_m_notgroup = ['. not group','. групповой быть не может']

    m_group = ['group:','групповая:']

    e_m_comm = [' error code of command',' ошибка кода команды']
    m_accept = [' accept interface management',' принять управление интерфесом']
    m_synch = [' synchronization',' синхронизация']
    m_sendaw = [' send AW',' передать ОС']
    m_selfcontrol = [' start self-control',' начать самоконтроль ОУ']
    m_blocktx = [' block TX',' блокировать передатчик']
    m_unlock = [' unlock TX',' разблокировать передатчик']
    m_blocksign = [' block sign of malfunction',' блокировать признак неисправности ОУ']
    m_reset = [' reset',' установить ОУ в исходное состояние']
    m_sendvec = [' transfer vector word',' передать векторное слово']
    m_lastcomm = [' transfer last command',' передать последнюю команду']
    m_sendvsk = [' send VSK word',' передать слово ВСК ОУ']
    m_synchdw = [' synchronization with DW',' синхронизация с СД']
    m_blocki = [' block i TX',' блокировать i-й передатчик']
    m_unlocki = [' unlock i TX',' разблокировать i-й передатчик']
    m_transmit = [' for transmit',' на передачу']
    m_reception = [' for reception',' на прием']
    
    m_dw = [' DW',' СД']

    m_itd = [' to TD',' в ОУ']
    m_ftd = [' from TD',' из ОУ']

    s_errorinmessage = [' error in message.',' ошибка в сообщении.']
    s_txaw = [' transmition answer word.',' передача ОС.']
    s_servicereq = [' service request.',' запрос на обслуживание.']
    s_gcommacc = [' group command accepted.',' принята групповая команда.']
    s_abusy = [' subscriber is busy.',' абонент занят.']
    s_faults = [' subscriber is fault.',' неисправность абонента.']
    s_intmanacc = [' interface management accepted.',' принято управление интерфейсом.']
    s_faultdev = [' device is fault.', ' неисправность ОУ.']

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'FIND_BIT_AFTER_10_BIT'
        self.samplerate = None

        self.prelastsample = 0
        self.lastsample = 0
        self.actualsample = 0

        self.syncsample = 0;
        self.synctype = 'Data';
        self.cwdetailscolour = 4

        self.halfbit = 5e-7
        self.bitwindow = 4e-7

        self.bits = 0
        self.bitcount = 0
        self.dwcount = 0

    def isparity(self):
        bitsvalue = self.bits
        tmpparity = 0
        for i in range(0,17):
            tmpparity = tmpparity + bitsvalue % 2
            bitsvalue = bitsvalue >> 1
        if tmpparity%2 == 1:
            return True
        else:
            return False

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
        self.halfbit = ceil(self.halfbit * self.samplerate)
        self.bitwindow = ceil(self.bitwindow * self.samplerate)

    def waitx(self,rftype):
        self.wait({0: rftype})
        self.prelastsample = self.lastsample
        self.lastsample = self.actualsample
        self.actualsample = self.samplenum

    def puthexdata(self):
        hexdatavalue = format(self.bits>>1, 'X')
        for i in range(0,4-len(hexdatavalue)):
            hexdatavalue = '0' + hexdatavalue
        hexdatavalue = '0x' + hexdatavalue
        return hexdatavalue

    def putdwdetails(self):
        dwdetailsvalue = '№:' + format(self.dwcount)
        return dwdetailsvalue

    def putcwdetails(self):
        if self.options['device_type'] == 'master':
            self.cwdetailscolour = 4
            adrvalue = ((self.bits >> 12) & 0x1F)
            kvalue = ((self.bits >> 11) & 0x1)
            subadrvalue = ((self.bits >> 6) & 0x1F)
            countdwvalue = ((self.bits >> 1) & 0x1F)
            if(adrvalue == 31):
                cwdetailsvalue = self.m_group[self.lang]
            elif kvalue == 1:
            	cwdetailsvalue = self.m_ftd[self.lang] + format(adrvalue)
            else:
                cwdetailsvalue = self.m_itd[self.lang] + format(adrvalue)
            if (subadrvalue == 0x0) | (subadrvalue == 0x1F):
                cmdinfvalue = self.e_m_comm[self.lang]
                if kvalue == 1:
                    if (countdwvalue == 0):
                        cmdinfvalue = self.m_accept[self.lang]
                        if(adrvalue == 31):
                            self.cwdetailscolour = 3
                            cmdinfvalue = cmdinfvalue + self.e_m_notgroup[self.lang]
                    elif (countdwvalue == 1):
                        cmdinfvalue = self.m_synch[self.lang]
                    elif (countdwvalue == 2):
                        cmdinfvalue = self.m_sendaw[self.lang]
                        if(adrvalue == 31):
                            self.cwdetailscolour = 3
                            cmdinfvalue = cmdinfvalue + self.e_m_notgroup[self.lang]
                    elif (countdwvalue == 3):
                        cmdinfvalue = self.m_selfcontrol[self.lang]
                    elif (countdwvalue == 4):
                        cmdinfvalue = self.m_blocktx[self.lang]
                    elif (countdwvalue == 5):
                        cmdinfvalue = self.m_unlocktx[self.lang]
                    elif (countdwvalue == 6):
                        cmdinfvalue = self.m_blocksign[self.lang]
                    elif (countdwvalue == 7):
                        cmdinfvalue = self.m_reset[self.lang]

                    elif (countdwvalue == 16):
                        cmdinfvalue = self.m_sendvec[self.lang]
                        if(adrvalue == 31):
                            self.cwdetailscolour = 3
                            cmdinfvalue = cmdinfvalue + self.e_m_notgroup[self.lang]
                    elif (countdwvalue == 18):
                        cmdinfvalue = self.m_lastcomm[self.lang]
                        if(adrvalue == 31):
                            self.cwdetailscolour = 3
                            cmdinfvalue = cmdinfvalue + self.e_m_notgroup[self.lang]
                    elif (countdwvalue == 19):
                        cmdinfvalue = self.m_sendvsk[self.lang]
                        if(adrvalue == 31):
                            self.cwdetailscolour = 3
                            cmdinfvalue = cmdinfvalue + self.e_m_notgroup[self.lang]

                else:
                    if (countdwvalue == 17):
                        cmdinfvalue = self.m_synchdw[self.lang]
                    elif (countdwvalue == 20):
                        cmdinfvalue = self.m_blocki[self.lang]
                    elif (countdwvalue == 21):
                        cmdinfvalue = self.m_unlocki[self.lang]
                cwdetailsvalue = cwdetailsvalue + cmdinfvalue

            else:
                if kvalue == 1:
                    cwdetailsvalue = cwdetailsvalue + self.m_transmit[self.lang]
                else:
                    cwdetailsvalue = cwdetailsvalue + self.m_reception[self.lang]

                if countdwvalue == 0:
                    countdwvalue = 32
                cwdetailsvalue = cwdetailsvalue + ' ' + format(countdwvalue) + self.m_dw[self.lang]
            pass    
            return cwdetailsvalue
        else:
            cwdetailsvalue = ''
            self.cwdetailscolour = 6

            if ((self.bits >> 11) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_errorinmessage[self.lang]
            if ((self.bits >> 10) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_txaw[self.lang]
            if ((self.bits >> 9) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_servicereq[self.lang]

            if ((self.bits >> 5) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_gcommacc[self.lang]
            if ((self.bits >> 4) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_abusy[self.lang]
            if ((self.bits >> 3) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_faults[self.lang]
            if ((self.bits >> 2) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_intmanacc[self.lang]
            if ((self.bits >> 1) & 0x1):
                cwdetailsvalue = cwdetailsvalue + self.s_faultdev[self.lang]

            if cwdetailsvalue == '':
                cwdetailsvalue = 'OK'
                self.cwdetailscolour = 4
            return cwdetailsvalue

    def putwordlabel(self):
        if self.synctype == 'CW':
            if(self.isparity()):
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [0, ['%s: %s' % (self.synctype, self.puthexdata())]])
                cwdetailswalue = self.putcwdetails()
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [self.cwdetailscolour, ['%s' % (cwdetailswalue)]])
            else:
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [0, ['%s' % (self.synctype) ]])
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [3, ['%s' % (self.e_parity[self.lang]) ]])
        elif self.synctype == 'DW':
            if(self.isparity()):
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [1, ['%s: %s' % (self.synctype, self.puthexdata())]])
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [5, ['%s' % (self.putdwdetails())]])
            else:
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [1, ['%s' % (self.synctype) ]])
                self.put(self.syncsample - 3*self.halfbit, self.actualsample + self.halfbit, self.out_ann, [3, ['%s' % (self.e_parity[self.lang]) ]])
            
    def resetbits(self):
        self.bits = 0
        self.bitcount = 0

    def addbit(self,bitvalue):
        self.bits = self.bits*2 + bitvalue
        self.bitcount = self.bitcount + 1
        if(self.syncsample != 0):
            if self.bitcount == 17:
                self.putwordlabel()       
            else:
                if self.bitcount > 17:
                    self.put(self.actualsample - self.halfbit, self.actualsample + self.halfbit, self.out_ann, [3, ['%s' % (self.e_count[self.lang])]])
                    if self.synctype == 'CW':
                    	self.put(self.actualsample - self.halfbit, self.actualsample + self.halfbit, self.out_ann, [0, ['%s' % (self.synctype) ]])
                    else:
                    	self.put(self.actualsample - self.halfbit, self.actualsample + self.halfbit, self.out_ann, [1, ['%s' % (self.synctype) ]])
					

    def newsyncword(self,newtype):
        if(self.syncsample != 0):
            if self.bitcount < 17:
                self.put(self.syncsample - 3*self.halfbit, self.prelastsample + self.halfbit, self.out_ann, [2, ['%s sync' % (self.synctype)]])
                self.put(self.syncsample - 3*self.halfbit, self.prelastsample + self.halfbit, self.out_ann, [3, ['%s -%d' % (self.e_count[self.lang], abs(17-self.bitcount))]])
        self.synctype = newtype
        if newtype == 'CW':
            self.state = 'FIND_BIT_AFTER_COMMAND_SYNC'
            self.dwcount = 0
        else:
            self.state = 'FIND_BIT_AFTER_DATA_SYNC'
            self.dwcount = self.dwcount + 1
        self.resetbits()
        self.syncsample = self.actualsample

    def isdiffinwindow(self,timevalue):
        if abs((self.actualsample - self.lastsample) - timevalue*self.halfbit) < self.bitwindow:
            return 1
        else:
            return 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        if self.options['language'] == 'en':
            self.lang = 0
        else:
            self.lang = 1

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:
            if self.state == 'FIND_BIT_AFTER_COMMAND_SYNC':
                self.waitx('r')
                if self.isdiffinwindow(4):
                    self.addbit(0)
                    self.state = 'FIND_BIT_AFTER_01_BIT'
                elif self.isdiffinwindow(3):
                    self.waitx('f')
                    if self.isdiffinwindow(1):
                        self.addbit(1)  
                        self.state = 'FIND_BIT_AFTER_10_BIT'

            elif self.state == 'FIND_BIT_AFTER_DATA_SYNC':
                self.waitx('f')
                if self.isdiffinwindow(4):
                    self.addbit(1)
                    self.state = 'FIND_BIT_AFTER_10_BIT'
                elif self.isdiffinwindow(3):
                    self.waitx('r')
                    if self.isdiffinwindow(1):
                        self.addbit(0) 
                        self.state = 'FIND_BIT_AFTER_01_BIT'

            elif self.state == 'FIND_BIT_AFTER_10_BIT':
                self.waitx('r')
                if self.isdiffinwindow(2):
                    self.addbit(0)
                    self.state = 'FIND_BIT_AFTER_01_BIT'
                elif self.isdiffinwindow(4):
                    self.newsyncword('DW')
                elif self.isdiffinwindow(1):
                    self.waitx('f')
                    if self.isdiffinwindow(1):
                        self.addbit(1)  
                        self.state = 'FIND_BIT_AFTER_10_BIT'
                    elif self.isdiffinwindow(3):
                        self.newsyncword('CW')
                else: 
                    self.waitx('f')
                    if self.isdiffinwindow(3):
                        self.newsyncword('CW')

            elif self.state == 'FIND_BIT_AFTER_01_BIT':
                self.waitx('f')
                if self.isdiffinwindow(2):
                    self.addbit(1)
                    self.state = 'FIND_BIT_AFTER_10_BIT'
                elif self.isdiffinwindow(4):
                    self.newsyncword('CW')
                elif self.isdiffinwindow(1):
                    self.waitx('r')
                    if self.isdiffinwindow(1):
                        self.addbit(0)   
                        self.state = 'FIND_BIT_AFTER_01_BIT'
                    elif self.isdiffinwindow(3):
                        self.newsyncword('DW')
                    else:
                        self.waitx('f')
                        if self.isdiffinwindow(3):
                            self.newsyncword('CW')
                
