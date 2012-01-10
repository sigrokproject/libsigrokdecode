/*
 * This file is part of the sigrok project.
 *
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

/* lives in type_logic.c */
extern PyTypeObject srd_logic_type;


static int convert_pyobj(struct srd_decoder_instance *di, PyObject *obj,
		int *ann_format, char ***ann)
{
	PyObject *py_tmp;
	struct srd_pd_output *pdo;
	int ann_id;

	/* Should be a list of [annotation format, [string, ...]] */
	if (!PyList_Check(obj) && !PyTuple_Check(obj)) {
		srd_err("Protocol decoder %s submitted %s instead of list",
				di->decoder->name, obj->ob_type->tp_name);
		return SRD_ERR_PYTHON;
	}

	/* Should have 2 elements... */
	if (PyList_Size(obj) != 2) {
		srd_err("Protocol decoder %s submitted annotation list with %d elements instead of 2",
				di->decoder->name, PyList_Size(obj));
		return SRD_ERR_PYTHON;
	}

	/* First element should be an integer matching a previously
	 * registered annotation format. */
	py_tmp = PyList_GetItem(obj, 0);
	if (!PyLong_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but first element was not an integer",
				di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	ann_id = PyLong_AsLong(py_tmp);
	if (!(pdo = g_slist_nth_data(di->decoder->annotation, ann_id))) {
		srd_err("Protocol decoder %s submitted data to non-existent annotation format %d",
				di->decoder->name, ann_id);
		return SRD_ERR_PYTHON;
	}
	*ann_format = ann_id;

	/* Second element must be a list */
	py_tmp = PyList_GetItem(obj, 1);
	if (!PyList_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but second element was not a list",
				di->decoder->name);
		return SRD_ERR_PYTHON;
	}
	if (py_strlist_to_char(py_tmp, ann) != SRD_OK) {
		srd_err("Protocol decoder %s submitted annotation list, but second element was malformed",
				di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	return SRD_OK;
}

static PyObject *Decoder_put(PyObject *self, PyObject *args)
{
	GSList *l;
	PyObject *data, *py_res;
	struct srd_decoder_instance *di, *next_di;
	struct srd_pd_output *pdo;
	struct srd_proto_data *pdata;
	uint64_t start_sample, end_sample;
	int output_id;
	void (*cb)();

	if (!(di = get_di_by_decobject(self)))
		return NULL;

	if (!PyArg_ParseTuple(args, "KKiO", &start_sample, &end_sample, &output_id, &data))
		return NULL;

	if (!(l = g_slist_nth(di->pd_output, output_id))) {
		srd_err("Protocol decoder %s submitted invalid output ID %d",
				di->decoder->name, output_id);
		return NULL;
	}
	pdo = l->data;

	if (!(pdata = g_try_malloc0(sizeof(struct srd_proto_data))))
		return NULL;
	pdata->start_sample = start_sample;
	pdata->end_sample = end_sample;
	pdata->pdo = pdo;

	switch (pdo->output_type) {
	case SRD_OUTPUT_ANN:
		/* Annotations are only fed to callbacks. */
		if ((cb = srd_find_callback(pdo->output_type))) {
			/* Annotations need converting from PyObject. */
			if (convert_pyobj(di, data, &pdata->ann_format,
					(char ***)&pdata->data) != SRD_OK) {
				/* An error was already logged. */
				break;
			}
			cb(pdata);
		}
		break;
	case SRD_OUTPUT_PROTO:
		for (l = di->next_di; l; l = l->next) {
			next_di = l->data;
			/* TODO: is this needed? */
			Py_XINCREF(next_di->py_instance);
			if (!(py_res = PyObject_CallMethod(next_di->py_instance, "decode",
					"KKO", start_sample, end_sample, data))) {
				if (PyErr_Occurred())
					PyErr_Print();
			}
			Py_XDECREF(py_res);
		}
		break;
	case SRD_OUTPUT_BINARY:
		srd_err("SRD_OUTPUT_BINARY not yet supported");
		break;
	default:
		srd_err("Protocol decoder %s submitted invalid output type %d",
				di->decoder->name, pdo->output_type);
		break;
	}

	g_free(pdata);

	Py_RETURN_NONE;
}


static PyObject *Decoder_add(PyObject *self, PyObject *args)
{
	PyObject *ret;
	struct srd_decoder_instance *di;
	char *proto_id;
	int output_type, pdo_id;

	if (!(di = get_di_by_decobject(self))) {
		srd_err("%s():%d decoder instance not found", __func__, __LINE__);
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		return NULL;
	}

	if (!PyArg_ParseTuple(args, "is", &output_type, &proto_id)) {
		if (PyErr_Occurred())
			PyErr_Print();
		return NULL;
	}

	pdo_id = pd_add(di, output_type, proto_id);
	if (pdo_id < 0)
		Py_RETURN_NONE;
	else
		ret = Py_BuildValue("i", pdo_id);

	return ret;
}

static PyMethodDef no_methods[] = { {NULL, NULL, 0, NULL} };
static PyMethodDef Decoder_methods[] = {
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: time, duration, data"},
	{"add", Decoder_add, METH_VARARGS, "Create a new output stream"},
	{NULL, NULL, 0, NULL}
};


typedef struct {
	PyObject_HEAD
} sigrok_Decoder_object;

static PyTypeObject srd_Decoder_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "sigrokdecode.Decoder",
	.tp_basicsize = sizeof(sigrok_Decoder_object),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = "Sigrok Decoder object",
	.tp_methods = Decoder_methods,
};

static struct PyModuleDef sigrokdecode_module = {
	PyModuleDef_HEAD_INIT,
	.m_name = "sigrokdecode",
	.m_doc = "sigrokdecode base class",
	.m_size = -1,
	.m_methods = no_methods,
};

PyMODINIT_FUNC PyInit_sigrokdecode(void)
{
	PyObject *mod;

	/* tp_new needs to be assigned here for compiler portability */
	srd_Decoder_type.tp_new = PyType_GenericNew;
	if (PyType_Ready(&srd_Decoder_type) < 0)
		return NULL;

	srd_logic_type.tp_new = PyType_GenericNew;
	if (PyType_Ready(&srd_logic_type) < 0)
		return NULL;

	mod = PyModule_Create(&sigrokdecode_module);
	Py_INCREF(&srd_Decoder_type);
	if (PyModule_AddObject(mod, "Decoder", (PyObject *)&srd_Decoder_type) == -1)
		return NULL;
	Py_INCREF(&srd_logic_type);
	if (PyModule_AddObject(mod, "srd_logic", (PyObject *)&srd_logic_type) == -1)
		return NULL;

	/* expose output types as symbols in the sigrokdecode module */
	if(PyModule_AddObject(mod, "SRD_OUTPUT_ANN",
			PyLong_FromLong(SRD_OUTPUT_ANN)) == -1)
		return NULL;
	if(PyModule_AddObject(mod, "SRD_OUTPUT_PROTO",
			PyLong_FromLong(SRD_OUTPUT_PROTO)) == -1)
		return NULL;
	if(PyModule_AddObject(mod, "SRD_OUTPUT_BINARY",
			PyLong_FromLong(SRD_OUTPUT_BINARY)) == -1)
		return NULL;

	return mod;
}

