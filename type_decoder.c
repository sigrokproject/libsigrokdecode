/*
 * This file is part of the libsigrokdecode project.
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

#include <config.h>
#include "libsigrokdecode-internal.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode.h"
#include <inttypes.h>

typedef struct {
        PyObject_HEAD
} srd_Decoder;

/* This is only used for nicer srd_dbg() output.
 */
static const char *output_type_name(unsigned int idx)
{
	static const char names[][16] = {
		"OUTPUT_ANN",
		"OUTPUT_PYTHON",
		"OUTPUT_BINARY",
		"OUTPUT_META",
		"(invalid)"
	};
	return names[MIN(idx, G_N_ELEMENTS(names) - 1)];
}

static int convert_annotation(struct srd_decoder_inst *di, PyObject *obj,
		struct srd_proto_data *pdata)
{
	PyObject *py_tmp;
	struct srd_pd_output *pdo;
	struct srd_proto_data_annotation *pda;
	int ann_class;
	char **ann_text;

	/* Should be a list of [annotation class, [string, ...]]. */
	if (!PyList_Check(obj)) {
		srd_err("Protocol decoder %s submitted an annotation that"
			" is not a list", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	/* Should have 2 elements. */
	if (PyList_Size(obj) != 2) {
		srd_err("Protocol decoder %s submitted annotation list with "
			"%zd elements instead of 2", di->decoder->name,
			PyList_Size(obj));
		return SRD_ERR_PYTHON;
	}

	/*
	 * The first element should be an integer matching a previously
	 * registered annotation class.
	 */
	py_tmp = PyList_GetItem(obj, 0);
	if (!PyLong_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"first element was not an integer.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}
	ann_class = PyLong_AsLong(py_tmp);
	if (!(pdo = g_slist_nth_data(di->decoder->annotations, ann_class))) {
		srd_err("Protocol decoder %s submitted data to unregistered "
			"annotation class %d.", di->decoder->name, ann_class);
		return SRD_ERR_PYTHON;
	}

	/* Second element must be a list. */
	py_tmp = PyList_GetItem(obj, 1);
	if (!PyList_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"second element was not a list.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}
	if (py_strseq_to_char(py_tmp, &ann_text) != SRD_OK) {
		srd_err("Protocol decoder %s submitted annotation list, but "
			"second element was malformed.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	pda = g_malloc(sizeof(struct srd_proto_data_annotation));
	pda->ann_class = ann_class;
	pda->ann_text = ann_text;
	pdata->data = pda;

	return SRD_OK;
}

static int convert_binary(struct srd_decoder_inst *di, PyObject *obj,
		struct srd_proto_data *pdata)
{
	struct srd_proto_data_binary *pdb;
	PyObject *py_tmp;
	Py_ssize_t size;
	int bin_class;
	char *class_name, *buf;

	/* Should be a list of [binary class, bytes]. */
	if (!PyList_Check(obj)) {
		srd_err("Protocol decoder %s submitted non-list for SRD_OUTPUT_BINARY.",
			di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	/* Should have 2 elements. */
	if (PyList_Size(obj) != 2) {
		srd_err("Protocol decoder %s submitted SRD_OUTPUT_BINARY list "
				"with %zd elements instead of 2", di->decoder->name,
				PyList_Size(obj));
		return SRD_ERR_PYTHON;
	}

	/* The first element should be an integer. */
	py_tmp = PyList_GetItem(obj, 0);
	if (!PyLong_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted SRD_OUTPUT_BINARY list, "
			"but first element was not an integer.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}
	bin_class = PyLong_AsLong(py_tmp);
	if (!(class_name = g_slist_nth_data(di->decoder->binary, bin_class))) {
		srd_err("Protocol decoder %s submitted SRD_OUTPUT_BINARY with "
			"unregistered binary class %d.", di->decoder->name, bin_class);
		return SRD_ERR_PYTHON;
	}

	/* Second element should be bytes. */
	py_tmp = PyList_GetItem(obj, 1);
	if (!PyBytes_Check(py_tmp)) {
		srd_err("Protocol decoder %s submitted SRD_OUTPUT_BINARY list, "
			"but second element was not bytes.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	/* Consider an empty set of bytes a bug. */
	if (PyBytes_Size(py_tmp) == 0) {
		srd_err("Protocol decoder %s submitted SRD_OUTPUT_BINARY "
				"with empty data set.", di->decoder->name);
		return SRD_ERR_PYTHON;
	}

	pdb = g_malloc(sizeof(struct srd_proto_data_binary));
	if (PyBytes_AsStringAndSize(py_tmp, &buf, &size) == -1)
		return SRD_ERR_PYTHON;
	pdb->bin_class = bin_class;
	pdb->size = size;
	if (!(pdb->data = g_try_malloc(pdb->size)))
		return SRD_ERR_MALLOC;
	memcpy((void *)pdb->data, (const void *)buf, pdb->size);
	pdata->data = pdb;

	return SRD_OK;
}

static int convert_meta(struct srd_proto_data *pdata, PyObject *obj)
{
	long long intvalue;
	double dvalue;

	if (pdata->pdo->meta_type == G_VARIANT_TYPE_INT64) {
		if (!PyLong_Check(obj)) {
			PyErr_Format(PyExc_TypeError, "This output was registered "
					"as 'int', but something else was passed.");
			return SRD_ERR_PYTHON;
		}
		intvalue = PyLong_AsLongLong(obj);
		if (PyErr_Occurred())
			return SRD_ERR_PYTHON;
		pdata->data = g_variant_new_int64(intvalue);
	} else if (pdata->pdo->meta_type == G_VARIANT_TYPE_DOUBLE) {
		if (!PyFloat_Check(obj)) {
			PyErr_Format(PyExc_TypeError, "This output was registered "
					"as 'float', but something else was passed.");
			return SRD_ERR_PYTHON;
		}
		dvalue = PyFloat_AsDouble(obj);
		if (PyErr_Occurred())
			return SRD_ERR_PYTHON;
		pdata->data = g_variant_new_double(dvalue);
	}

	return SRD_OK;
}

static PyObject *Decoder_put(PyObject *self, PyObject *args)
{
	GSList *l;
	PyObject *py_data, *py_res;
	struct srd_decoder_inst *di, *next_di;
	struct srd_pd_output *pdo;
	struct srd_proto_data *pdata;
	uint64_t start_sample, end_sample;
	int output_id;
	struct srd_pd_callback *cb;

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		/* Shouldn't happen. */
		srd_dbg("put(): self instance not found.");
		return NULL;
	}

	if (!PyArg_ParseTuple(args, "KKiO", &start_sample, &end_sample,
		&output_id, &py_data)) {
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
		 output_type_name(pdo->output_type), output_id);

	pdata = g_malloc0(sizeof(struct srd_proto_data));
	pdata->start_sample = start_sample;
	pdata->end_sample = end_sample;
	pdata->pdo = pdo;

	switch (pdo->output_type) {
	case SRD_OUTPUT_ANN:
		/* Annotations are only fed to callbacks. */
		if ((cb = srd_pd_output_callback_find(di->sess, pdo->output_type))) {
			/* Convert from PyDict to srd_proto_data_annotation. */
			if (convert_annotation(di, py_data, pdata) != SRD_OK) {
				/* An error was already logged. */
				break;
			}
			cb->cb(pdata, cb->cb_data);
		}
		break;
	case SRD_OUTPUT_PYTHON:
		for (l = di->next_di; l; l = l->next) {
			next_di = l->data;
			srd_spew("Sending %" PRIu64 "-%" PRIu64 " to instance %s",
				 start_sample, end_sample, next_di->inst_id);
			if (!(py_res = PyObject_CallMethod(
				next_di->py_inst, "decode", "KKO", start_sample,
				end_sample, py_data))) {
				srd_exception_catch("Calling %s decode() failed",
							next_di->inst_id);
			}
			Py_XDECREF(py_res);
		}
		if ((cb = srd_pd_output_callback_find(di->sess, pdo->output_type))) {
			/* Frontends aren't really supposed to get Python
			 * callbacks, but it's useful for testing. */
			pdata->data = py_data;
			cb->cb(pdata, cb->cb_data);
		}
		break;
	case SRD_OUTPUT_BINARY:
		if ((cb = srd_pd_output_callback_find(di->sess, pdo->output_type))) {
			/* Convert from PyDict to srd_proto_data_binary. */
			if (convert_binary(di, py_data, pdata) != SRD_OK) {
				/* An error was already logged. */
				break;
			}
			cb->cb(pdata, cb->cb_data);
		}
		break;
	case SRD_OUTPUT_META:
		if ((cb = srd_pd_output_callback_find(di->sess, pdo->output_type))) {
			/* Annotations need converting from PyObject. */
			if (convert_meta(pdata, py_data) != SRD_OK) {
				/* An exception was already set up. */
				break;
			}
			cb->cb(pdata, cb->cb_data);
		}
		break;
	default:
		srd_err("Protocol decoder %s submitted invalid output type %d.",
			di->decoder->name, pdo->output_type);
		break;
	}

	g_free(pdata);

	Py_RETURN_NONE;
}

static PyObject *Decoder_register(PyObject *self, PyObject *args,
		PyObject *kwargs)
{
	struct srd_decoder_inst *di;
	struct srd_pd_output *pdo;
	PyObject *py_new_output_id;
	PyTypeObject *meta_type_py;
	const GVariantType *meta_type_gv;
	int output_type;
	char *proto_id, *meta_name, *meta_descr;
	char *keywords[] = {"output_type", "proto_id", "meta", NULL};

	meta_type_py = NULL;
	meta_type_gv = NULL;
	meta_name = meta_descr = NULL;

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		return NULL;
	}

	/* Default to instance id, which defaults to class id. */
	proto_id = di->inst_id;
	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "i|s(Oss)", keywords,
			&output_type, &proto_id,
			&meta_type_py, &meta_name, &meta_descr)) {
		/* Let Python raise this exception. */
		return NULL;
	}

	/* Check if the meta value's type is supported. */
	if (output_type == SRD_OUTPUT_META) {
		if (meta_type_py == &PyLong_Type)
			meta_type_gv = G_VARIANT_TYPE_INT64;
		else if (meta_type_py == &PyFloat_Type)
			meta_type_gv = G_VARIANT_TYPE_DOUBLE;
		else {
			PyErr_Format(PyExc_TypeError, "Unsupported type.");
			return NULL;
		}
	}

	srd_dbg("Instance %s creating new output type %d for %s.",
		di->inst_id, output_type, proto_id);

	pdo = g_malloc(sizeof(struct srd_pd_output));

	/* pdo_id is just a simple index, nothing is deleted from this list anyway. */
	pdo->pdo_id = g_slist_length(di->pd_output);
	pdo->output_type = output_type;
	pdo->di = di;
	pdo->proto_id = g_strdup(proto_id);

	if (output_type == SRD_OUTPUT_META) {
		pdo->meta_type = meta_type_gv;
		pdo->meta_name = g_strdup(meta_name);
		pdo->meta_descr = g_strdup(meta_descr);
	}

	di->pd_output = g_slist_append(di->pd_output, pdo);
	py_new_output_id = Py_BuildValue("i", pdo->pdo_id);

	return py_new_output_id;
}

static int get_term_type(const char *v)
{
	switch (v[0]) {
	case 'h':
		return SRD_TERM_HIGH;
	case 'l':
		return SRD_TERM_LOW;
	case 'r':
		return SRD_TERM_RISING_EDGE;
	case 'f':
		return SRD_TERM_FALLING_EDGE;
	case 'e':
		return SRD_TERM_EITHER_EDGE;
	case 'n':
		return SRD_TERM_NO_EDGE;
	}

	return -1;
}

/**
 * Get the pin values at the current sample number.
 *
 * @param di The decoder instance to use. Must not be NULL.
 *           The number of channels must be >= 1.
 *
 * @return A newly allocated PyTuple containing the pin values at the
 *         current sample number.
 */
static PyObject *get_current_pinvalues(const struct srd_decoder_inst *di)
{
	int i;
	uint8_t sample;
	const uint8_t *sample_pos;
	int byte_offset, bit_offset;
	PyObject *py_pinvalues;

	if (!di) {
		srd_err("Invalid decoder instance.");
		return NULL;
	}

	py_pinvalues = PyTuple_New(di->dec_num_channels);

	for (i = 0; i < di->dec_num_channels; i++) {
		/* A channelmap value of -1 means "unused optional channel". */
		if (di->dec_channelmap[i] == -1) {
			/* Value of unused channel is 0xff, instead of 0 or 1. */
			PyTuple_SetItem(py_pinvalues, i, PyLong_FromLong(0xff));
		} else {
			sample_pos = di->inbuf + ((di->abs_cur_samplenum - di->abs_start_samplenum) * di->data_unitsize);
			byte_offset = di->dec_channelmap[i] / 8;
			bit_offset = di->dec_channelmap[i] % 8;
			sample = *(sample_pos + byte_offset) & (1 << bit_offset) ? 1 : 0;
			PyTuple_SetItem(py_pinvalues, i, PyLong_FromLong(sample));
		}
	}

	Py_IncRef(py_pinvalues);

	return py_pinvalues;
}

/**
 * Create a list of terms in the specified condition.
 *
 * If there are no terms in the condition, 'term_list' will be NULL.
 *
 * @param py_dict A Python dict containing terms. Must not be NULL.
 * @param term_list Pointer to a GSList which will be set to the newly
 *                  created list of terms. Must not be NULL.
 *
 * @return SRD_OK upon success, a negative error code otherwise.
 */
static int create_term_list(PyObject *py_dict, GSList **term_list)
{
	Py_ssize_t pos = 0;
	PyObject *py_key, *py_value;
	struct srd_term *term;
	uint64_t num_samples_to_skip;
	char *term_str;

	if (!py_dict || !term_list)
		return SRD_ERR_ARG;

	/* "Create" an empty GSList of terms. */
	*term_list = NULL;

	/* Iterate over all items in the current dict. */
	while (PyDict_Next(py_dict, &pos, &py_key, &py_value)) {
		/* Check whether the current key is a string or a number. */
		if (PyLong_Check(py_key)) {
			/* The key is a number. */
			/* TODO: Check if the number is a valid channel. */
			/* Get the value string. */
			if ((py_pydictitem_as_str(py_dict, py_key, &term_str)) != SRD_OK) {
				srd_err("Failed to get the value.");
				return SRD_ERR;
			}
			term = g_malloc0(sizeof(struct srd_term));
			term->type = get_term_type(term_str);
			term->channel = PyLong_AsLong(py_key);
			g_free(term_str);
		} else if (PyUnicode_Check(py_key)) {
			/* The key is a string. */
			/* TODO: Check if it's "skip". */
			if ((py_pydictitem_as_long(py_dict, py_key, &num_samples_to_skip)) != SRD_OK) {
				srd_err("Failed to get number of samples to skip.");
				return SRD_ERR;
			}
			term = g_malloc0(sizeof(struct srd_term));
			term->type = SRD_TERM_SKIP;
			term->num_samples_to_skip = num_samples_to_skip;
			term->num_samples_already_skipped = 0;
		} else {
			srd_err("Term key is neither a string nor a number.");
			return SRD_ERR;
		}

		/* Add the term to the list of terms. */
		*term_list = g_slist_append(*term_list, term);
	}

	return SRD_OK;
}

/**
 * Replace the current condition list with the new one.
 *
 * @param self TODO. Must not be NULL.
 * @param args TODO. Must not be NULL.
 *
 * @retval SRD_OK The new condition list was set successfully.
 * @retval SRD_ERR There was an error setting the new condition list.
 *                 The contents of di->condition_list are undefined.
 * @retval 9999 TODO.
 */
static int set_new_condition_list(PyObject *self, PyObject *args)
{
	struct srd_decoder_inst *di;
	GSList *term_list;
	PyObject *py_conditionlist, *py_conds, *py_dict;
	int i, num_conditions, ret;

	if (!self || !args)
		return SRD_ERR_ARG;

	/* Get the decoder instance. */
	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		return SRD_ERR;
	}

	/* Parse the argument of self.wait() into 'py_conds'. */
	if (!PyArg_ParseTuple(args, "O", &py_conds)) {
		/* Let Python raise this exception. */
		return SRD_ERR;
	}

	/* Check whether 'py_conds' is a dict or a list. */
	if (PyList_Check(py_conds)) {
		/* 'py_conds' is a list. */
		py_conditionlist = py_conds;
		num_conditions = PyList_Size(py_conditionlist);
		if (num_conditions == 0)
			return 9999; /* The PD invoked self.wait([]). */
		Py_IncRef(py_conditionlist);
	} else if (PyDict_Check(py_conds)) {
		/* 'py_conds' is a dict. */
		if (PyDict_Size(py_conds) == 0)
			return 9999; /* The PD invoked self.wait({}). */
		/* Make a list and put the dict in there for convenience. */
		py_conditionlist = PyList_New(1);
		Py_IncRef(py_conds);
		PyList_SetItem(py_conditionlist, 0, py_conds);
		num_conditions = 1;
	} else {
		srd_err("Condition list is neither a list nor a dict.");
		return SRD_ERR;
	}

	/* Free the old condition list. */
	condition_list_free(di);

	ret = SRD_OK;

	/* Iterate over the conditions, set di->condition_list accordingly. */
	for (i = 0; i < num_conditions; i++) {
		/* Get a condition (dict) from the condition list. */
		py_dict = PyList_GetItem(py_conditionlist, i);
		if (!PyDict_Check(py_dict)) {
			srd_err("Condition is not a dict.");
			ret = SRD_ERR;
			break;
		}

		/* Create the list of terms in this condition. */
		if ((ret = create_term_list(py_dict, &term_list)) < 0)
			break;

		/* Add the new condition to the PD instance's condition list. */
		di->condition_list = g_slist_append(di->condition_list, term_list);
	}

	Py_DecRef(py_conditionlist);

	return ret;
}

static PyObject *Decoder_wait(PyObject *self, PyObject *args)
{
	int ret;
	unsigned int i;
	gboolean found_match;
	struct srd_decoder_inst *di;
	PyObject *py_pinvalues, *py_matched;

	if (!self || !args)
		return NULL;

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		Py_RETURN_NONE;
	}

	ret = set_new_condition_list(self, args);

	if (ret == 9999) {
		/* Empty condition list, automatic match. */
		PyObject_SetAttrString(di->py_inst, "matched", Py_None);
		/* Leave self.samplenum unchanged (== di->abs_cur_samplenum). */
		return get_current_pinvalues(di);
	}

	while (1) {
		/* Wait for new samples to process. */
		g_mutex_lock(&di->data_mutex);
		while (!di->got_new_samples)
			g_cond_wait(&di->got_new_samples_cond, &di->data_mutex);

		/* Check whether any of the current condition(s) match. */
		ret = process_samples_until_condition_match(di, &found_match);

		/* If there's a match, set self.samplenum etc. and return. */
		if (found_match) {
			/* Set self.samplenum to the (absolute) sample number that matched. */
			PyObject_SetAttrString(di->py_inst, "samplenum",
				PyLong_FromLong(di->abs_cur_samplenum));

			if (di->match_array && di->match_array->len > 0) {
				py_matched = PyTuple_New(di->match_array->len);
				for (i = 0; i < di->match_array->len; i++)
					PyTuple_SetItem(py_matched, i, PyBool_FromLong(di->match_array->data[i]));
				PyObject_SetAttrString(di->py_inst, "matched", py_matched);
				match_array_free(di);
			} else {
				PyObject_SetAttrString(di->py_inst, "matched", Py_None);
			}
	
			py_pinvalues = get_current_pinvalues(di);

			g_mutex_unlock(&di->data_mutex);

			return py_pinvalues;
		}

		/* No match, reset state for the next chunk. */
		di->got_new_samples = FALSE;
		di->handled_all_samples = TRUE;
		di->abs_start_samplenum = 0;
		di->abs_end_samplenum = 0;
		di->inbuf = NULL;
		di->inbuflen = 0;

		/* Signal the main thread that we handled all samples. */
		g_cond_signal(&di->handled_all_samples_cond);

		g_mutex_unlock(&di->data_mutex);
	}

	Py_RETURN_NONE;
}

/**
 * Return whether the specified channel was supplied to the decoder.
 *
 * @param self TODO. Must not be NULL.
 * @param args TODO. Must not be NULL.
 *
 * @retval Py_True The channel has been supplied by the frontend.
 * @retval Py_False The channel has been supplied by the frontend.
 * @retval NULL An error occurred.
 */
static PyObject *Decoder_has_channel(PyObject *self, PyObject *args)
{
	int idx, max_idx;
	struct srd_decoder_inst *di;
	PyObject *py_channel;

	if (!self || !args)
		return NULL;

	if (!(di = srd_inst_find_by_obj(NULL, self))) {
		PyErr_SetString(PyExc_Exception, "decoder instance not found");
		return NULL;
	}

	/* Parse the argument of self.has_channel() into 'py_channel'. */
	if (!PyArg_ParseTuple(args, "O", &py_channel)) {
		/* Let Python raise this exception. */
		return NULL;
	}

	if (!PyLong_Check(py_channel)) {
		PyErr_SetString(PyExc_Exception, "channel index not a number");
		return NULL;
	}

	idx = PyLong_AsLong(py_channel);
	max_idx = g_slist_length(di->decoder->channels)
		+ g_slist_length(di->decoder->opt_channels) - 1;

	if (idx < 0 || idx > max_idx) {
		srd_err("Invalid channel index %d/%d.", idx, max_idx);
		PyErr_SetString(PyExc_Exception, "invalid channel");
		return NULL;
	}

	return (di->dec_channelmap[idx] == -1) ? Py_False : Py_True;
}

static PyMethodDef Decoder_methods[] = {
	{"put", Decoder_put, METH_VARARGS,
	 "Accepts a dictionary with the following keys: startsample, endsample, data"},
	{"register", (PyCFunction)Decoder_register, METH_VARARGS|METH_KEYWORDS,
			"Register a new output stream"},
	{"wait", Decoder_wait, METH_VARARGS,
			"Wait for one or more conditions to occur"},
	{"has_channel", Decoder_has_channel, METH_VARARGS,
			"Report whether a channel was supplied"},
	{NULL, NULL, 0, NULL}
};

/**
 * Create the sigrokdecode.Decoder type.
 *
 * @return The new type object.
 *
 * @private
 */
SRD_PRIV PyObject *srd_Decoder_type_new(void)
{
	PyType_Spec spec;
	PyType_Slot slots[] = {
		{ Py_tp_doc, "sigrok Decoder base class" },
		{ Py_tp_methods, Decoder_methods },
		{ Py_tp_new, (void *)&PyType_GenericNew },
		{ 0, NULL }
	};
	spec.name = "sigrokdecode.Decoder";
	spec.basicsize = sizeof(srd_Decoder);
	spec.itemsize = 0;
	spec.flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE;
	spec.slots = slots;

	return PyType_FromSpec(&spec);
}
