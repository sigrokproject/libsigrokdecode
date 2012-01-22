/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
 * Copyright (C) 2012 Bert Vermeulen <bert@biot.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "sigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "sigrokdecode-internal.h"
#include "config.h"
#include <glib.h>
#include <inttypes.h>
#include <stdlib.h>


/* List of decoder instances. */
static GSList *di_list = NULL;

/* List of frontend callbacks to receive PD output. */
static GSList *callbacks = NULL;

/* lives in decoder.c */
extern GSList *pd_list;

/* lives in module_sigrokdecode.c */
extern PyMODINIT_FUNC PyInit_sigrokdecode(void);

/* lives in type_logic.c */
extern PyTypeObject srd_logic_type;


/**
 * Initialize libsigrokdecode.
 *
 * This initializes the Python interpreter, and creates and initializes
 * a "sigrok" Python module with a single put() method.
 *
 * Then, it searches for sigrok protocol decoder files (*.py) in the
 * "decoders" subdirectory of the the sigrok installation directory.
 * All decoders that are found are loaded into memory and added to an
 * internal list of decoders, which can be queried via srd_list_decoders().
 *
 * The caller is responsible for calling the clean-up function srd_exit(),
 * which will properly shut down libsigrokdecode and free its allocated memory.
 *
 * Multiple calls to srd_init(), without calling srd_exit() in between,
 * are not allowed.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *         Upon Python errors, return SRD_ERR_PYTHON. If the sigrok decoders
 *         directory cannot be accessed, return SRD_ERR_DECODERS_DIR.
 *         If not enough memory could be allocated, return SRD_ERR_MALLOC.
 */
int srd_init(void)
{
	int ret;

	srd_dbg("srd: initializing");

	/* Add our own module to the list of built-in modules. */
	PyImport_AppendInittab("sigrokdecode", PyInit_sigrokdecode);

	/* Initialize the python interpreter. */
	Py_Initialize();

	if ((ret = set_modulepath()) != SRD_OK) {
		Py_Finalize();
		return ret;
	}

	if ((ret = srd_load_all_decoders()) != SRD_OK) {
		Py_Finalize();
		return ret;
	}

	return SRD_OK;
}


/**
 * Shutdown libsigrokdecode.
 *
 * This frees all the memory allocated for protocol decoders and shuts down
 * the Python interpreter.
 *
 * This function should only be called if there was a (successful!) invocation
 * of srd_init() before. Calling this function multiple times in a row, without
 * any successful srd_init() calls in between, is not allowed.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_exit(void)
{

	srd_dbg("srd: exiting");

	srd_unload_all_decoders();
	g_slist_free(pd_list);

	/* Py_Finalize() returns void, any finalization errors are ignored. */
	Py_Finalize();

	return SRD_OK;
}


/**
 * Add search directories for the protocol decoders.
 *
 * TODO: add path from env var SIGROKDECODE_PATH, config etc
 * TODO: Should take directoryname/path as input.
 */
int set_modulepath(void)
{
	int ret;
	gchar *path, *s;

#ifdef _WIN32
	gchar **splitted;

	/*
	 * On Windows/MinGW, Python's sys.path needs entries of the form
	 * 'C:\\foo\\bar' instead of '/foo/bar'.
	 */

	splitted = g_strsplit(DECODERS_DIR, "/", 0);
	path = g_build_pathv("\\\\", splitted);
	g_strfreev(splitted);
#else
	path = g_strdup(DECODERS_DIR);
#endif

	/* TODO: Prepend instead of appending. */
	/* TODO: Sanity check on 'path' (length, escape special chars, ...). */
	s = g_strdup_printf("import sys; sys.path.append(r'%s')", path);

	ret = PyRun_SimpleString(s);

	g_free(path);
	g_free(s);

	return ret;
}


