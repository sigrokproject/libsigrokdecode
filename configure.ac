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

AC_PREREQ(2.61)

# TODO: Should be libsigrokdecode, not sigrok.
m4_define([sigrok_major_version], [0])
m4_define([sigrok_minor_version], [2])
m4_define([sigrok_micro_version], [0])
m4_define([sigrok_version],
	  [sigrok_major_version.sigrok_minor_version.sigrok_micro_version])

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

# Library version for libsigrokdecode.
# Carefully read the libtool docs before updating these numbers!
# The algorithm for determining which number to change (and how) is nontrivial!
# http://www.gnu.org/software/libtool/manual/libtool.html#Updating-version-info
SIGROKDECODE_LT_CURRENT=0
SIGROKDECODE_LT_REVISION=0
SIGROKDECODE_LT_AGE=0
SIGROKDECODE_LT_VERSION="$SIGROKDECODE_LT_CURRENT:$SIGROKDECODE_LT_REVISION:$SIGROKDECODE_LT_AGE"
SIGROKDECODE_LT_LDFLAGS="-version-info $SIGROKDECODE_LT_VERSION"
AC_SUBST(SIGROKDECODE_LT_LDFLAGS)

# Checks for libraries.

# libglib-2.0 is always needed.
# Note: glib-2.0 is part of the libsigrokdecode API
# (hard pkg-config requirement).
AM_PATH_GLIB_2_0([2.22.0],
        [CFLAGS="$CFLAGS $GLIB_CFLAGS"; LIBS="$LIBS $GLIB_LIBS"])

# Python support. We require at least Python >= 3.0.
CPPFLAGS_PYTHON=""
LDFLAGS_PYTHON=""
case "$build" in
*linux*)
	# We know that Linux has 'python3-config'.
	CPPFLAGS_PYTHON="$(python3-config --includes)"
	LDFLAGS_PYTHON="$(python3-config --ldflags)"
	;;
*darwin*)
	# On Darwin, Macports has python3.x-config, fink has python3-config.
	# Mac OS X (Snow Leopard) ships with 'python-config' per default, but
	# that's Python 2.x, so not useful for us.
	if test -x python3-config; then
		# python3-config exists, use it.
		CPPFLAGS_PYTHON="$(python3-config --includes)"
		LDFLAGS_PYTHON="$(python3-config --ldflags)"
	else
		# No python3-config found, so try hardcoded python3.2-config.
		CPPFLAGS_PYTHON="$(python3.2-config --includes)"
		LDFLAGS_PYTHON="$(python3.2-config --ldflags)"
	fi
	;;
*mingw*)
	# We currently hardcode the paths to the Python 3.2 default install
	# location as there's no 'python-config' script on Windows, it seems.
	CPPFLAGS_PYTHON="-I/c/Python32/include"
	LDFLAGS_PYTHON="-L/c/Python32/libs -lpython32"
	;;
*)
	# Everything else is untested, we just hope 'python3-config' works.
	CPPFLAGS_PYTHON="$(python3-config --includes)"
	LDFLAGS_PYTHON="$(python3-config --ldflags)"
	;;
esac
AC_SUBST(CPPFLAGS_PYTHON)
AC_SUBST(LDFLAGS_PYTHON)

# Checks for header files.
# These are already checked: inttypes.h stdint.h stdlib.h string.h unistd.h.
AC_CHECK_HEADERS([fcntl.h sys/time.h termios.h])

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
AC_CHECK_FUNCS([gettimeofday memset strchr strcspn strdup strerror strncasecmp strstr strtol strtoul strtoull])

AC_SUBST(DECODERS_DIR, "$datadir/libsigrokdecode/decoders")
AC_SUBST(MAKEFLAGS, '--no-print-directory')
AC_SUBST(AM_LIBTOOLFLAGS, '--silent')

SIGROK_MAJOR_VERSION=sigrok_major_version
SIGROK_MINOR_VERSION=sigrok_minor_version
SIGROK_MICRO_VERSION=sigrok_micro_version
SIGROK_VERSION=sigrok_version

AC_SUBST(SIGROK_MAJOR_VERSION)
AC_SUBST(SIGROK_MINOR_VERSION)
AC_SUBST(SIGROK_MICRO_VERSION)
AC_SUBST(SIGROK_VERSION)

AC_DEFINE(SIGROK_MAJOR_VERSION, [sigrok_major_version],
	  [Define to the sigrok major version])
AC_DEFINE(SIGROK_MINOR_VERSION, [sigrok_minor_version],
	  [Define to the sigrok minor version])
AC_DEFINE(SIGROK_MICRO_VERSION, [sigrok_micro_version],
	  [Define to the sigrok micro version])
AC_DEFINE(SIGROK_VERSION, [sigrok_version],
	  [Define to the sigrok version])

AC_CONFIG_FILES([Makefile
		 libsigrokdecode.pc
		 decoders/Makefile
		])

AC_OUTPUT

