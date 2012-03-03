/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

#ifndef LIBSIGROKDECODE_SIGROKDECODE_H
#define LIBSIGROKDECODE_SIGROKDECODE_H

#include <Python.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <stdint.h>
#include <glib.h>

#ifdef __cplusplus
extern "C" {
#endif

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
#define SRD_OK                 0 /**< No error */
#define SRD_ERR               -1 /**< Generic/unspecified error */
#define SRD_ERR_MALLOC        -2 /**< Malloc/calloc/realloc error */
#define SRD_ERR_ARG           -3 /**< Function argument error */
#define SRD_ERR_BUG           -4 /**< Errors hinting at internal bugs */
#define SRD_ERR_PYTHON        -5 /**< Python C API error */
#define SRD_ERR_DECODERS_DIR  -6 /**< Protocol decoder path invalid */

/* libsigrokdecode loglevels. */
#define SRD_LOG_NONE   0 /**< Output no messages at all. */
#define SRD_LOG_ERR    1 /**< Output error messages. */
#define SRD_LOG_WARN   2 /**< Output warnings. */
#define SRD_LOG_INFO   3 /**< Output informational messages. */
#define SRD_LOG_DBG    4 /**< Output debug messages. */
#define SRD_LOG_SPEW   5 /**< Output very noisy debug messages. */

/*
 * Use SRD_API to mark public API symbols, and SRD_PRIV for private symbols.
 *
 * Variables and functions marked 'static' are private already and don't
 * need SR_PRIV. However, functions which are not static (because they need
 * to be used in other libsigrokdecode-internal files) but are also not
 * meant to be part of the public libsigrokdecode API, must use SRD_PRIV.
 *
 * This uses the 'visibility' feature of gcc (requires gcc >= 4.0).
 *
 * Details: http://gcc.gnu.org/wiki/Visibility
 */

/* Marks public libsigrokdecode API symbols. */
#define SRD_API __attribute__((visibility("default")))

/* Marks private, non-public libsigrokdecode symbols (not part of the API). */
#define SRD_PRIV __attribute__((visibility("hidden")))

/*
 * When adding an output type, don't forget to...
 *   - expose it to PDs in controller.c:PyInit_sigrokdecode()
 *   - add a check in module_sigrokdecode.c:Decoder_put()
 *   - add a debug string in type_decoder.c:OUTPUT_TYPES
 */
enum {
	SRD_OUTPUT_ANN,
	SRD_OUTPUT_PROTO,
	SRD_OUTPUT_BINARY,
};

#define SRD_MAX_NUM_PROBES 64

/* TODO: Documentation. */
struct srd_decoder {
	/** The decoder ID. Must be non-NULL and unique for all decoders. */
	char *id;

	/** The (short) decoder name. */
	char *name;

	/** The (long) decoder name. May be NULL. */
	char *longname;

	/** A (short, one-line) description of the decoder. */
	char *desc;

	/** The license of the decoder. Valid values: "gplv2+", "gplv3+". */
	char *license;

	/** TODO */
	GSList *inputformats;

	/** TODO */
	GSList *outputformats;

	/** Probes */
	GSList *probes;

	/** Optional probes */
	GSList *opt_probes;

	/*
	 * List of NULL-terminated char[], containing descriptions of the
	 * supported annotation output.
	 */
	GSList *annotations;

	/** Python module */
	PyObject *py_mod;

	/** sigrokdecode.Decoder class */
	PyObject *py_dec;
};

struct srd_probe {
	char *id;
	char *name;
	char *desc;
	int order;
};

struct srd_decoder_inst {
	struct srd_decoder *decoder;
	PyObject *py_inst;
	char *inst_id;
	GSList *pd_output;
	int dec_num_probes;
	int *dec_probemap;
	int data_num_probes;
	int data_unitsize;
	uint64_t data_samplerate;
	GSList *next_di;
};

struct srd_pd_output {
	int pdo_id;
	int output_type;
	struct srd_decoder_inst *di;
	char *proto_id;
};

struct srd_proto_data {
	uint64_t start_sample;
	uint64_t end_sample;
	struct srd_pd_output *pdo;
	int ann_format;
	void *data;
};

typedef void (*srd_pd_output_callback_t)(struct srd_proto_data *pdata,
					 void *cb_data);

struct srd_pd_callback {
	int output_type;
	srd_pd_output_callback_t cb;
	void *cb_data;
};

/* custom python types */
typedef struct {
	PyObject_HEAD
} srd_Decoder;

typedef struct {
	PyObject_HEAD
	struct srd_decoder_inst *di;
	uint64_t start_samplenum;
	unsigned int itercnt;
	uint8_t *inbuf;
	uint64_t inbuflen;
	PyObject *sample;
} srd_logic;

/*--- controller.c ----------------------------------------------------------*/

SRD_API int srd_init(char *path);
SRD_API int srd_exit(void);
SRD_API int srd_inst_options_set(struct srd_decoder_inst *di,
				     GHashTable *options);
SRD_API int srd_inst_probes_set(struct srd_decoder_inst *di,
				    GHashTable *probes);
SRD_API struct srd_decoder_inst *srd_inst_new(const char *id,
						      GHashTable *options);
SRD_API int srd_inst_stack(struct srd_decoder_inst *di_from,
			       struct srd_decoder_inst *di_to);
SRD_API struct srd_decoder_inst *srd_inst_find_by_id(char *inst_id);
SRD_API int srd_session_start(int num_probes, int unitsize,
			      uint64_t samplerate);
SRD_API int srd_session_feed(uint64_t start_samplenum, uint8_t *inbuf,
			     uint64_t inbuflen);
SRD_API int srd_register_callback(int output_type,
				  srd_pd_output_callback_t cb, void *cb_data);

/*--- decoder.c -------------------------------------------------------------*/

SRD_API GSList *srd_decoders_list(void);
SRD_API struct srd_decoder *srd_decoder_get_by_id(const char *id);
SRD_API int srd_decoder_load(const char *name);
SRD_API int srd_decoder_unload(struct srd_decoder *dec);
SRD_API int srd_decoders_load_all(void);
SRD_API int srd_decoders_unload_all(void);
SRD_API char *srd_decoder_doc(struct srd_decoder *dec);

/*--- log.c -----------------------------------------------------------------*/

typedef int (*srd_log_callback_t)(void *cb_data, int loglevel,
				  const char *format, va_list args);

SRD_API int srd_log_loglevel_set(int loglevel);
SRD_API int srd_log_loglevel_get(void);
SRD_API int srd_log_callback_set(srd_log_callback_t cb, void *cb_data);
SRD_API int srd_log_callback_set_default(void);
SRD_API int srd_log_logdomain_set(const char *logdomain);
SRD_API char *srd_log_logdomain_get(void);

#ifdef __cplusplus
}
#endif

#endif
