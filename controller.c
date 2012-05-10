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

/* List of frontend callbacks to receive decoder output. */
static GSList *callbacks = NULL;

/* decoder.c */
extern SRD_PRIV GSList *pd_list;

/* module_sigrokdecode.c */
/* FIXME: SRD_PRIV causes issues on MinGW. Investigate. */
extern PyMODINIT_FUNC PyInit_sigrokdecode(void);

/* type_logic.c */
extern SRD_PRIV PyTypeObject srd_logic_type;

/**
 * Initialize libsigrokdecode.
 *
 * This initializes the Python interpreter, and creates and initializes
 * a "sigrokdecode" Python module.
 *
 * Then, it searches for sigrok protocol decoder files (*.py) in the
 * "decoders" subdirectory of the the sigrok installation directory.
 * All decoders that are found are loaded into memory and added to an
 * internal list of decoders, which can be queried via srd_decoders_list().
 *
 * The caller is responsible for calling the clean-up function srd_exit(),
 * which will properly shut down libsigrokdecode and free its allocated memory.
 *
 * Multiple calls to srd_init(), without calling srd_exit() in between,
 * are not allowed.
 *
 * @param path Path to an extra directory containing protocol decoders
 *             which will be added to the Python sys.path, or NULL.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *         Upon Python errors, return SRD_ERR_PYTHON. If the sigrok decoders
 *         directory cannot be accessed, return SRD_ERR_DECODERS_DIR.
 *         If not enough memory could be allocated, return SRD_ERR_MALLOC.
 */
SRD_API int srd_init(const char *path)
{
	int ret;
	char *env_path;

	srd_dbg("Initializing libsigrokdecode.");

	/* Add our own module to the list of built-in modules. */
	PyImport_AppendInittab("sigrokdecode", PyInit_sigrokdecode);

	/* Initialize the Python interpreter. */
	Py_Initialize();

	/* Installed decoders. */
	if ((ret = srd_decoder_searchpath_add(DECODERS_DIR)) != SRD_OK) {
		Py_Finalize();
		return ret;
	}

	/* Path specified by the user. */
	if (path) {
		if ((ret = srd_decoder_searchpath_add(path)) != SRD_OK) {
			Py_Finalize();
			return ret;
		}
	}

	/* Environment variable overrides everything, for debugging. */
	if ((env_path = getenv("SIGROKDECODE_DIR"))) {
		if ((ret = srd_decoder_searchpath_add(env_path)) != SRD_OK) {
			Py_Finalize();
			return ret;
		}
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
SRD_API int srd_exit(void)
{
	srd_dbg("Exiting libsigrokdecode.");

	srd_decoder_unload_all();
	g_slist_free(pd_list);
	pd_list = NULL;

	/* Py_Finalize() returns void, any finalization errors are ignored. */
	Py_Finalize();

	return SRD_OK;
}

/**
 * Add an additional search directory for the protocol decoders.
 *
 * The specified directory is prepended (not appended!) to Python's sys.path,
 * in order to search for sigrok protocol decoders in the specified
 * directories first, and in the generic Python module directories (and in
 * the current working directory) last. This avoids conflicts if there are
 * Python modules which have the same name as a sigrok protocol decoder in
 * sys.path or in the current working directory.
 *
 * @param path Path to the directory containing protocol decoders which shall
 *             be added to the Python sys.path, or NULL.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_PRIV int srd_decoder_searchpath_add(const char *path)
{
	PyObject *py_cur_path, *py_item;
	GString *new_path;
	int wc_len, i;
	wchar_t *wc_new_path;
	char *item;

	srd_dbg("Adding '%s' to module path.", path);

	new_path = g_string_sized_new(256);
	g_string_assign(new_path, g_strdup(path));
	py_cur_path = PySys_GetObject("path");
	for (i = 0; i < PyList_Size(py_cur_path); i++) {
		g_string_append(new_path, g_strdup(G_SEARCHPATH_SEPARATOR_S));
		py_item = PyList_GetItem(py_cur_path, i);
		if (!PyUnicode_Check(py_item))
			/* Shouldn't happen. */
			continue;
		if (py_str_as_str(py_item, &item) != SRD_OK)
			continue;
		g_string_append(new_path, item);
	}

	/* Convert to wide chars. */
	wc_len = sizeof(wchar_t) * (new_path->len + 1);
	if (!(wc_new_path = g_try_malloc(wc_len))) {
		srd_dbg("malloc failed");
		return SRD_ERR_MALLOC;
	}
	mbstowcs(wc_new_path, new_path->str, wc_len);
	PySys_SetPath(wc_new_path);
	g_string_free(new_path, TRUE);
	g_free(wc_new_path);

//#ifdef _WIN32
//	gchar **splitted;
//
//	/*
//	 * On Windows/MinGW, Python's sys.path needs entries of the form
//	 * 'C:\\foo\\bar' instead of '/foo/bar'.
//	 */
//
//	splitted = g_strsplit(DECODERS_DIR, "/", 0);
//	path = g_build_pathv("\\\\", splitted);
//	g_strfreev(splitted);
//#else
//	path = g_strdup(DECODERS_DIR);
//#endif

	return SRD_OK;
}

