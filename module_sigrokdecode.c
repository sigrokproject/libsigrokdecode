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
#include "config.h"

/* lives in type_logic.c */
extern PyTypeObject srd_logic_type;


/* TODO: not used, doesn't work actually */
static PyObject *Decoder_init(PyObject *self, PyObject *args)
{
	(void)self;
	(void)args;
	printf("init Decoder object %p\n", self);

	Py_RETURN_NONE;
}

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

	if (!(l = g_slist_nth(di->pd_output, output_id))) {
		/* PD supplied invalid output id */
		/* TODO: better error message */
		return NULL;
	}
	pdo = l->data;

	/* TODO: SRD_OUTPUT_ANNOTATION should go back up to the caller,
	 * and SRD_OUTPUT_PROTOCOL should go up the PD stack.
	 */
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
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: time, duration, data"},
	{"output_new", Decoder_output_new, METH_VARARGS,
	 "Create a new output stream"},
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
	.tp_init = (initproc) Decoder_init,
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

	return mod;
}