/**
 * Set options in a decoder instance.
 *
 * @param di Decoder instance.
 * @param options A GHashTable of options to set.
 *
 * Handled options are removed from the hash.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_instance_set_options(struct srd_decoder_instance *di,
		GHashTable *options)
{
	PyObject *py_dec_options, *py_dec_optkeys, *py_di_options, *py_optval;
	PyObject *py_optlist, *py_classval;
	Py_UNICODE *py_ustr;
	unsigned long long int val_ull;
	int num_optkeys, ret, size, i;
	char *key, *value;

	if(!PyObject_HasAttrString(di->decoder->py_dec, "options")) {
		/* Decoder has no options. */
		if (g_hash_table_size(options) == 0) {
			/* No options provided. */
			return SRD_OK;
		} else {
			srd_err("Protocol decoder has no options.");
			return SRD_ERR_ARG;
		}
		return SRD_OK;
	}

	ret = SRD_ERR_PYTHON;
	key = NULL;
	py_dec_options = py_dec_optkeys = py_di_options = py_optval = NULL;
	py_optlist = py_classval = NULL;
	py_dec_options = PyObject_GetAttrString(di->decoder->py_dec, "options");

	/* All of these are synthesized objects, so they're good. */
	py_dec_optkeys = PyDict_Keys(py_dec_options);
	num_optkeys = PyList_Size(py_dec_optkeys);
	if (!(py_di_options = PyObject_GetAttrString(di->py_instance, "options")))
		goto err_out;
	for (i = 0; i < num_optkeys; i++) {
		/* Get the default class value for this option. */
		py_str_as_str(PyList_GetItem(py_dec_optkeys, i), &key);
		if (!(py_optlist = PyDict_GetItemString(py_dec_options, key)))
			goto err_out;
		if (!(py_classval = PyList_GetItem(py_optlist, 1)))
			goto err_out;
		if (!PyUnicode_Check(py_classval) && !PyLong_Check(py_classval)) {
			srd_err("Options of type %s are not yet supported.", Py_TYPE(py_classval)->tp_name);
			goto err_out;
		}

		if ((value = g_hash_table_lookup(options, key))) {
			/* An override for this option was provided. */
			if (PyUnicode_Check(py_classval)) {
				if (!(py_optval = PyUnicode_FromString(value))) {
					/* Some UTF-8 encoding error. */
					PyErr_Clear();
					goto err_out;
				}
			} else if (PyLong_Check(py_classval)) {
				if (!(py_optval = PyLong_FromString(value, NULL, 0))) {
					/* ValueError Exception */
					PyErr_Clear();
					srd_err("Option %s has invalid value %s: expected integer.",
							key, value);
					goto err_out;
				}
			}
			g_hash_table_remove(options, key);
		} else {
			/* Use the class default for this option. */
			if (PyUnicode_Check(py_classval)) {
				/* Make a brand new copy of the string. */
				py_ustr = PyUnicode_AS_UNICODE(py_classval);
				size = PyUnicode_GET_SIZE(py_classval);
				py_optval = PyUnicode_FromUnicode(py_ustr, size);
			} else if (PyLong_Check(py_classval)) {
				/* Make a brand new copy of the integer. */
				val_ull = PyLong_AsUnsignedLongLong(py_classval);
				if (val_ull == (unsigned long long)-1) {
					/* OverFlowError exception */
					PyErr_Clear();
					srd_err("Invalid integer value for %s: expected integer.", key);
					goto err_out;
				}
				if (!(py_optval = PyLong_FromUnsignedLongLong(val_ull)))
					goto err_out;
			}
		}

		/* If we got here, py_optval holds a known good new reference
		 * to the instance option to set.
		 */
		if (PyDict_SetItemString(py_di_options, key, py_optval) == -1)
			goto err_out;
	}

	ret = SRD_OK;

err_out:
	Py_XDECREF(py_optlist);
	Py_XDECREF(py_di_options);
	Py_XDECREF(py_dec_optkeys);
	Py_XDECREF(py_dec_options);
	if (key)
		g_free(key);
	if (PyErr_Occurred()) {
		srd_dbg("srd: stray exception!");
		PyErr_Print();
		PyErr_Clear();
	}

	return ret;
}

