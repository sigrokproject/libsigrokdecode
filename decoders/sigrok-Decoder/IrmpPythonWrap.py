


from ctypes import *
import platform

      

class IrmpWrap:
    class IrmpData(Structure):
         _fields_ = [  ("protocol"      , c_uint32 ),
                       ("protocolName"  , c_char_p ),
                       ("address"       , c_uint32 ),
                       ("command"       , c_uint32 ),
                       ("flags"         , c_uint32 ),
                       ("startSample"   , c_uint32 ),
                       ("endSample"     , c_uint32 ),
         ]
    
    def __init__(self):
        libname = "irmp.dll"
        # get the right filename

        if platform.uname()[0] == "Linux":
            name = "irmp.so"    
    
        self.__irmpDll = cdll.LoadLibrary("irmp.dll")
        self.__irmpDll.IRMP_GetSampleRate.restype = c_int32
        self.__irmpDll.IRMP_GetSampleRate.argtypes = []
        
        
        self.__irmpDll.IRMP_GetProtocolName.restype = c_char_p
        self.__irmpDll.IRMP_GetProtocolName.argtypes = [c_uint32]
        
        self.__irmpDll.IRMP_Reset.restype = None
        self.__irmpDll.IRMP_Reset.argtypes = []
        
        self.__irmpDll.IRMP_AddSample.restype = c_uint32
        self.__irmpDll.IRMP_AddSample.argtypes = [c_uint8]
        
        self.__irmpDll.IRMP_GetData.restype = c_uint32
        self.__irmpDll.IRMP_GetData.argtypes = [POINTER(IrmpWrap.IrmpData)]
        
        self.__irmpDll.IRMP_Detect.restype = IrmpWrap.IrmpData
        self.__irmpDll.IRMP_Detect.argtypes = [ c_char_p, c_uint32]
        
        self.__data = IrmpWrap.IrmpData()
        self.__startSample = c_uint32(0)
        self.__endSample   = c_uint32(0)

        return

    def GetProtocollName(self, pn):
        return self.__irmpDll.IRMP_GetProtocollName(pn)
    
    def GetSampleRate(self):
        return self.__irmpDll.IRMP_GetSampleRate()
    
    def Reset(self):
        self.__irmpDll.IRMP_Reset()
        
    def AddSample(self, level):
        
        if self.__irmpDll.IRMP_AddSample(c_uint8( 1 if (level!=0) else 0)):
            self.__irmpDll.IRMP_GetData( byref(self.__data))
            return True
        else:
            return False
        
    def GetData(self):
        return { 'data'  : { 
                             'protocol'     : self.__data.protocol,
                             'protocolName' : self.__data.protocolName.decode('UTF-8'),
                             'address'       : self.__data.address,
                             'command'       : self.__data.command,
                             'repeat'        : (self.__data.flags != 0)
                           }, 
                 'start' : self.__data.startSample,
                 'end'   : self.__data.endSample
               }

