##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2013 Uwe Hermann <uwe@hermann-uwe.de>
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
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

if HAVE_CHECK
TESTS = check_main
check_PROGRAMS = ${TESTS}
check_main_SOURCES = \
	$(top_builddir)/libsigrokdecode.h \
	check_main.c \
	check_core.c \
	check_decoder.c \
	check_inst.c \
	check_session.c
check_main_CFLAGS = @check_CFLAGS@
check_main_LDADD = $(top_builddir)/libsigrokdecode.la @check_LIBS@
check_main_CPPFLAGS = $(CPPFLAGS_PYTHON) \
	-DDECODERS_DIR='"$(abs_top_builddir)/decoders"'
endif

if BUILD_RUNTC
noinst_PROGRAMS = runtc
runtc_SOURCES = runtc.c
runtc_CPPFLAGS = $(CPPFLAGS_PYTHON) $(LIBSIGROK_CFLAGS) \
	-DDECODERS_DIR='"$(abs_top_builddir)/decoders"'
runtc_LDFLAGS = -L$(top_builddir) $(LIBSIGROK_LIBS) $(LDFLAGS_PYTHON) -lsigrokdecode
endif