/* Helper GComparefunc for g_slist_find_custom() in srd_instance_set_probes() */
static gint compare_probe_id(struct srd_probe *a, char *probe_id)
{

	return strcmp(a->id, probe_id);
}

/**
 * Set probes in a decoder instance.
 *
 * @param di Decoder instance.
 * @param probes A GHashTable of probes to set. Key is probe name, value is
 * the probe number. Samples passed to this instance will be arranged in this
 * order.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_instance_set_probes(struct srd_decoder_instance *di,
		GHashTable *new_probes)
{
	GList *l;
	GSList *sl;
	struct srd_probe *p;
	int *new_probemap, new_probenum;
	char *probe_id;

	if (g_hash_table_size(new_probes) == 0)
		/* No probes provided. */
		return SRD_OK;

	if(di->dec_num_probes == 0) {
		/* Decoder has no probes. */
		srd_err("Protocol decoder %s has no probes to define.",
				di->decoder->name);
		return SRD_ERR_ARG;
	}

	new_probemap = NULL;

	if (!(new_probemap = g_try_malloc(sizeof(int) * di->dec_num_probes))) {
		srd_err("Failed to malloc new probe map.");
		return SRD_ERR_MALLOC;
	}

	for (l = g_hash_table_get_keys(new_probes); l; l = l->next) {
		probe_id = l->data;
		new_probenum = strtol(g_hash_table_lookup(new_probes, probe_id), NULL, 10);
		if (!(sl = g_slist_find_custom(di->decoder->probes, probe_id,
				(GCompareFunc)compare_probe_id))) {
			/* Fall back on optional probes. */
			if (!(sl = g_slist_find_custom(di->decoder->extra_probes,
					probe_id, (GCompareFunc)compare_probe_id))) {
				srd_err("Protocol decoder %s has no probe '%s'.",
						di->decoder->name, probe_id);
				g_free(new_probemap);
				return SRD_ERR_ARG;
			}
		}
		p = sl->data;
		new_probemap[p->order] = new_probenum;
	}
	g_free(di->dec_probemap);
	di->dec_probemap = new_probemap;

	return SRD_OK;
}

/**
 * Create a new protocol decoder instance.
 *
 * @param id Decoder 'id' field.
 * @param options GHashtable of options which override the defaults set in
 * 	    the decoder class.
 * @return Pointer to a newly allocated struct srd_decoder_instance, or
 * 		NULL in case of failure.
 */
struct srd_decoder_instance *srd_instance_new(const char *decoder_id,
		GHashTable *options)
{
	struct srd_decoder *dec;
	struct srd_decoder_instance *di;
	int i;
	char *instance_id;

	srd_dbg("srd: creating new %s instance", decoder_id);

	if (!(dec = srd_get_decoder_by_id(decoder_id))) {
		srd_err("Protocol decoder %s not found.", decoder_id);
		return NULL;
	}

	if (!(di = g_try_malloc0(sizeof(*di)))) {
		srd_err("Failed to malloc instance.");
		return NULL;
	}

	instance_id = g_hash_table_lookup(options, "id");
	di->decoder = dec;
	di->instance_id = g_strdup(instance_id ? instance_id : decoder_id);
	g_hash_table_remove(options, "id");

	/* Prepare a default probe map, where samples come in the
	 * order in which the decoder class defined them.
	 */
	di->dec_num_probes = g_slist_length(di->decoder->probes) +
			g_slist_length(di->decoder->extra_probes);
	if (di->dec_num_probes) {
		if (!(di->dec_probemap = g_try_malloc(sizeof(int) * di->dec_num_probes))) {
			srd_err("Failed to malloc probe map.");
			g_free(di);
			return NULL;
		}
		for (i = 0; i < di->dec_num_probes; i++)
			di->dec_probemap[i] = i;
	}

	/* Create a new instance of this decoder class. */
	if (!(di->py_instance = PyObject_CallObject(dec->py_dec, NULL))) {
		if (PyErr_Occurred())
			PyErr_Print();
		g_free(di->dec_probemap);
		g_free(di);
		return NULL;
	}

	if (srd_instance_set_options(di, options) != SRD_OK) {
		g_free(di->dec_probemap);
		g_free(di);
		return NULL;
	}

	/* Instance takes input from a frontend by default. */
	di_list = g_slist_append(di_list, di);

	return di;
}

