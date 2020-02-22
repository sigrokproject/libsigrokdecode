##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Rene Staffen
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

'''
Python binding for the IRMP library.
'''

import ctypes
import platform

class IrmpLibrary:
    '''
    Library instance for an infrared protocol detector.
    '''

    class ResultData(ctypes.Structure):
        _fields_ = [
            ( 'protocol', ctypes.c_uint32, ),
            ( 'protocol_name', ctypes.c_char_p, ),
            ( 'address', ctypes.c_uint32, ),
            ( 'command', ctypes.c_uint32, ),
            ( 'flags', ctypes.c_uint32, ),
            ( 'start_sample', ctypes.c_uint32, ),
            ( 'end_sample', ctypes.c_uint32, ),
        ]

    FLAG_REPETITION = 1 << 0

    def _library_filename(self):
        '''
        Determine the library filename depending on the platform.
        '''

        if platform.uname()[0] == 'Linux':
            return 'libirmp.so'
        # TODO Add support for more platforms.
        return 'irmp.dll'

    def __init__(self):
        '''
        Create a library instance.
        '''

        # Load the library. Lookup routines, declare their prototypes.
        filename = self._library_filename()
        self._lib = ctypes.cdll.LoadLibrary(filename)

        self._lib.irmp_get_sample_rate.restype = ctypes.c_uint32
        self._lib.irmp_get_sample_rate.argtypes = []

        self._lib.irmp_reset_state.restype = None
        self._lib.irmp_reset_state.argtypes = []

        self._lib.irmp_add_one_sample.restype = ctypes.c_int
        self._lib.irmp_add_one_sample.argtypes = [ ctypes.c_int, ]

        if False:
            self._lib.irmp_detect_buffer.restype = self.ResultData
            self._lib.irmp_detect_buffer.argtypes = [ ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, ]

        self._lib.irmp_get_result_data.restype = ctypes.c_int
        self._lib.irmp_get_result_data.argtypes = [ ctypes.POINTER(self.ResultData), ]

        self._lib.irmp_get_protocol_name.restype = ctypes.c_char_p
        self._lib.irmp_get_protocol_name.argtypes = [ ctypes.c_uint32, ]

        # Create a result buffer that's local to the library instance.
        self._data = self.ResultData()

    def get_sample_rate(self):
        return self._lib.irmp_get_sample_rate()

    def reset_state(self):
        self._lib.irmp_reset_state()

    def add_one_sample(self, level):
        if not self._lib.irmp_add_one_sample(int(level)):
            return False
        self._lib.irmp_get_result_data(ctypes.byref(self._data))
        return True

    def get_result_data(self):
        data = {
            'proto_nr': self._data.protocol,
            'proto_name': self._data.protocol_name.decode('UTF-8', 'ignore'),
            'address': self._data.address,
            'command': self._data.command,
            'repeat': bool(self._data.flags & self.FLAG_REPETITION),
            'start': self._data.start_sample,
            'end': self._data.end_sample,
        }
        return data
