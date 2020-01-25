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

#from .lists import *

from .IrmpPythonWrap import IrmpWrap

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ir_irmp'
    name = 'IR IRMP'
    longname = 'IR IRMP multi protocol decoder'
    desc = 'IRMP - multi protocol infrared decoder with support for many IR protocols by Frank M. (ukw)'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['IR']
    channels = (
        {'id': 'ir', 'name': 'IR', 'desc': 'Data line'},
    )
    options = (
        {'id': 'polarity', 'desc': 'Polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high')},
#
#        {'id': 'cd_freq', 'desc': 'Carrier Frequency', 'default': 0},
    )
    annotations = (
        ('packet', 'Packet'),
        ('debug', 'Debug'),
    )
    annotation_rows = (
        ('packets', 'IR Packets', (0,)),
        ('debug', 'Debug', (1,)),
    )
    irmp = IrmpWrap()

    def putIr(self, data):
        ss     = data['start'] * self.subSample
        es     = data['end']   * self.subSample
        ad     = data['data']['address']
        pr     = data['data']['protocol']
        pn     = data['data']['protocolName']
        cm     = data['data']['command']
        repeat = data['data']['repeat']
        
        
       # print(f" {self.samplenum}  {ss} - {es} ({data['start']} - {data['end']})")
        self.put(ss, es, self.out_ann,
                 [0, [ f"Protocol: {pn} ({pr}), Address 0x{ad:04x}, Command: 0x{cm:04x} {'repeated' if repeat else ''}",
                       f"P: {pn} ({pr}), Ad: 0x{ad:x}, Cmd: 0x{cm:x} {'rep' if repeat else ''}",
                       f"P: {pr}  A: 0x{ad:x} C: 0x{cm:x} {'rep' if repeat else ''}",
                       f"C:{cm:x} A:{ad:x} {'r' if repeat else ''}",
                       f"C:{cm:x}",
                     ]])

    def __init__(self):
        self.irmp = Decoder.irmp
        self.reset()

    def reset(self):
        self.irmp.Reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value


    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        
        if (self.samplerate % self.irmp.GetSampleRate()) != 0:
            raise SamplerateError(f'samplerate has to be multple of {self.irmp.GetSampleRate()}' )
            
        self.subSample  = int(self.samplerate / self.irmp.GetSampleRate())
        sampleSkip = self.subSample
        #self.reset()
        #print (f" startdecode: samplenum {self.samplenum} rate: {self.samplerate} subsample {self.subSample}")
        # cd_count = None
        # if self.options['cd_freq']:
        #     cd_count = int(self.samplerate / self.options['cd_freq']) + 1
        
        self.active = 0 if self.options['polarity'] == 'active-low' else 1

        (ir,) = self.wait([{'skip' : sampleSkip}])
        i = 0

        while True:
            ##### todo: check if ir carrier frequency detection can be used
            #
            # Detect changes in the presence of an active input signal.
            # The decoder can either be fed an already filtered RX signal
            # or optionally can detect the presence of a carrier. Periods
            # of inactivity (signal changes slower than the carrier freq,
            # if specified) pass on the most recently sampled level. This
            # approach works for filtered and unfiltered input alike, and
            # only slightly extends the active phase of input signals with
            # carriers included by one period of the carrier frequency.
            # IR based communication protocols can cope with this slight
            # inaccuracy just fine by design. Enabling carrier detection
            # on already filtered signals will keep the length of their
            # active period, but will shift their signal changes by one
            # carrier period before they get passed to decoding logic.
            #   if cd_count:
            #       (cur_ir,) = self.wait([{0: 'e'}, {'skip': cd_count}])
            #       if self.matched[0]:
            #           cur_ir = self.active
            #       if cur_ir == prev_ir:
            #           continue
            #       prev_ir = cur_ir
            #       self.ir = cur_ir
            #   else:
            #       (self.ir,) = self.wait({0: 'e'})
            #   
            #print (f"samplenum {self.samplenum}")
            #if i%100 == 0:
            #    self.put(self.samplenum, self.samplenum+10, self.out_ann,
            #             [1, [ f"{self.samplenum}  - {i}",]])

            if self.active == 1:
                ir = 1 - ir
                
            if self.irmp.AddSample(ir):
                data = self.irmp.GetData()
                self.putIr(data)
            i = i + 1
            (ir,) = self.wait([{'skip' : sampleSkip}])