int srd_instance_stack(struct srd_decoder_instance *di_from,
		struct srd_decoder_instance *di_to)
{

	if (!di_from || !di_to) {
		srd_err("Invalid from/to instance pair.");
		return SRD_ERR_ARG;
	}

	if (!g_slist_find(di_list, di_from)) {
		srd_err("Unstacked instance not found.");
		return SRD_ERR_ARG;
	}

	/* Remove from the unstacked list. */
	di_list = g_slist_remove(di_list, di_to);

	/* Stack on top of source di. */
	di_from->next_di = g_slist_append(di_from->next_di, di_to);

	return SRD_OK;
}


/* TODO: this should go into the PD stack */
struct srd_decoder_instance *srd_instance_find(char *instance_id)
{
	GSList *l;
	struct srd_decoder_instance *tmp, *di;

	di = NULL;
	for (l = di_list; l; l = l->next) {
		tmp = l->data;
		if (!strcmp(tmp->instance_id, instance_id)) {
			di = tmp;
			break;
		}
	}

	return di;
}

int srd_instance_start(struct srd_decoder_instance *di, PyObject *args)
{
	PyObject *py_name, *py_res;

	srd_dbg("srd: calling start() method on protocol decoder instance %s",
			di->instance_id);

	if (!(py_name = PyUnicode_FromString("start"))) {
		srd_err("Unable to build python object for 'start'.");
		if (PyErr_Occurred())
			PyErr_Print();
		return SRD_ERR_PYTHON;
	}

	if (!(py_res = PyObject_CallMethodObjArgs(di->py_instance,
			py_name, args, NULL))) {
		if (PyErr_Occurred())
			PyErr_Print();
		return SRD_ERR_PYTHON;
	}

	Py_DecRef(py_res);
	Py_DecRef(py_name);

	return SRD_OK;
}

/**
 * Run the specified decoder function.
 *
 * @param start_samplenum The starting sample number for the buffer's sample
 * 		set, relative to the start of capture.
 * @param di The decoder instance to call.
 * @param inbuf The buffer to decode.
 * @param inbuflen Length of the buffer.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_instance_decode(uint64_t start_samplenum,
		struct srd_decoder_instance *di, uint8_t *inbuf, uint64_t inbuflen)
{
	PyObject *py_res;
	srd_logic *logic;
	uint64_t end_samplenum;

	srd_dbg("srd: calling decode() on instance %s with %d bytes starting "
			"at sample %d", di->instance_id, inbuflen, start_samplenum);

	/* Return an error upon unusable input. */
	if (di == NULL) {
		srd_dbg("srd: empty decoder instance");
		return SRD_ERR_ARG;
	}
	if (inbuf == NULL) {
		srd_dbg("srd: NULL buffer pointer");
		return SRD_ERR_ARG;
	}
	if (inbuflen == 0) {
		srd_dbg("srd: empty buffer");
		return SRD_ERR_ARG;
	}

	/* Create new srd_logic object. Each iteration around the PD's loop
	 * will fill one sample into this object.
	 */
	logic = PyObject_New(srd_logic, &srd_logic_type);
	Py_INCREF(logic);
	logic->di = di;
	logic->start_samplenum = start_samplenum;
	logic->itercnt = 0;
	logic->inbuf = inbuf;
	logic->inbuflen = inbuflen;
	logic->sample = PyList_New(2);
	Py_INCREF(logic->sample);

	Py_IncRef(di->py_instance);
	end_samplenum = start_samplenum + inbuflen / di->data_unitsize;
	if (!(py_res = PyObject_CallMethod(di->py_instance, "decode",
			"KKO", logic->start_samplenum, end_samplenum, logic))) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */

		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}
	Py_DecRef(py_res);

	return SRD_OK;
}