/**
 * Set one or more options in a decoder instance.
 *
 * Handled options are removed from the hash.
 *
 * @param di Decoder instance.
 * @param options A GHashTable of options to set.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_inst_option_set(struct srd_decoder_inst *di,
				GHashTable *options)
{
	PyObject *py_dec_options, *py_dec_optkeys, *py_di_options, *py_optval;
	PyObject *py_optlist, *py_classval;
	Py_UNICODE *py_ustr;
	unsigned long long int val_ull;
	int num_optkeys, ret, size, i;
	char *key, *value;

	if (!PyObject_HasAttrString(di->decoder->py_dec, "options")) {
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
	if (!(py_di_options = PyObject_GetAttrString(di->py_inst, "options")))
		goto err_out;
	for (i = 0; i < num_optkeys; i++) {
		/* Get the default class value for this option. */
		py_str_as_str(PyList_GetItem(py_dec_optkeys, i), &key);
		if (!(py_optlist = PyDict_GetItemString(py_dec_options, key)))
			goto err_out;
		if (!(py_classval = PyList_GetItem(py_optlist, 1)))
			goto err_out;
		if (!PyUnicode_Check(py_classval) && !PyLong_Check(py_classval)) {
			srd_err("Options of type %s are not yet supported.",
				Py_TYPE(py_classval)->tp_name);
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
					srd_err("Option %s has invalid value "
						"%s: expected integer.",
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
					srd_err("Invalid integer value for %s: "
						"expected integer.", key);
					goto err_out;
				}
				if (!(py_optval = PyLong_FromUnsignedLongLong(val_ull)))
					goto err_out;
			}
		}

		/*
		 * If we got here, py_optval holds a known good new reference
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
	g_free(key);
	if (PyErr_Occurred())
		srd_exception_catch("Stray exception in srd_inst_option_set().");

	return ret;
}

/* Helper GComparefunc for g_slist_find_custom() in srd_inst_probe_set_all() */
static gint compare_probe_id(const struct srd_probe *a, const char *probe_id)
{
	return strcmp(a->id, probe_id);
}

