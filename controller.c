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

/* TODO: this should probably be in sigrokdecode.h */
/* Re-define some string functions for Python >= 3.0. */
#if PY_VERSION_HEX >= 0x03000000
#define PyString_AsString PyBytes_AsString
#define PyString_FromString PyBytes_FromString
#define PyString_Check PyBytes_Check
#endif


static GSList *pipelines = NULL;

/* lives in decoder.c */
extern GSList *list_pds;
extern GSList *decoders;

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


static PyObject *Decoder_put(PyObject *self, PyObject *args)
{
	PyObject *arg;

//	printf("put object %x\n", self);

	if (!PyArg_ParseTuple(args, "O:put", &arg))
		return NULL;

	// fprintf(stdout, "sigrok.put() called by decoder:\n");
	PyObject_Print(arg, stdout, Py_PRINT_RAW);
	puts("");

	Py_RETURN_NONE;
}

static PyMethodDef no_methods[] = { {NULL, NULL, 0, NULL} };
static PyMethodDef Decoder_methods[] = {
	{"__init__", Decoder_init, METH_VARARGS, ""},
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: time, duration, data"},
	{NULL, NULL, 0, NULL}
};


// class Decoder(sigrok.Decoder):
typedef struct {
	PyObject_HEAD
} sigrok_Decoder_object;

static PyTypeObject sigrok_Decoder_type = {
	PyObject_HEAD_INIT(NULL)
	0,
	"sigrok.Decoder",
	sizeof(sigrok_Decoder_object),
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	0,
	Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	"Sigrok Decoder object",
	0,
	0,
	0,
	0,
	0,
	0,
	Decoder_methods,
};

PyMODINIT_FUNC init_sigrok_Decoder(void)
{
	PyObject *mod;

	sigrok_Decoder_type.tp_new = PyType_GenericNew;
	if (PyType_Ready(&sigrok_Decoder_type) < 0)
		return;

	mod = Py_InitModule3("sigrok", no_methods, "sigrok base classes");
	Py_INCREF(&sigrok_Decoder_type);
	PyModule_AddObject(mod, "Decoder", (PyObject *)&sigrok_Decoder_type);

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

	/* Py_Initialize() returns void and usually cannot fail. */
	Py_Initialize();

	init_sigrok_Decoder();

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
	g_slist_free(list_pds);

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
	decoders = g_slist_append(decoders, di);

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

	probenum = PyInt_FromLong(num);
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

	for (d = decoders; d; d = d->next) {
		di = d->data;
		if (!(py_res = PyObject_CallMethod(di->py_instance, "start",
						 "{s:s,s:i,s:d}",
						 "driver", driver,
						 "unitsize", unitsize,
						 "starttime", starttime))) {
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
 * @param outbuf TODO
 * @param outbuflen TODO
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_run_decoder(struct srd_decoder_instance *dec,
		    uint8_t *inbuf, uint64_t inbuflen)
{
	PyObject *py_instance, *py_res;
	/* FIXME: Don't have a timebase available here. Make one up. */
	static int _timehack = 0;

	_timehack += inbuflen;

//	fprintf(stdout, "%s: %s\n", __func__, dec->decoder->name);

	/* Return an error upon unusable input. */
	if (dec == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (inbuf == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return SRD_ERR_ARGS; /* TODO: More specific error? */

	/* TODO: Error handling. */
	py_instance = dec->py_instance;
	Py_XINCREF(py_instance);

	if (!(py_res = PyObject_CallMethod(py_instance, "decode",
					   "{s:i,s:i,s:s#}",
					   "time", _timehack,
					   "duration", 10,
					   "data", inbuf, inbuflen))) { /* NEWREF */
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */

		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	Py_XDECREF(py_res);
	return SRD_OK;
}


/* Feed logic samples to decoder session. */
int srd_session_feed(uint8_t *inbuf, uint64_t inbuflen)
{
	GSList *d;
	int ret;

//	fprintf(stdout, "%s: %d bytes\n", __func__, inbuflen);

	for (d = decoders; d; d = d->next) {
		if ((ret = srd_run_decoder(d->data, inbuf, inbuflen)) != SRD_OK)
			return ret;
	}

	return SRD_OK;
}


//int srd_pipeline_new(int plid)
//{
//
//
//}
//
//
//int pd_output_new(int output_type, char *output_id, char *description)
//{
//
//
//}




