##
## This file is part of the sigrok project.
##
## Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

ACLOCAL_AMFLAGS = -I autostuff

SUBDIRS = decoders

lib_LTLIBRARIES = libsigrokdecode.la

libsigrokdecode_la_SOURCES = controller.c decoder.c log.c util.c exception.c \
	module_sigrokdecode.c type_decoder.c type_logic.c version.c

libsigrokdecode_la_CPPFLAGS = $(CPPFLAGS_PYTHON) \
			      -DDECODERS_DIR='"$(DECODERS_DIR)"'
libsigrokdecode_la_LDFLAGS = $(SRD_LIB_LDFLAGS) $(LDFLAGS_PYTHON)

include_HEADERS = sigrokdecode.h
noinst_HEADERS = sigrokdecode-internal.h

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = libsigrokdecode.pc

EXTRA_DIST = Doxyfile

MAINTAINERCLEANFILES = ChangeLog

.PHONY: ChangeLog
ChangeLog:
	git --git-dir $(top_srcdir)/../.git log > ChangeLog || touch ChangeLog

dist-hook: ChangeLog