/**
 * Set all probes in a decoder instance.
 *
 * This function sets _all_ probes for the specified decoder instance, i.e.,
 * it overwrites any probes that were already defined (if any).
 *
 * @param di Decoder instance.
 * @param new_probes A GHashTable of probes to set. Key is probe name, value is
 *                   the probe number. Samples passed to this instance will be
 *                   arranged in this order.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_inst_probe_set_all(struct srd_decoder_inst *di,
			           GHashTable *new_probes)
{
	GList *l;
	GSList *sl;
	struct srd_probe *p;
	int *new_probemap, new_probenum;
	char *probe_id, *probenum_str;
	int i, num_required_probes;

	srd_dbg("set probes called for instance %s with list of %d probes",
		di->inst_id, g_hash_table_size(new_probes));

	if (g_hash_table_size(new_probes) == 0)
		/* No probes provided. */
		return SRD_OK;

	if (di->dec_num_probes == 0) {
		/* Decoder has no probes. */
		srd_err("Protocol decoder %s has no probes to define.",
			di->decoder->name);
		return SRD_ERR_ARG;
	}

	new_probemap = NULL;

	if (!(new_probemap = g_try_malloc(sizeof(int) * di->dec_num_probes))) {
		srd_err("Failed to g_malloc() new probe map.");
		return SRD_ERR_MALLOC;
	}

	/*
	 * For now, map all indexes to probe -1 (can be overridden later).
	 * This -1 is interpreted as an unspecified probe later.
	 */
	for (i = 0; i < di->dec_num_probes; i++)
		new_probemap[i] = -1;

	for (l = g_hash_table_get_keys(new_probes); l; l = l->next) {
		probe_id = l->data;
		probenum_str = g_hash_table_lookup(new_probes, probe_id);
		if (!probenum_str) {
			/* Probe name was specified without a value. */
			srd_err("No probe number was specified for %s.",
				probe_id);
			g_free(new_probemap);
			return SRD_ERR_ARG;
		}
		new_probenum = strtol(probenum_str, NULL, 10);
		if (!(sl = g_slist_find_custom(di->decoder->probes, probe_id,
				(GCompareFunc)compare_probe_id))) {
			/* Fall back on optional probes. */
			if (!(sl = g_slist_find_custom(di->decoder->opt_probes,
			     probe_id, (GCompareFunc) compare_probe_id))) {
				srd_err("Protocol decoder %s has no probe "
					"'%s'.", di->decoder->name, probe_id);
				g_free(new_probemap);
				return SRD_ERR_ARG;
			}
		}
		p = sl->data;
		new_probemap[p->order] = new_probenum;
		srd_dbg("Setting probe mapping: %s (index %d) = probe %d.",
			p->id, p->order, new_probenum);
	}

	srd_dbg("Final probe map:");
	num_required_probes = g_slist_length(di->decoder->probes);
	for (i = 0; i < di->dec_num_probes; i++) {
		srd_dbg(" - index %d = probe %d (%s)", i, new_probemap[i],
		        (i < num_required_probes) ? "required" : "optional");
	}

	g_free(di->dec_probemap);
	di->dec_probemap = new_probemap;

	return SRD_OK;
}

/**
 * Create a new protocol decoder instance.
 *
 * @param decoder_id Decoder 'id' field.
 * @param options GHashtable of options which override the defaults set in
 *                the decoder class.
 *
 * @return Pointer to a newly allocated struct srd_decoder_inst, or
 *         NULL in case of failure.
 */
SRD_API struct srd_decoder_inst *srd_inst_new(const char *decoder_id,
					      GHashTable *options)
{
	int i;
	struct srd_decoder *dec;
	struct srd_decoder_inst *di;
	char *inst_id;

	srd_dbg("Creating new %s instance.", decoder_id);

	if (!(dec = srd_decoder_get_by_id(decoder_id))) {
		srd_err("Protocol decoder %s not found.", decoder_id);
		return NULL;
	}

	if (!(di = g_try_malloc0(sizeof(struct srd_decoder_inst)))) {
		srd_err("Failed to g_malloc() instance.");
		return NULL;
	}

	inst_id = g_hash_table_lookup(options, "id");
	di->decoder = dec;
	di->inst_id = g_strdup(inst_id ? inst_id : decoder_id);
	g_hash_table_remove(options, "id");

	/*
	 * Prepare a default probe map, where samples come in the
	 * order in which the decoder class defined them.
	 */
	di->dec_num_probes = g_slist_length(di->decoder->probes) +
			     g_slist_length(di->decoder->opt_probes);
	if (di->dec_num_probes) {
		if (!(di->dec_probemap =
		     g_try_malloc(sizeof(int) * di->dec_num_probes))) {
			srd_err("Failed to g_malloc() probe map.");
			g_free(di);
			return NULL;
		}
		for (i = 0; i < di->dec_num_probes; i++)
			di->dec_probemap[i] = i;
	}

	/* Create a new instance of this decoder class. */
	if (!(di->py_inst = PyObject_CallObject(dec->py_dec, NULL))) {
		if (PyErr_Occurred())
			srd_exception_catch("failed to create %s instance: ",
					    decoder_id);
		g_free(di->dec_probemap);
		g_free(di);
		return NULL;
	}

	if (srd_inst_option_set(di, options) != SRD_OK) {
		g_free(di->dec_probemap);
		g_free(di);
		return NULL;
	}

	/* Instance takes input from a frontend by default. */
	di_list = g_slist_append(di_list, di);

	return di;
}

