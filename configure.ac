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

AC_PREREQ([2.61])

# libsigrokdecode package version number (NOT the same as shared lib version!).
m4_define([libsigrokdecode_major_version], [0])
m4_define([libsigrokdecode_minor_version], [2])
m4_define([libsigrokdecode_micro_version], [0])
m4_define([libsigrokdecode_version],
	  [libsigrokdecode_major_version.libsigrokdecode_minor_version.libsigrokdecode_micro_version])

AC_INIT([libsigrokdecode], [libsigrokdecode_version],
	[sigrok-devel@lists.sourceforge.net], [libsigrokdecode],
	[http://www.sigrok.org])
AC_CONFIG_HEADER([config.h])
AC_CONFIG_MACRO_DIR([autostuff])
AC_CONFIG_AUX_DIR([autostuff])

AM_INIT_AUTOMAKE([-Wall -Werror foreign std-options])
m4_ifdef([AM_SILENT_RULES], [AM_SILENT_RULES([yes])])

AH_TOP([#ifndef LIBSIGROKDECODE_CONFIG_H
#define LIBSIGROKDECODE_CONFIG_H    /* To stop multiple inclusions. */])
AH_BOTTOM([#endif /* LIBSIGROKDECODE_CONFIG_H */])

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
LIBSIGROKDECODE_LT_CURRENT=0
LIBSIGROKDECODE_LT_REVISION=0
LIBSIGROKDECODE_LT_AGE=0
LIBSIGROKDECODE_LT_VERSION="$LIBSIGROKDECODE_LT_CURRENT:$LIBSIGROKDECODE_LT_REVISION:$LIBSIGROKDECODE_LT_AGE"
LIBSIGROKDECODE_LT_LDFLAGS="-version-info $LIBSIGROKDECODE_LT_VERSION"
AC_SUBST(LIBSIGROKDECODE_LT_LDFLAGS)

# Checks for libraries.

# libglib-2.0 is always needed.
# Note: glib-2.0 is part of the libsigrokdecode API
# (hard pkg-config requirement).
AM_PATH_GLIB_2_0([2.22.0],
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
	AC_MSG_WARN([using hardcoded Python3 configuration on MinGW])
	CPPFLAGS_PYTHON="-I/c/Python32/include"
	LDFLAGS_PYTHON="-L/c/Python32/libs -lpython32"
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

LIBSIGROKDECODE_MAJOR_VERSION=libsigrokdecode_major_version
LIBSIGROKDECODE_MINOR_VERSION=libsigrokdecode_minor_version
LIBSIGROKDECODE_MICRO_VERSION=libsigrokdecode_micro_version
LIBSIGROKDECODE_VERSION=libsigrokdecode_version

AC_SUBST(LIBSIGROKDECODE_MAJOR_VERSION)
AC_SUBST(LIBSIGROKDECODE_MINOR_VERSION)
AC_SUBST(LIBSIGROKDECODE_MICRO_VERSION)
AC_SUBST(LIBSIGROKDECODE_VERSION)

AC_DEFINE(LIBSIGROKDECODE_MAJOR_VERSION, [libsigrokdecode_major_version],
	  [Define to the libsigrokdecode major package version])
AC_DEFINE(LIBSIGROKDECODE_MINOR_VERSION, [libsigrokdecode_minor_version],
	  [Define to the libsigrokdecode minor package version])
AC_DEFINE(LIBSIGROKDECODE_MICRO_VERSION, [libsigrokdecode_micro_version],
	  [Define to the libsigrokdecode micro package version])
AC_DEFINE(LIBSIGROKDECODE_VERSION, [libsigrokdecode_version],
	  [Define to the libsigrokdecode package version])

AC_CONFIG_FILES([Makefile
		 libsigrokdecode.pc
		 decoders/Makefile
		 decoders/dcf77/Makefile
		 decoders/ddc/Makefile
		 decoders/ebr30a_i2c_demux/Makefile
		 decoders/i2c/Makefile
		 decoders/i2cdemux/Makefile
		 decoders/mlx90614/Makefile
		 decoders/mx25lxx05d/Makefile
		 decoders/nunchuk/Makefile
		 decoders/pan1321/Makefile
		 decoders/rtc8564/Makefile
		 decoders/spi/Makefile
		 decoders/transitioncounter/Makefile
		 decoders/uart/Makefile
		 decoders/usb/Makefile
		])

AC_OUTPUT

echo
echo "libsigrokdecode configuration summary:"
echo
echo "  - Package version (major.minor.micro):    $LIBSIGROKDECODE_VERSION"
echo "  - Library version (current:revision:age): $LIBSIGROKDECODE_LT_VERSION"
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

