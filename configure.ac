##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Bert Vermeulen <bert@biot.com>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

# We require at least autoconf 2.63 (AC_INIT format changed there).
AC_PREREQ([2.63])

# libsigrokdecode package version number (NOT the same as shared lib version!).
m4_define([srd_package_version_major], [0])
m4_define([srd_package_version_minor], [1])
m4_define([srd_package_version_micro], [0])
m4_define([srd_package_version], [srd_package_version_major.srd_package_version_minor.srd_package_version_micro])

AC_INIT([libsigrokdecode], [srd_package_version],
	[sigrok-devel@lists.sourceforge.net], [libsigrokdecode],
	[http://www.sigrok.org])
AC_CONFIG_HEADER([config.h])
AC_CONFIG_MACRO_DIR([autostuff])
AC_CONFIG_AUX_DIR([autostuff])

# We require at least automake 1.11 (needed for 'silent rules').
AM_INIT_AUTOMAKE([1.11 -Wall -Werror foreign std-options])
m4_ifdef([AM_SILENT_RULES], [AM_SILENT_RULES([yes])])
m4_ifdef([AM_PROG_AR], [AM_PROG_AR])

AH_TOP([#ifndef SRD_CONFIG_H
#define SRD_CONFIG_H    /* To stop multiple inclusions. */])
AH_BOTTOM([#endif /* SRD_CONFIG_H */])

CFLAGS="-g -Wall -Wextra"

# Checks for programs.
AC_PROG_CXX
AC_PROG_CC
AC_PROG_CPP
AC_PROG_INSTALL
AC_PROG_LN_S

# Initialize libtool.
LT_INIT

# Initialize pkg-config.
# We require at least 0.22, as "Requires.private" behaviour changed there.
PKG_PROG_PKG_CONFIG([0.22])

# Library version for libsigrokdecode (NOT the same as the package version).
# Carefully read the libtool docs before updating these numbers!
# The algorithm for determining which number to change (and how) is nontrivial!
# http://www.gnu.org/software/libtool/manual/libtool.html#Updating-version-info
SRD_LIB_VERSION_CURRENT=0
SRD_LIB_VERSION_REVISION=0
SRD_LIB_VERSION_AGE=0
SRD_LIB_VERSION="$SRD_LIB_VERSION_CURRENT:$SRD_LIB_VERSION_REVISION:$SRD_LIB_VERSION_AGE"
SRD_LIB_LDFLAGS="-version-info $SRD_LIB_VERSION"
AC_SUBST(SRD_LIB_VERSION_CURRENT)
AC_SUBST(SRD_LIB_VERSION_REVISION)
AC_SUBST(SRD_LIB_VERSION_AGE)
AC_SUBST(SRD_LIB_VERSION)
AC_SUBST(SRD_LIB_LDFLAGS)

# Checks for libraries.

# libglib-2.0 is always needed.
# Note: glib-2.0 is part of the libsigrokdecode API
# (hard pkg-config requirement).
AM_PATH_GLIB_2_0([2.28.0],
        [CFLAGS="$CFLAGS $GLIB_CFLAGS"; LIBS="$LIBS $GLIB_LIBS"])

# Python support. We require at least Python >= 3.0.
AC_ARG_VAR([PYTHON3_CONFIG], [path to python3-config utility])
AC_CHECK_PROGS([PYTHON3_CONFIG], [python3-config python3.2-config python3.1-config python3.0-config])
CPPFLAGS_PYTHON=""
LDFLAGS_PYTHON=""
case "$build" in
*mingw*)
	# We currently hardcode the paths to the Python 3.2 default install
	# location as there's no 'python-config' script on Windows, it seems.
	# Note: We add both the /c/ and c:/ syntax (needed for cmake).
	AC_MSG_WARN([using hardcoded Python3 configuration on MinGW])
	CPPFLAGS_PYTHON="-I/c/Python32/include -Ic:/Python32/include"
	LDFLAGS_PYTHON="-L/c/Python32/libs -Lc:/Python32/libs -lpython32"
	;;
*)
	# We know that Linux has 'python3-config'.
	# On Darwin, Macports has python3.x-config, fink has python3-config.
	# Mac OS X (Snow Leopard) ships with 'python-config' per default, but
	# that's Python 2.x, so not useful for us.
	# Everything else is untested, we just hope 'PYTHON3_CONFIG' works.
	if test -n "$PYTHON3_CONFIG"; then
		CPPFLAGS_PYTHON="$($PYTHON3_CONFIG --includes)"
		LDFLAGS_PYTHON="$($PYTHON3_CONFIG --ldflags)"
	else
		AC_MSG_ERROR([python3-config not found])
	fi
	;;
esac
AC_SUBST(CPPFLAGS_PYTHON)
AC_SUBST(LDFLAGS_PYTHON)

# Checks for header files.
# These are already checked: inttypes.h stdint.h stdlib.h string.h unistd.h.
# AC_CHECK_HEADERS([])

# Checks for typedefs, structures, and compiler characteristics.
AC_C_INLINE
AC_TYPE_INT8_T
AC_TYPE_INT16_T
AC_TYPE_INT32_T
AC_TYPE_INT64_T
AC_TYPE_UINT8_T
AC_TYPE_UINT16_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_SIZE_T

# Checks for library functions.
AC_CHECK_FUNCS([memset strtoull])

AC_SUBST(DECODERS_DIR, "$datadir/libsigrokdecode/decoders")
AC_SUBST(MAKEFLAGS, '--no-print-directory')
AC_SUBST(AM_LIBTOOLFLAGS, '--silent')

SRD_PACKAGE_VERSION_MAJOR=srd_package_version_major
SRD_PACKAGE_VERSION_MINOR=srd_package_version_minor
SRD_PACKAGE_VERSION_MICRO=srd_package_version_micro
SRD_PACKAGE_VERSION=srd_package_version

AC_SUBST(SRD_PACKAGE_VERSION_MAJOR)
AC_SUBST(SRD_PACKAGE_VERSION_MINOR)
AC_SUBST(SRD_PACKAGE_VERSION_MICRO)
AC_SUBST(SRD_PACKAGE_VERSION)

AC_CONFIG_FILES([Makefile
		 sigrokdecode.h
		 libsigrokdecode.pc
		 decoders/Makefile
		 decoders/avr_isp/Makefile
		 decoders/dcf77/Makefile
		 decoders/edid/Makefile
		 decoders/i2c/Makefile
		 decoders/i2cdemux/Makefile
		 decoders/i2cfilter/Makefile
		 decoders/i2s/Makefile
		 decoders/jtag/Makefile
		 decoders/jtag_stm32/Makefile
		 decoders/lm75/Makefile
		 decoders/lpc/Makefile
		 decoders/mlx90614/Makefile
		 decoders/mx25lxx05d/Makefile
		 decoders/mxc6225xu/Makefile
		 decoders/nunchuk/Makefile
		 decoders/pan1321/Makefile
		 decoders/rtc8564/Makefile
		 decoders/sdcard_spi/Makefile
		 decoders/spi/Makefile
		 decoders/transitioncounter/Makefile
		 decoders/uart/Makefile
		 decoders/uart_dump/Makefile
		 decoders/usb_signalling/Makefile
		 decoders/usb_protocol/Makefile
		 decoders/onewire_link/Makefile
		 decoders/onewire_network/Makefile
		 decoders/maxim_ds28ea00/Makefile
		])

AC_OUTPUT

echo
echo "libsigrokdecode configuration summary:"
echo
echo "  - Package version (major.minor.micro):    $SRD_PACKAGE_VERSION"
echo "  - Library version (current:revision:age): $SRD_LIB_VERSION"
echo "  - Prefix: $prefix"
echo
echo "Detected libraries:"
echo

# Note: This only works for libs with pkg-config integration.
for lib in "glib-2.0"; do
        if `$PKG_CONFIG --exists $lib`; then
                ver=`$PKG_CONFIG --modversion $lib`
                answer="yes ($ver)"
        else
                answer="no"
        fi
        echo "  - $lib: $answer"
done

echo
echo "Detected Python:"
echo
echo "  - Python CPPFLAGS: $CPPFLAGS_PYTHON"
echo "  - Python LDFLAGS: $LDFLAGS_PYTHON"
echo