/**
 * Stack a decoder instance on top of another.
 *
 * @param di_from The instance to move.
 * @param di_to The instance on top of which di_from will be stacked.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_inst_stack(struct srd_decoder_inst *di_from,
			   struct srd_decoder_inst *di_to)
{
	if (!di_from || !di_to) {
		srd_err("Invalid from/to instance pair.");
		return SRD_ERR_ARG;
	}

	if (g_slist_find(di_list, di_to)) {
		/* Remove from the unstacked list. */
		di_list = g_slist_remove(di_list, di_to);
	}

	/* Stack on top of source di. */
	di_from->next_di = g_slist_append(di_from->next_di, di_to);

	return SRD_OK;
}

/**
 * Find a decoder instance by its instance ID.
 *
 * Only the bottom level of instances are searched -- instances already stacked
 * on top of another one will not be found.
 *
 * @param inst_id The instance ID to be found.
 *
 * @return Pointer to struct srd_decoder_inst, or NULL if not found.
 */
SRD_API struct srd_decoder_inst *srd_inst_find_by_id(const char *inst_id)
{
	GSList *l;
	struct srd_decoder_inst *tmp, *di;

	di = NULL;
	for (l = di_list; l; l = l->next) {
		tmp = l->data;
		if (!strcmp(tmp->inst_id, inst_id)) {
			di = tmp;
			break;
		}
	}

	return di;
}

/**
 * Find a decoder instance by its Python object.
 *
 * I.e. find that instance's instantiation of the sigrokdecode.Decoder class.
 * This will recurse to find the instance anywhere in the stack tree.
 *
 * @param stack Pointer to a GSList of struct srd_decoder_inst, indicating the
 *              stack to search. To start searching at the bottom level of
 *              decoder instances, pass NULL.
 * @param obj The Python class instantiation.
 *
 * @return Pointer to struct srd_decoder_inst, or NULL if not found.
 */
SRD_PRIV struct srd_decoder_inst *srd_inst_find_by_obj(const GSList *stack,
						       const PyObject *obj)
{
// TODO?
	const GSList *l;
	struct srd_decoder_inst *tmp, *di;

	di = NULL;
	for (l = stack ? stack : di_list; di == NULL && l != NULL; l = l->next) {
		tmp = l->data;
		if (tmp->py_inst == obj)
			di = tmp;
		else if (tmp->next_di)
			di = srd_inst_find_by_obj(tmp->next_di, obj);
	}

	return di;
}

SRD_PRIV int srd_inst_start(struct srd_decoder_inst *di, PyObject *args)
{
	PyObject *py_name, *py_res;
	GSList *l;
	struct srd_decoder_inst *next_di;

	srd_dbg("Calling start() method on protocol decoder instance %s.",
		di->inst_id);

	if (!(py_name = PyUnicode_FromString("start"))) {
		srd_err("Unable to build Python object for 'start'.");
		srd_exception_catch("Protocol decoder instance %s: ",
				    di->inst_id);
		return SRD_ERR_PYTHON;
	}

	if (!(py_res = PyObject_CallMethodObjArgs(di->py_inst,
						  py_name, args, NULL))) {
		srd_exception_catch("Protocol decoder instance %s: ",
				    di->inst_id);
		return SRD_ERR_PYTHON;
	}

	Py_DecRef(py_res);
	Py_DecRef(py_name);

	/*
	 * Start all the PDs stacked on top of this one. Pass along the
	 * metadata all the way from the bottom PD, even though it's only
	 * applicable to logic data for now.
	 */
	for (l = di->next_di; l; l = l->next) {
		next_di = l->data;
		srd_inst_start(next_di, args);
	}

	return SRD_OK;
}

