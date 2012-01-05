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

#include "config.h"
#include "sigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <glib.h>
#include <inttypes.h>


/* TODO
static GSList *pipelines = NULL;
struct srd_pipeline {
	int id;
	GSList *decoders;
};
*/

/* lives in decoder.c */
extern GSList *pd_list;
extern GSList *di_list;

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
 * Multiple calls to srd_init(), without calling srd_exit() inbetween,
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

	PyImport_AppendInittab("sigrokdecode", PyInit_sigrokdecode);

	/* Py_Initialize() returns void and usually cannot fail. */
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
 * any successful srd_init() calls inbetween, is not allowed.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_exit(void)
{
	/* Unload/free all decoders, and then the list of decoders itself. */
	/* TODO: Error handling. */
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
 */
int set_modulepath(void)
{
	int ret;

	PyRun_SimpleString("import sys");
	ret = PyRun_SimpleString("sys.path.append(r'" DECODERS_DIR "');");

	return ret;
}


struct srd_decoder_instance *srd_instance_new(const char *id)
{
	struct srd_decoder *dec;
	struct srd_decoder_instance *di;
	PyObject *py_args;

	fprintf(stdout, "%s: %s\n", __func__, id);

	if (!(dec = srd_get_decoder_by_id(id)))
		return NULL;

	/* TODO: Error handling. Use g_try_malloc(). */
	di = g_malloc(sizeof(*di));
	di->decoder = dec;
	di->pd_output = NULL;
	di->unitsize = 0;

	/* Create an empty Python tuple. */
	if (!(py_args = PyTuple_New(0))) { /* NEWREF */
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */

		return NULL; /* TODO: More specific error? */
	}

	/* Create an instance of the 'Decoder' class. */
	di->py_instance = PyObject_Call(dec->py_decobj, py_args, NULL);
	if (!di->py_instance) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_XDECREF(py_args);
		return NULL; /* TODO: More specific error? */
	}
	di_list = g_slist_append(di_list, di);

	Py_XDECREF(py_args);

	return di;
}


int srd_instance_set_probe(struct srd_decoder_instance *di,
			   const char *probename, int num)
{
	PyObject *probedict, *probenum;

	probedict = PyObject_GetAttrString(di->py_instance, "probes"); /* NEWREF */
	if (!probedict) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */

		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	probenum = PyLong_FromLong(num);
	PyMapping_SetItemString(probedict, (char *)probename, probenum);

	Py_XDECREF(probenum);
	Py_XDECREF(probedict);

	return SRD_OK;
}


int srd_session_start(int num_probes, int unitsize, uint64_t samplerate)
{
	PyObject *py_res;
	GSList *d;
	struct srd_decoder_instance *di;

	fprintf(stdout, "%s\n", __func__);

	for (d = di_list; d; d = d->next) {
		di = d->data;
		di->num_probes = num_probes;
		di->unitsize = unitsize;
		di->samplerate = samplerate;
		if (!(py_res = PyObject_CallMethod(di->py_instance, "start",
				    "{s:l}",
					"samplerate", (long)samplerate))) {
			if (PyErr_Occurred())
				PyErr_Print(); /* Returns void. */

			return SRD_ERR_PYTHON; /* TODO: More specific error? */
		}
		Py_XDECREF(py_res);
	}

	return SRD_OK;
}


/**
 * Run the specified decoder function.
 *
 * @param dec TODO
 * @param inbuf TODO
 * @param inbuflen TODO
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_run_decoder(uint64_t timeoffset, uint64_t duration,
		struct srd_decoder_instance *di, uint8_t *inbuf, uint64_t inbuflen)
{
	PyObject *py_instance, *py_res;
	srd_logic *logic;

	/* Return an error upon unusable input. */
	if (di == NULL)
		return SRD_ERR_ARG; /* TODO: More specific error? */
	if (inbuf == NULL)
		return SRD_ERR_ARG; /* TODO: More specific error? */
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return SRD_ERR_ARG; /* TODO: More specific error? */

	/* TODO: Error handling. */
	py_instance = di->py_instance;
	Py_XINCREF(py_instance);

	logic = PyObject_New(srd_logic, &srd_logic_type);
	Py_INCREF(logic);
	logic->di = di;
	logic->itercnt = 0;
	logic->inbuf = inbuf;
	logic->inbuflen = inbuflen;
	logic->sample = PyList_New(2);
	Py_INCREF(logic->sample);

	if (!(py_res = PyObject_CallMethod(py_instance, "decode",
			"KKO", timeoffset, duration, logic))) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */

		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	Py_XDECREF(py_res);

	return SRD_OK;
}


/* Feed logic samples to decoder session. */
int srd_session_feed(uint64_t timeoffset, uint64_t duration, uint8_t *inbuf,
		uint64_t inbuflen)
{
	GSList *d;
	int ret;

//	fprintf(stdout, "%s: %d bytes\n", __func__, inbuflen);

	for (d = di_list; d; d = d->next) {
		if ((ret = srd_run_decoder(timeoffset, duration, d->data, inbuf,
				inbuflen)) != SRD_OK)
			return ret;
	}

	return SRD_OK;
}


int pd_output_new(struct srd_decoder_instance *di, int output_type,
		char *protocol_id, char *description)
{
	GSList *l;
	struct srd_pd_output *pdo;
	int pdo_id;

	fprintf(stdout, "%s: output type %d, protocol_id %s, description %s\n",
			__func__, output_type, protocol_id, description);

	pdo_id = -1;
	for (l = di->pd_output; l; l = l->next) {
		pdo = l->data;
		if (pdo->pdo_id > pdo_id)
			pdo_id = pdo->pdo_id;
	}
	pdo_id++;

	if (!(pdo = g_try_malloc(sizeof(struct srd_pd_output))))
		return -1;

	pdo->pdo_id = pdo_id;
	pdo->output_type = output_type;
	pdo->protocol_id = g_strdup(protocol_id);
	pdo->description = g_strdup(description);
	di->pd_output = g_slist_append(di->pd_output, pdo);

	return pdo_id;
}

struct srd_decoder_instance *get_di_by_decobject(void *decobject)
{
	GSList *l;
	struct srd_decoder_instance *di;

	for (l = di_list; l; l = l->next) {
		di = l->data;
		if (decobject == di->py_instance)
			return di;
	}

	return NULL;
}


//int srd_pipeline_new(int plid)
//{
//
//
//}




