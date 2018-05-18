##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2018 Elias Oenal <sigrok@eliasoenal.com>
## All rights reserved.
##
## Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##
## 1. Redistributions of source code must retain the above copyright notice,
##    this list of conditions and the following disclaimer.
## 2. Redistributions in binary form must reproduce the above copyright notice,
##    this list of conditions and the following disclaimer in the documentation
##    and/or other materials provided with the distribution.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
## IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
## ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
## LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
## CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
## SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
## INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
## CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
## ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
## POSSIBILITY OF SUCH DAMAGE.
##

import sigrokdecode as srd

MODULE_ID = {
    0x00: 'Unknown or unspecified',
    0x01: 'GBIC',
    0x02: 'Module/connector soldered to motherboard',
    0x03: 'SFP',
    0x04: '300 pin XSBI',
    0x05: 'XENPAK',
    0x06: 'XFP',
    0x07: 'XFF',
    0x08: 'XFP-E',
    0x09: 'XPAK',
    0x0a: 'X2',
    0x0B: 'DWDM-SFP',
    0x0C: 'QSFP',
    0x0D: 'QSFP+',
    0x0E: 'CFP',
    0x0F: 'CXP (TBD)',
    0x11: 'CFP2',
    0x12: 'CFP4',
}

class Decoder(srd.Decoder):
    api_version = 3
    id = 'cfp'
    name = 'CFP'
    longname = '100 Gigabit C form-factor pluggable (CFP)'
    desc = 'Data structure describing display device capabilities.'
    license = 'BSD'
    inputs = ['mdio']
    outputs = ['cfp']
    annotations = (
        ('cfp-register', 'Register'),
        ('cfp-decode', 'Decode'),
    )
    annotation_rows = (
        ('cfp-register', 'Register', (0,)),
        ('cfp-decode', 'Decode', (1,)),
    )

    def __init__(self):
        pass

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def decode(self, ss, es, data):
        for (clause45, clause45_address, is_read, portad, devad, register) in data:
            if is_read:
                if clause45_address >= 0x8000 and clause45_address <= 0x807F:
                    self.put(ss, es, self.out_ann, [0, ['CFP NVR 1: Basic ID registers', 'NVR1']])
                    if clause45_address == 0x8000:
                        self.put(ss, es, self.out_ann, [1, ['Module identifier: %s' % MODULE_ID.get(register, 'Reserved')]])
                elif clause45_address >= 0x8080 and clause45_address <= 0x80FF:
                    self.put(ss, es, self.out_ann, [0, ['CFP NVR 2: Extended ID registers', 'NVR2']])
                elif clause45_address >= 0x8100 and clause45_address <= 0x817F:
                    self.put(ss, es, self.out_ann, [0, ['CFP NVR 3: Network lane specific registers', 'NVR3']])
                elif clause45_address >= 0x8180 and clause45_address <= 0x81FF:
                    self.put(ss, es, self.out_ann, [0, ['CFP NVR 4', 'NVR4']])
                elif clause45_address >= 0x8400 and clause45_address <= 0x847F:
                    self.put(ss, es, self.out_ann, [0, ['Vendor NVR 1: Vendor data registers', 'V-NVR1']])
                elif clause45_address >= 0x8480 and clause45_address <= 0x84FF:
                    self.put(ss, es, self.out_ann, [0, ['Vendor NVR 2: Vendor data registers', 'V-NVR2']])
                elif clause45_address >= 0x8800 and clause45_address <= 0x887F:
                    self.put(ss, es, self.out_ann, [0, ['User NVR 1: User data registers', 'U-NVR1']])
                elif clause45_address >= 0x8880 and clause45_address <= 0x88FF:
                    self.put(ss, es, self.out_ann, [0, ['User NVR 2: User data registers', 'U-NVR2']])
                elif clause45_address >= 0xA000 and clause45_address <= 0xA07F:
                    self.put(ss, es, self.out_ann, [0, ['CFP Module VR 1: CFP Module level control and DDM registers', 'Mod-VR1']])
                elif clause45_address >= 0xA080 and clause45_address <= 0xA0FF:
                    self.put(ss, es, self.out_ann, [0, ['MLG VR 1: MLG Management Interface registers', 'MLG-VR1']])
