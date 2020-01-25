irmp4sigrok - minimal irmp distribution for easy integration as static or dynamic lib
-------------------------------------------------------------------------------------

Modfied version of frank meyers multi protocol infrared decoder 
  IRMP (--> https://www.mikrocontroller.net/articles/IRMP )


All relevant code is amalgated in a single source file along with an external libraray interface. 
Purpose is fast and more easy integration in sigrok decoder library.
Since in near future a irmp2 wih a clearer design that is expected, not that much efford was made to fix the shortcommings that IRMP currently has in non embedded environment:
 - no runtime configurablity
 - no thread safety.

The irmpconfig.h was not changed and can be replaced by any "standard" IRMP config file.
the delivered config provides a set of as many protocols as was possible without having interfering protocols active.
It also is configured to 20kHz sample rate because this is most likely divisable without remainder.


 
Usage: just compile the given c-file with visual studio or gcc

eg:
 md gcc86
 gcc -m32 -O3 -shared irmp4sigrok.c -o gcc86/irmp.dll 
 md gcc64
 gcc -m64 -O3 -shared irmp4sigrok.c -o gcc64/irmp.dll