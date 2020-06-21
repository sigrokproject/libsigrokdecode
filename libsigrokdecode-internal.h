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
 * along with this program; if not, see <http://www.gnu.org/licenses/>.
 */

#ifndef LIBSIGROKDECODE_LIBSIGROKDECODE_INTERNAL_H
#define LIBSIGROKDECODE_LIBSIGROKDECODE_INTERNAL_H

/* Use the stable ABI subset as per PEP 384. */
#define Py_LIMITED_API 0x03020000

#include <Python.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode.h"

enum {
	SRD_TERM_ALWAYS_FALSE,
	SRD_TERM_HIGH,
	SRD_TERM_LOW,
	SRD_TERM_RISING_EDGE,
	SRD_TERM_FALLING_EDGE,
	SRD_TERM_EITHER_EDGE,
	SRD_TERM_NO_EDGE,
	SRD_TERM_SKIP,
};

struct srd_term {
	int type;
	int channel;
	uint64_t num_samples_to_skip;
	uint64_t num_samples_already_skipped;
};

/* Custom Python types: */

typedef struct {
	PyObject_HEAD
	struct srd_decoder_inst *di;
	uint64_t abs_start_samplenum;
	unsigned int itercnt;
	uint8_t *inbuf;
	uint64_t inbuflen;
	PyObject *sample;
} srd_logic;

struct srd_session {
	int session_id;

	/* List of decoder instances. */
	GSList *di_list;

	/* List of frontend callbacks to receive decoder output. */
	GSList *callbacks;
};

/* srd.c */
SRD_PRIV int srd_decoder_searchpath_add(const char *path);

/* session.c */
SRD_PRIV struct srd_pd_callback *srd_pd_output_callback_find(struct srd_session *sess,
		int output_type);

/* instance.c */
SRD_PRIV int srd_inst_start(struct srd_decoder_inst *di);
SRD_PRIV void match_array_free(struct srd_decoder_inst *di);
SRD_PRIV void condition_list_free(struct srd_decoder_inst *di);
SRD_PRIV int srd_inst_decode(struct srd_decoder_inst *di,
		uint64_t abs_start_samplenum, uint64_t abs_end_samplenum,
		const uint8_t *inbuf, uint64_t inbuflen, uint64_t unitsize);
SRD_PRIV int process_samples_until_condition_match(struct srd_decoder_inst *di, gboolean *found_match);
SRD_PRIV int srd_inst_flush(struct srd_decoder_inst *di);
SRD_PRIV int srd_inst_terminate_reset(struct srd_decoder_inst *di);
SRD_PRIV void srd_inst_free(struct srd_decoder_inst *di);
SRD_PRIV void srd_inst_free_all(struct srd_session *sess);

/* log.c */
#if defined(G_OS_WIN32) && (__GNUC__ > 4 || (__GNUC__ == 4 && __GNUC_MINOR__ >= 4))
/*
 * On MinGW, we need to specify the gnu_printf format flavor or GCC
 * will assume non-standard Microsoft printf syntax.
 */
SRD_PRIV int srd_log(int loglevel, const char *format, ...)
		__attribute__((__format__ (__gnu_printf__, 2, 3)));
#else
SRD_PRIV int srd_log(int loglevel, const char *format, ...) G_GNUC_PRINTF(2, 3);
#endif

#define srd_spew(...)	srd_log(SRD_LOG_SPEW, __VA_ARGS__)
#define srd_dbg(...)	srd_log(SRD_LOG_DBG,  __VA_ARGS__)
#define srd_info(...)	srd_log(SRD_LOG_INFO, __VA_ARGS__)
#define srd_warn(...)	srd_log(SRD_LOG_WARN, __VA_ARGS__)
#define srd_err(...)	srd_log(SRD_LOG_ERR,  __VA_ARGS__)

/* decoder.c */
SRD_PRIV long srd_decoder_apiver(const struct srd_decoder *d);

/* type_decoder.c */
SRD_PRIV PyObject *srd_Decoder_type_new(void);
SRD_PRIV const char *output_type_name(unsigned int idx);

/* type_logic.c */
SRD_PRIV PyObject *srd_logic_type_new(void);

/* module_sigrokdecode.c */
PyMODINIT_FUNC PyInit_sigrokdecode(void);

/* util.c */
SRD_PRIV PyObject *py_import_by_name(const char *name);
SRD_PRIV int py_attr_as_str(PyObject *py_obj, const char *attr, char **outstr);
SRD_PRIV int py_attr_as_strlist(PyObject *py_obj, const char *attr, GSList **outstrlist);
SRD_PRIV int py_dictitem_as_str(PyObject *py_obj, const char *key, char **outstr);
SRD_PRIV int py_listitem_as_str(PyObject *py_obj, Py_ssize_t idx, char **outstr);
SRD_PRIV int py_pydictitem_as_str(PyObject *py_obj, PyObject *py_key, char **outstr);
SRD_PRIV int py_pydictitem_as_long(PyObject *py_obj, PyObject *py_key, int64_t *out);
SRD_PRIV int py_str_as_str(PyObject *py_str, char **outstr);
SRD_PRIV int py_strseq_to_char(PyObject *py_strseq, char ***out_strv);
SRD_PRIV GVariant *py_obj_to_variant(PyObject *py_obj);

/* exception.c */
#if defined(G_OS_WIN32) && (__GNUC__ > 4 || (__GNUC__ == 4 && __GNUC_MINOR__ >= 4))
/*
 * On MinGW, we need to specify the gnu_printf format flavor or GCC
 * will assume non-standard Microsoft printf syntax.
 */
SRD_PRIV void srd_exception_catch(const char *format, ...)
		__attribute__((__format__ (__gnu_printf__, 1, 2)));
#else
SRD_PRIV void srd_exception_catch(const char *format, ...) G_GNUC_PRINTF(1, 2);
#endif

#endif
