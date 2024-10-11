#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2020-2021 Tobias Peter <tobias.peter@infineon.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#

'''
Decode the TPM TIS transactions contained in an SPI signal.
References: [tis] TCG PC Client Platform TPM Profile (PTP) Specification https://trustedcomputinggroup.org/wp-content/uploads/TCG_PC_Client_Platform_TPM_Profile_PTP_2.0_r1.03_v22.pdf
'''

import sigrokdecode as srd

from . import tpm_tis_spi


class Decoder(srd.Decoder):
    api_version = 3
    id = 'tpm_tis_spi'
    name = 'TPM TIS 2.0 SPI'
    longname = 'Trusted Platform Module Interface (TIS 2.0) over Serial Peripheral Bus'
    desc = 'Trusted Platform Module Interface (TIS 2.0) over Serial Peripheral Bus'
    license = 'gplv3+'
    inputs = ['spi']
    outputs = ['tpm-tis']
    tags = ['TPM']
    annotations = tpm_tis_spi.ANNOTATIONS
    annotation_rows = (
        ('protocol', 'Protocol', (tpm_tis_spi.ANN_RW_LENGTH, tpm_tis_spi.ANN_ADDRESS, tpm_tis_spi.ANN_WAIT_STATE, tpm_tis_spi.ANN_DATA)),
        ('transactions', 'Transactions', (tpm_tis_spi.ANN_TRANSACTION,)),
        ('warnings', 'Warnings', (tpm_tis_spi.ANN_WARNING,)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

    def reset(self):
        self._decoder = None

    def _reset_decoder(self):
        self._decoder = iter(tpm_tis_spi.decoder(self.out_ann, self.out_py))
        ann = self._decoder.send(None)
        while ann is not None:
            self.put(*ann)
            ann = self._decoder.send(None)

    def decode(self, ss, es, data):
        ptype, mosi, miso = data
        if ptype != 'DATA':
            return

        if self._decoder is None:
            self._reset_decoder()
        try:
            ann = self._decoder.send((ss, es, mosi, miso))
            while ann is not None:
                self.put(*ann)
                ann = self._decoder.send(None)
        except StopIteration:
            self._decoder = None