/**
 * Run the specified decoder function.
 *
 * @param start_samplenum The starting sample number for the buffer's sample
 * 			  set, relative to the start of capture.
 * @param di The decoder instance to call. Must not be NULL.
 * @param inbuf The buffer to decode. Must not be NULL.
 * @param inbuflen Length of the buffer. Must be > 0.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_PRIV int srd_inst_decode(uint64_t start_samplenum,
			     const struct srd_decoder_inst *di,
			     const uint8_t *inbuf, uint64_t inbuflen)
{
	PyObject *py_res;
	srd_logic *logic;
	uint64_t end_samplenum;

	srd_dbg("Calling decode() on instance %s with %d bytes starting "
		"at sample %d.", di->inst_id, inbuflen, start_samplenum);

	/* Return an error upon unusable input. */
	if (!di) {
		srd_dbg("empty decoder instance");
		return SRD_ERR_ARG;
	}
	if (!inbuf) {
		srd_dbg("NULL buffer pointer");
		return SRD_ERR_ARG;
	}
	if (inbuflen == 0) {
		srd_dbg("empty buffer");
		return SRD_ERR_ARG;
	}

	/*
	 * Create new srd_logic object. Each iteration around the PD's loop
	 * will fill one sample into this object.
	 */
	logic = PyObject_New(srd_logic, &srd_logic_type);
	Py_INCREF(logic);
	logic->di = (struct srd_decoder_inst *)di;
	logic->start_samplenum = start_samplenum;
	logic->itercnt = 0;
	logic->inbuf = (uint8_t *)inbuf;
	logic->inbuflen = inbuflen;
	logic->sample = PyList_New(2);
	Py_INCREF(logic->sample);

	Py_IncRef(di->py_inst);
	end_samplenum = start_samplenum + inbuflen / di->data_unitsize;
	if (!(py_res = PyObject_CallMethod(di->py_inst, "decode",
					   "KKO", logic->start_samplenum,
					   end_samplenum, logic))) {
		srd_exception_catch("Protocol decoder instance %s: ",
				    di->inst_id);
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}
	Py_DecRef(py_res);

	return SRD_OK;
}

SRD_PRIV void srd_inst_free(struct srd_decoder_inst *di)
{
	GSList *l;
	struct srd_pd_output *pdo;

	srd_dbg("Freeing instance %s", di->inst_id);

	Py_DecRef(di->py_inst);
	g_free(di->inst_id);
	g_free(di->dec_probemap);
	g_slist_free(di->next_di);
	for (l = di->pd_output; l; l = l->next) {
		pdo = l->data;
		g_free(pdo->proto_id);
		g_free(pdo);
	}
	g_slist_free(di->pd_output);
}

SRD_PRIV void srd_inst_free_all(GSList *stack)
{
	GSList *l;
	struct srd_decoder_inst *di;

	di = NULL;
	for (l = stack ? stack : di_list; di == NULL && l != NULL; l = l->next) {
		di = l->data;
		if (di->next_di)
			srd_inst_free_all(di->next_di);
		srd_inst_free(di);
	}
	if (!stack) {
		g_slist_free(di_list);
		di_list = NULL;
	}
}

