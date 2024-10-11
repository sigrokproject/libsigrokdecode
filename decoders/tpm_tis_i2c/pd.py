#
# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2020-2021 Tobias Peter <tobias.peter@infineon.com>
# Copyright (C) 2022 Johannes Holland <johannes.holland@infineon.com>
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
Decode the TPM TIS transactions contained in an I2C signal.
References: [tis] TCG PC Client Platform TPM Profile (PTP) Specification https://trustedcomputinggroup.org/wp-content/uploads/PC-Client-Specific-Platform-TPM-Profile-for-TPM-2p0-v1p05p_r14_pub.pdf
'''

import sigrokdecode as srd

from . import tpm_tis_i2c


class Decoder(srd.Decoder):
    api_version = 3
    id = 'tpm_tis_i2c'
    name = 'TPM TIS 2.0 I2C'
    longname = 'Trusted Platform Module Interface (TIS 2.0) over Inter-Integrated Circuit Bus'
    desc = 'Trusted Platform Module Interface (TIS 2.0) over Inter-Integrated Circuit Bus'
    license = 'gplv3+'
    inputs = ['i2c']
    outputs = ['tpm-tis']
    tags = ['TPM']
    annotations = tpm_tis_i2c.ANNOTATIONS
    annotation_rows = (
        ('protocol', 'Protocol', (tpm_tis_i2c.ANN_ADDRESS, tpm_tis_i2c.ANN_DATA_READ, tpm_tis_i2c.ANN_DATA_WRITE)),
        ('transactions', 'Transactions', (tpm_tis_i2c.ANN_TRANSACTION,)),
        ('warnings', 'Warnings', (tpm_tis_i2c.ANN_WARNING,)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

    def reset(self):
        self._decoder = None

    def _reset_decoder(self):
        self._decoder = tpm_tis_i2c.decoder(self.out_ann, self.out_py)
        ann = self._decoder.send(None)
        while ann is not None:
            self.put(*ann)
            ann = self._decoder.send(None)

    def decode(self, ss, es, data):
        ptype, pdata = data
        if ptype == 'BITS':
            return

        if self._decoder is None:
            self._reset_decoder()
        try:
            ann = self._decoder.send((ss, es, ptype, pdata))
            while ann is not None:
                self.put(*ann)
                ann = self._decoder.send(None)
        except (StopIteration, ValueError):
            self._decoder = None
