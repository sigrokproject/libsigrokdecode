##
## This file is part of the libsigrokdecode project.
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

SUBDIRS = . contrib tests

lib_LTLIBRARIES = libsigrokdecode.la

libsigrokdecode_la_SOURCES = \
	srd.c \
	session.c \
	decoder.c \
	instance.c \
	log.c \
	util.c \
	exception.c \
	module_sigrokdecode.c \
	type_decoder.c \
	type_logic.c \
	error.c \
	version.c

libsigrokdecode_la_CPPFLAGS = $(CPPFLAGS_PYTHON) \
	-DDECODERS_DIR='"$(DECODERS_DIR)"'
libsigrokdecode_la_LDFLAGS = $(SRD_LIB_LDFLAGS) $(LDFLAGS_PYTHON)

library_includedir = $(includedir)/libsigrokdecode
library_include_HEADERS = libsigrokdecode.h version.h
noinst_HEADERS = libsigrokdecode-internal.h

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = libsigrokdecode.pc

EXTRA_DIST = Doxyfile

MAINTAINERCLEANFILES = ChangeLog

.PHONY: ChangeLog
ChangeLog:
	git --git-dir $(top_srcdir)/.git log > ChangeLog || touch ChangeLog

dist-hook: ChangeLog
	$(MKDIR_P) $(distdir)/tools
	cp tools/install-decoders $(distdir)/tools
	$(MKDIR_P) $(distdir)/decoders
	tools/install-decoders -o $(distdir)/decoders

install-decoders:
	$(MKDIR_P) $(DESTDIR)$(DECODERS_DIR)
	tools/install-decoders -o $(DESTDIR)$(DECODERS_DIR)

install-data-hook: install-decoders

