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

import sigrokdecode as srd

from . import tpm_fifo_tis


def _finish_annotations(annotations):
    '''Depending on the amount of data read/written, sometimes the data-less formats (e.g. 'write 11 bytes') end up longer than the ones with data ('write 1234').
    In those cases, we remove them, because if we have the space to show the data, and now have sigrok pick the longer but less informative string.
    Assume :param annotations: is sorted by preference, and throw out any longer annotations following shorter ones.'''
    finished = [annotations[0]]
    for ann in annotations[1:]:
        if len(ann) < len(finished[-1]):
            finished.append(ann)
    return finished


class Decoder(srd.Decoder):
    api_version = 3
    id = 'tpm_fifo_tis'
    name = 'TPM FIFO'
    longname = 'Trusted Platform Module Commands over TIS 2.0 interface'
    desc = 'Trusted Platform Module Commands over TIS 2.0 interface'
    license = 'gplv3+'
    inputs = ['tpm-tis']
    outputs = ['tpm']
    tags = ['TPM']
    annotations = tpm_fifo_tis.ANNOTATIONS
    annotation_rows = (
        ('register', 'Register Transaction', (tpm_fifo_tis.ANN_REG_READ, tpm_fifo_tis.ANN_REG_WRITE)),
        ('tpm', 'TPM Command/Response', (tpm_fifo_tis.ANN_TPM_CMD, tpm_fifo_tis.ANN_TPM_RSP)),
        ('warnings', 'Warnings', (tpm_fifo_tis.ANN_WARN,)),
        ('states', 'TPM States', (tpm_fifo_tis.ANN_STATE,)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_py = self.register(srd.OUTPUT_PYTHON)

    def reset(self):
        self._decoder = None

    def _reset_decoder(self):
        self._decoder = iter(tpm_fifo_tis.decoder(self.out_ann, self.out_py))
        ann = self._decoder.send(None)
        while ann is not None:
            self.put(*ann)
            ann = self._decoder.send(None)

    def decode(self, ss, es, data):
        ptype, xfer = data
        if ptype != 'TRANSACTION':
            return

        if self._decoder is None:
            self._reset_decoder()
        try:
            ann = self._decoder.send((ss, es, xfer))
            while ann is not None:
                self.put(*ann)
                ann = self._decoder.send(None)
        except StopIteration:
            self._decoder = None
