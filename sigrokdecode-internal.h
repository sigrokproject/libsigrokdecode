/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2011 Uwe Hermann <uwe@hermann-uwe.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
 */

#ifndef LIBSIGROKDECODE_SIGROKDECODE_INTERNAL_H
#define LIBSIGROKDECODE_SIGROKDECODE_INTERNAL_H

#include "sigrokdecode.h"
// #include <stdarg.h>
// #include <glib.h>

/*--- Macros ----------------------------------------------------------------*/

#ifndef ARRAY_SIZE
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#endif

#ifndef ARRAY_AND_SIZE
#define ARRAY_AND_SIZE(a) (a), ARRAY_SIZE(a)
#endif

/*--- controller.c ----------------------------------------------------------*/

SRD_PRIV int pd_add(struct srd_decoder_inst *di, int output_type,
		    char *output_id);

/*--- exception.c -----------------------------------------------------------*/

SRD_PRIV void catch_exception(const char *format, ...);

/*--- log.c -----------------------------------------------------------------*/

SRD_PRIV int srd_log(int loglevel, const char *format, ...);
SRD_PRIV int srd_spew(const char *format, ...);
SRD_PRIV int srd_dbg(const char *format, ...);
SRD_PRIV int srd_info(const char *format, ...);
SRD_PRIV int srd_warn(const char *format, ...);
SRD_PRIV int srd_err(const char *format, ...);

/*--- util.c ----------------------------------------------------------------*/

SRD_PRIV int py_attr_as_str(PyObject *py_obj, const char *attr, char **outstr);
SRD_PRIV int py_dictitem_as_str(PyObject *py_obj, const char *key, char **outstr);
SRD_PRIV int py_str_as_str(PyObject *py_str, char **outstr);
SRD_PRIV int py_strlist_to_char(PyObject *py_strlist, char ***outstr);

#endif
