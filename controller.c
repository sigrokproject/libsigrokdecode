/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
 * Copyright (C) 2011 Bert Vermeulen <bert@biot.com>
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
#include <sigrokdecode.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <glib.h>
#include <inttypes.h>


/* TODO
static GSList *pipelines = NULL;
*/

/* lives in decoder.c */
extern GSList *pd_list;
extern GSList *di_list;

struct srd_pipeline {
	int id;
	GSList *decoders;
};



static PyObject *Decoder_init(PyObject *self, PyObject *args)
{
	(void)self;
	(void)args;
//	printf("init object %x\n", self);

	Py_RETURN_NONE;
}

struct srd_decoder_instance *get_di_by_decobject(void *decobject);

static PyObject *Decoder_put(PyObject *self, PyObject *args)
{
	GSList *l;
	PyObject *data;
	struct srd_decoder_instance *di;
	struct srd_pd_output *pdo;
	uint64_t timeoffset, duration;
	int output_id;

	if (!(di = get_di_by_decobject(self)))
		return NULL;

	if (!PyArg_ParseTuple(args, "KKiO", &timeoffset, &duration, &output_id, &data))
		return NULL;

	printf("put: %s instance %p time %" PRIu64 " duration %" PRIu64 " ",
			di->decoder->name, di, timeoffset, duration);

	if (!(l = g_slist_nth(di->pd_output, output_id)))
		/* PD supplied invalid output id */
		/* TODO: better error message */
		return NULL;
	pdo = l->data;

	printf("stream %d: ", pdo->output_type);
	PyObject_Print(data, stdout, Py_PRINT_RAW);
	puts("");

	Py_RETURN_NONE;
}


static PyObject *Decoder_output_new(PyObject *self, PyObject *py_output_type)
{
	PyObject *ret;
	struct srd_decoder_instance *di;
	char *protocol_id, *description;
	int output_type, pdo_id;

	if (!(di = get_di_by_decobject(self)))
		return NULL;

	printf("output_new di %s\n", di->decoder->name);

//	if (!PyArg_ParseTuple(args, "i:output_type,s:protocol_id,s:description",
//			&output_type, &protocol_id, &description))
	if (!PyArg_ParseTuple(py_output_type, "i:output_type", &output_type))
		return NULL;

	protocol_id = "i2c";
	description = "blah";
	pdo_id = pd_output_new(di, output_type, protocol_id, description);
	if (pdo_id < 0)
		Py_RETURN_NONE;
	else
		ret = Py_BuildValue("i", pdo_id);

	return ret;
}

static PyMethodDef no_methods[] = { {NULL, NULL, 0, NULL} };
static PyMethodDef Decoder_methods[] = {
	{"__init__", Decoder_init, METH_VARARGS, ""},
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: time, duration, data"},
	{"output_new", Decoder_output_new, METH_VARARGS,
	 "Create a new output stream"},
	{NULL, NULL, 0, NULL}
};


typedef struct {
	PyObject_HEAD
} sigrok_Decoder_object;

static PyTypeObject sigrok_Decoder_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "sigrok.Decoder",
	.tp_basicsize = sizeof(sigrok_Decoder_object),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = "Sigrok Decoder object",
	.tp_methods = Decoder_methods,
};

static struct PyModuleDef sigrok_Decoder_module = {
	PyModuleDef_HEAD_INIT,
	.m_name = "sigrok",
	.m_doc = "sigrok base classes",
	.m_size = -1,
	.m_methods = no_methods,
};

PyMODINIT_FUNC PyInit_sigrok(void)
{
	PyObject *mod;

	/* assign this here, for compiler portability */
	sigrok_Decoder_type.tp_new = PyType_GenericNew;
	if (PyType_Ready(&sigrok_Decoder_type) < 0)
		return NULL;

//	mod = Py_InitModule3("sigrok", no_methods, "sigrok base classes");
	mod = PyModule_Create(&sigrok_Decoder_module);
	Py_INCREF(&sigrok_Decoder_type);
	if (PyModule_AddObject(mod, "Decoder", (PyObject *)&sigrok_Decoder_type) == -1)
		return NULL;

	return mod;
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

	PyImport_AppendInittab("sigrok", PyInit_sigrok);

	/* Py_Initialize() returns void and usually cannot fail. */
	Py_Initialize();

	PyInit_sigrok();

	PyRun_SimpleString("import sys;");
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


int srd_session_start(const char *driver, int unitsize, uint64_t starttime,
		uint64_t samplerate)
{
	PyObject *py_res;
	GSList *d;
	struct srd_decoder_instance *di;

	fprintf(stdout, "%s: %s\n", __func__, driver);

	for (d = di_list; d; d = d->next) {
		di = d->data;
		if (!(py_res = PyObject_CallMethod(di->py_instance, "start",
					"{s:s,s:l,s:l,s:l}",
					"driver", driver,
					"unitsize", (long)unitsize,
					"starttime", (long)starttime,
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
		struct srd_decoder_instance *dec, uint8_t *inbuf, uint64_t inbuflen)
{
	PyObject *py_instance, *py_res;

//	fprintf(stdout, "%s: %s\n", __func__, dec->decoder->name);
//	printf("to %u du %u len %d\n", timeoffset, duration, inbuflen);

	/* Return an error upon unusable input. */
	if (dec == NULL)
		return SRD_ERR_ARG; /* TODO: More specific error? */
	if (inbuf == NULL)
		return SRD_ERR_ARG; /* TODO: More specific error? */
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return SRD_ERR_ARG; /* TODO: More specific error? */

	/* TODO: Error handling. */
	py_instance = dec->py_instance;
	Py_XINCREF(py_instance);

	if (!(py_res = PyObject_CallMethod(py_instance, "decode",
			"KKy#", timeoffset, duration, inbuf, inbuflen))) {
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


//int srd_pipeline_new(int plid)
//{
//
//
//}