int srd_session_start(int num_probes, int unitsize, uint64_t samplerate)
{
	PyObject *args;
	GSList *d, *s;
	struct srd_decoder_instance *di;
	int ret;

	srd_dbg("srd: calling start() on all instances with %d probes, "
			"unitsize %d samplerate %d", num_probes, unitsize, samplerate);

	/* Currently only one item of metadata is passed along to decoders,
	 * samplerate. This can be extended as needed.
	 */
	if (!(args = Py_BuildValue("{s:l}", "samplerate", (long)samplerate))) {
		srd_err("Unable to build python object for metadata.");
		return SRD_ERR_PYTHON;
	}

	/* Run the start() method on all decoders receiving frontend data. */
	for (d = di_list; d; d = d->next) {
		di = d->data;
		di->data_num_probes = num_probes;
		di->data_unitsize = unitsize;
		di->data_samplerate = samplerate;
		if ((ret = srd_instance_start(di, args) != SRD_OK))
			return ret;

		/* Run the start() method on all decoders up the stack from this one. */
		for (s = di->next_di; s; s = s->next) {
			/* These don't need probes, unitsize and samplerate. */
			di = s->data;
			if ((ret = srd_instance_start(di, args) != SRD_OK))
				return ret;
		}
	}

	Py_DecRef(args);

	return SRD_OK;
}

/* Feed logic samples to decoder session. */
int srd_session_feed(uint64_t start_samplenum, uint8_t *inbuf, uint64_t inbuflen)
{
	GSList *d;
	int ret;

	srd_dbg("srd: calling decode() on all instances with starting sample "
			"number %"PRIu64", %"PRIu64" bytes at 0x%p", start_samplenum,
			inbuflen, inbuf);

	for (d = di_list; d; d = d->next) {
		if ((ret = srd_instance_decode(start_samplenum, d->data, inbuf,
				inbuflen)) != SRD_OK)
			return ret;
	}

	return SRD_OK;
}


int srd_register_callback(int output_type, void *cb)
{
	struct srd_pd_callback *pd_cb;

	srd_dbg("srd: registering new callback for output type %d", output_type);

	if (!(pd_cb = g_try_malloc(sizeof(struct srd_pd_callback))))
		return SRD_ERR_MALLOC;

	pd_cb->output_type = output_type;
	pd_cb->callback = cb;
	callbacks = g_slist_append(callbacks, pd_cb);

	return SRD_OK;
}

void *srd_find_callback(int output_type)
{
	GSList *l;
	struct srd_pd_callback *pd_cb;
	void *(cb);

	cb = NULL;
	for (l = callbacks; l; l = l->next) {
		pd_cb = l->data;
		if (pd_cb->output_type == output_type) {
			cb = pd_cb->callback;
			break;
		}
	}

	return cb;
}


/* This is the backend function to python sigrokdecode.add() call. */
int pd_add(struct srd_decoder_instance *di, int output_type,
		char *proto_id)
{
	struct srd_pd_output *pdo;

	srd_dbg("srd: instance %s creating new output type %d for %s",
			di->instance_id, output_type, proto_id);

	if (!(pdo = g_try_malloc(sizeof(struct srd_pd_output))))
		return -1;

	/* pdo_id is just a simple index, nothing is deleted from this list anyway. */
	pdo->pdo_id = g_slist_length(di->pd_output);
	pdo->output_type = output_type;
	pdo->decoder = di->decoder;
	pdo->proto_id = g_strdup(proto_id);
	di->pd_output = g_slist_append(di->pd_output, pdo);

	return pdo->pdo_id;
}

struct srd_decoder_instance *get_di_by_decobject(void *decobject)
{
	GSList *l, *s;
	struct srd_decoder_instance *di;

	for (l = di_list; l; l = l->next) {
		di = l->data;
		if (decobject == di->py_instance)
			return di;
		/* Check decoders stacked on top of this one. */
		for (s = di->next_di; s; s = s->next) {
			di = s->data;
			if (decobject == di->py_instance)
				return di;
		}
	}

	return NULL;
}

