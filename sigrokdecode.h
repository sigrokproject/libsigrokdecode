/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

#ifndef SIGROKDECODE_SIGROKDECODE_H
#define SIGROKDECODE_SIGROKDECODE_H

#include <Python.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <stdint.h>
#include <glib.h>

/*
 * Status/error codes returned by libsigrokdecode functions.
 *
 * All possible return codes of libsigrokdecode functions must be listed here.
 * Functions should never return hardcoded numbers as status, but rather
 * use these #defines instead. All error codes are negative numbers.
 *
 * The error codes are globally unique in libsigrokdecode, i.e. if one of the
 * libsigrokdecode functions returns a "malloc error" it must be exactly the
 * same return value as used by all other functions to indicate "malloc error".
 * There must be no functions which indicate two different errors via the
 * same return code.
 *
 * Also, for compatibility reasons, no defined return codes are ever removed
 * or reused for different #defines later. You can only add new #defines and
 * return codes, but never remove or redefine existing ones.
 */
#define SIGROKDECODE_OK			 0 /* No error */
#define SIGROKDECODE_ERR		-1 /* Generic/unspecified error */
#define SIGROKDECODE_ERR_MALLOC		-2 /* Malloc/calloc/realloc error */
#define SIGROKDECODE_ERR_ARGS		-3 /* Function argument error */
#define SIGROKDECODE_ERR_PYTHON		-4 /* Python C API error */
#define SIGROKDECODE_ERR_DECODERS_DIR	-5 /* Protocol decoder path invalid */

/* The list of loaded protocol decoders. */
GSList *list_pds;

/* TODO: Documentation. */
struct sigrokdecode_decoder {
	char *id;
	char *name;
	char *desc;
	char *func;
	GSList *inputformats;
	GSList *outputformats;

	PyObject *py_mod;
	PyObject *py_func;
};

int sigrokdecode_init(void);
int sigrokdecode_load_decoder(const char *name, struct sigrokdecode_decoder **dec);
int sigrokdecode_run_decoder(struct sigrokdecode_decoder *dec,
			     uint8_t *inbuf, uint64_t inbuflen,
			     uint8_t **outbuf, uint64_t *outbuflen);
int sigrokdecode_shutdown(void);

#endif
