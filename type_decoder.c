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
#include <inttypes.h>

/* This is only used for nicer srd_dbg() output. */
static const char *OUTPUT_TYPES[] = {
	"OUTPUT_ANN",
	"OUTPUT_PROTO",
	"OUTPUT_BINARY",
};

static int convert_pyobj(struct srd_decoder_inst *di, PyObject *obj,
			 int *ann_format, char ***ann)
{
	PyObject *py_tmp;
	struct srd_pd_output *pdo;
	int ann_id;

	/* Should be a list of [annotation format, [string, ...]]. */
	if (!PyList_Check(obj) && !PyTuple_Check(obj)) {
		srd_err("Protocol decoder %s submitted %s instead of list.",
			di->decoder->name, obj->ob_type->tp_name);
		return SRD_ERR_PYTHON;
	}

	/* Should have 2 elements. */
	if (PyList_Size(obj) != 2) {
		srd_err("Protocol decoder %s submitted annotation list with "
			"%d elements instead of 2", di->decoder->name,
			PyList_Size(obj));
		return SRD_ERR_PYTHON;
	}

	/*
	 * The first element should be an integer matching a previously
	 * registered annotation format.
	 */
	py_tmp = PyList_GetItem(obj, 0);
	if (!PyLong_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"first element was not an integer.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	ann_id = PyLong_AsLong(py_tmp);
	if (!(pdo = g_slist_nth_data(di->decoder->annotations, ann_id))) {
		srd_err("Protocol decoder %s submitted data to unregistered "
			"annotation format %d.", di->decoder->name, ann_id);
		return SRD_ERR_PYTHON;
	}
	*ann_format = ann_id;

	/* Second element must be a list. */
	py_tmp = PyList_GetItem(obj, 1);
	if (!PyList_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"second element was not a list.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}
	if (py_strlist_to_char(py_tmp, ann) != SRD_OK) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"second element was malformed.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	return SRD_OK;
}

static PyObject *Decoder_put(PyObject *self, PyObject *args)
{
	GSList *l;
	PyObject *data, *py_res;
	struct srd_decoder_inst *di, *next_di;
	struct srd_pd_output *pdo;
	struct srd_proto_data *pdata;
	uint64_t start_sample, end_sample;
	int output_id;
	void (*cb)();

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		/* Shouldn't happen. */
		srd_dbg("put(): self instance not found.");
		return NULL;
	}

	if (!PyArg_ParseTuple(args, "KKiO", &start_sample, &end_sample,
	    &output_id, &data)) {
		/*
		 * This throws an exception, but by returning NULL here we let
		 * Python raise it. This results in a much better trace in
		 * controller.c on the decode() method call.
		 */
		return NULL;
	}

	if (!(l = g_slist_nth(di->pd_output, output_id))) {
		srd_err("Protocol decoder %s submitted invalid output ID %d.",
			di->decoder->name, output_id);
		return NULL;
	}
	pdo = l->data;

	srd_spew("Instance %s put %" PRIu64 "-%" PRIu64 " %s on oid %d.",
		 di->inst_id, start_sample, end_sample,
		 OUTPUT_TYPES[pdo->output_type], output_id);

	if (!(pdata = g_try_malloc0(sizeof(struct srd_proto_data)))) {
		srd_err("Failed to g_malloc() struct srd_proto_data.");
		return NULL;
	}
	pdata->start_sample = start_sample;
	pdata->end_sample = end_sample;
	pdata->pdo = pdo;

	switch (pdo->output_type) {
	case SRD_OUTPUT_ANN:
		/* Annotations are only fed to callbacks. */
		if ((cb = srd_pd_output_callback_find(pdo->output_type))) {
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
			/* TODO: Is this needed? */
			Py_XINCREF(next_di->py_inst);
			srd_spew("Sending %d-%d to instance %s",
				 start_sample, end_sample,
				 next_di->inst_id);
			if (!(py_res = PyObject_CallMethod(
			    next_di->py_inst, "decode", "KKO", start_sample,
			    end_sample, data))) {
				srd_exception_catch("Calling %s decode(): ",
						    next_di->inst_id);
			}
			Py_XDECREF(py_res);
		}
		break;
	case SRD_OUTPUT_BINARY:
		srd_err("SRD_OUTPUT_BINARY not yet supported.");
		break;
	default:
		srd_err("Protocol decoder %s submitted invalid output type %d.",
			di->decoder->name, pdo->output_type);
		break;
	}

	g_free(pdata);

	Py_RETURN_NONE;
}

static PyObject *Decoder_add(PyObject *self, PyObject *args)
{
	PyObject *ret;
	struct srd_decoder_inst *di;
	char *proto_id;
	int output_type, pdo_id;

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		return NULL;
	}

	if (!PyArg_ParseTuple(args, "is", &output_type, &proto_id)) {
		/* Let Python raise this exception. */
		return NULL;
	}

	pdo_id = srd_inst_pd_output_add(di, output_type, proto_id);
	if (pdo_id < 0)
		Py_RETURN_NONE;
	else
		ret = Py_BuildValue("i", pdo_id);

	return ret;
}

static PyMethodDef Decoder_methods[] = {
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: startsample, endsample, data"},
	{"add", Decoder_add, METH_VARARGS, "Create a new output stream"},
	{NULL, NULL, 0, NULL}
};

SRD_PRIV PyTypeObject srd_Decoder_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "sigrokdecode.Decoder",
	.tp_basicsize = sizeof(srd_Decoder),
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = "sigrok Decoder base class",
	.tp_methods = Decoder_methods,
};