/**
 * Start a decoding session.
 *
 * Decoders, instances and stack must have been prepared beforehand.
 *
 * @param num_probes The number of probes which the incoming feed will contain.
 * @param unitsize The number of bytes per sample in the incoming feed.
 * @param samplerate The samplerate of the incoming feed.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_session_start(int num_probes, int unitsize, uint64_t samplerate)
{
	PyObject *args;
	GSList *d;
	struct srd_decoder_inst *di;
	int ret;

	srd_dbg("Calling start() on all instances with %d probes, "
		"unitsize %d samplerate %d.", num_probes, unitsize, samplerate);

	/*
	 * Currently only one item of metadata is passed along to decoders,
	 * samplerate. This can be extended as needed.
	 */
	if (!(args = Py_BuildValue("{s:l}", "samplerate", (long)samplerate))) {
		srd_err("Unable to build Python object for metadata.");
		return SRD_ERR_PYTHON;
	}

	/* Run the start() method on all decoders receiving frontend data. */
	for (d = di_list; d; d = d->next) {
		di = d->data;
		di->data_num_probes = num_probes;
		di->data_unitsize = unitsize;
		di->data_samplerate = samplerate;
		if ((ret = srd_inst_start(di, args)) != SRD_OK)
			break;
	}

	Py_DecRef(args);

	return ret;
}

/**
 * Send a chunk of logic sample data to a running decoder session.
 *
 * @param start_samplenum The sample number of the first sample in this chunk.
 * @param inbuf Pointer to sample data.
 * @param inbuflen Length in bytes of the buffer.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_session_send(uint64_t start_samplenum, const uint8_t *inbuf,
			     uint64_t inbuflen)
{
	GSList *d;
	int ret;

	srd_dbg("Calling decode() on all instances with starting sample "
		"number %" PRIu64 ", %" PRIu64 " bytes at 0x%p",
		start_samplenum, inbuflen, inbuf);

	for (d = di_list; d; d = d->next) {
		if ((ret = srd_inst_decode(start_samplenum, d->data, inbuf,
					   inbuflen)) != SRD_OK)
			return ret;
	}

	return SRD_OK;
}

/**
 * Register/add a decoder output callback function.
 *
 * The function will be called when a protocol decoder sends output back
 * to the PD controller (except for Python objects, which only go up the
 * stack).
 *
 * @param output_type The output type this callback will receive. Only one
 *                    callback per output type can be registered.
 * @param cb The function to call. Must not be NULL.
 * @param cb_data Private data for the callback function. Can be NULL.
 */
SRD_API int srd_pd_output_callback_add(int output_type,
				srd_pd_output_callback_t cb, void *cb_data)
{
	struct srd_pd_callback *pd_cb;

	srd_dbg("Registering new callback for output type %d.", output_type);

	if (!(pd_cb = g_try_malloc(sizeof(struct srd_pd_callback)))) {
		srd_err("Failed to g_malloc() struct srd_pd_callback.");
		return SRD_ERR_MALLOC;
	}

	pd_cb->output_type = output_type;
	pd_cb->cb = cb;
	pd_cb->cb_data = cb_data;
	callbacks = g_slist_append(callbacks, pd_cb);

	return SRD_OK;
}

SRD_PRIV void *srd_pd_output_callback_find(int output_type)
{
	GSList *l;
	struct srd_pd_callback *pd_cb;
	void *(cb);

	cb = NULL;
	for (l = callbacks; l; l = l->next) {
		pd_cb = l->data;
		if (pd_cb->output_type == output_type) {
			cb = pd_cb->cb;
			break;
		}
	}

	return cb;
}

/* This is the backend function to Python sigrokdecode.add() call. */
SRD_PRIV int srd_inst_pd_output_add(struct srd_decoder_inst *di,
				    int output_type, const char *proto_id)
{
	struct srd_pd_output *pdo;

	srd_dbg("Instance %s creating new output type %d for %s.",
		di->inst_id, output_type, proto_id);

	if (!(pdo = g_try_malloc(sizeof(struct srd_pd_output)))) {
		srd_err("Failed to g_malloc() struct srd_pd_output.");
		return -1;
	}

	/* pdo_id is just a simple index, nothing is deleted from this list anyway. */
	pdo->pdo_id = g_slist_length(di->pd_output);
	pdo->output_type = output_type;
	pdo->di = di;
	pdo->proto_id = g_strdup(proto_id);
	di->pd_output = g_slist_append(di->pd_output, pdo);

	return pdo->pdo_id;
}
