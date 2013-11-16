/*
 * This file is part of the libsigrokdecode project.
 *
 * Copyright (C) 2011 Uwe Hermann <uwe@hermann-uwe.de>
 * Copyright (C) 2012 Bert Vermeulen <bert@biot.com>
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

#ifndef LIBSIGROKDECODE_LIBSIGROKDECODE_INTERNAL_H
#define LIBSIGROKDECODE_LIBSIGROKDECODE_INTERNAL_H

#include "libsigrokdecode.h"

struct srd_session {
	int session_id;

	/* List of decoder instances. */
	GSList *di_list;

	/* List of frontend callbacks to receive decoder output. */
	GSList *callbacks;
};

/*--- controller.c ----------------------------------------------------------*/

SRD_PRIV int srd_decoder_searchpath_add(const char *path);
SRD_PRIV struct srd_decoder_inst *srd_inst_find_by_obj( const GSList *stack,
		const PyObject *obj);
SRD_PRIV int srd_inst_start(struct srd_decoder_inst *di);
SRD_PRIV int srd_inst_decode(const struct srd_decoder_inst *di,
		uint64_t start_samplenum, uint64_t end_samplenum,
		const uint8_t *inbuf, uint64_t inbuflen);
SRD_PRIV void srd_inst_free(struct srd_decoder_inst *di);
SRD_PRIV void srd_inst_free_all(struct srd_session *sess, GSList *stack);
SRD_PRIV struct srd_pd_callback *srd_pd_output_callback_find(struct srd_session *sess,
		int output_type);

/*--- session.c -------------------------------------------------------------*/
SRD_PRIV int session_is_valid(struct srd_session *sess);

/*--- exception.c -----------------------------------------------------------*/

SRD_PRIV void srd_exception_catch(const char *format, ...);

/*--- log.c -----------------------------------------------------------------*/

SRD_PRIV int srd_log(int loglevel, const char *format, ...);
SRD_PRIV int srd_spew(const char *format, ...);
SRD_PRIV int srd_dbg(const char *format, ...);
SRD_PRIV int srd_info(const char *format, ...);
SRD_PRIV int srd_warn(const char *format, ...);
SRD_PRIV int srd_err(const char *format, ...);

/*--- util.c ----------------------------------------------------------------*/

SRD_PRIV int py_attr_as_str(const PyObject *py_obj, const char *attr,
			    char **outstr);
SRD_PRIV int py_dictitem_as_str(const PyObject *py_obj, const char *key,
				char **outstr);
SRD_PRIV int py_str_as_str(const PyObject *py_str, char **outstr);
SRD_PRIV int py_strlist_to_char(const PyObject *py_strlist, char ***outstr);

#endif
