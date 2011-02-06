/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
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

#include "config.h"
#include <sigrokdecode.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <stdio.h>
#include <string.h>
#include <dirent.h>

/* Re-define some string functions for Python >= 3.0. */
#if PY_VERSION_HEX >= 0x03000000
#define PyString_AsString PyBytes_AsString
#define PyString_FromString PyBytes_FromString
#define PyString_Check PyBytes_Check
#endif

/* The list of protocol decoders. */
GSList *list_pds = NULL;

/*
 * Here's a quick overview of Python/C API reference counting.
 *
 * Check the Python/C API docs for what type of reference a function returns.
 *
 *  - If it returns a "new reference", you're responsible to Py_XDECREF() it.
 *
 *  - If it returns a "borrowed reference", you MUST NOT Py_XDECREF() it.
 *
 *  - If a function "steals" a reference, you no longer are responsible for
 *    Py_XDECREF()ing it (someone else will do it for you at some point).
 */

static int srd_load_decoder(const char *name, struct srd_decoder **dec);

/**
 * Initialize libsigrokdecode.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_init(void)
{
	DIR *dir;
	struct dirent *dp;
	char *decodername;
	struct srd_decoder *dec;
	int ret;

	/* Py_Initialize() returns void and usually cannot fail. */
	Py_Initialize();

	/* Add search directory for the protocol decoders. */
	/* FIXME: Check error code. */
	/* FIXME: What happens if this function is called multiple times? */
	PyRun_SimpleString("import sys;"
			   "sys.path.append(r'" DECODERS_DIR "');");

	if (!(dir = opendir(DECODERS_DIR)))
		return SRD_ERR_DECODERS_DIR;

	while ((dp = readdir(dir)) != NULL) {
		if (!g_str_has_suffix(dp->d_name, ".py"))
			continue;

		/* Decoder name == filename (without .py suffix). */
		decodername = g_strndup(dp->d_name, strlen(dp->d_name) - 3);

		/* TODO: Error handling. */
		dec = malloc(sizeof(struct srd_decoder));

		/* Load the decoder. */
		ret = srd_load_decoder(decodername, &dec);

		/* Append it to the list of supported/loaded decoders. */
		list_pds = g_slist_append(list_pds, dec);
	}
	closedir(dir);

	return SRD_OK;
}

/**
 * Returns the list of supported/loaded protocol decoders.
 *
 * This is a GSList containing the names of the decoders as strings.
 *
 * @return List of decoders, NULL if none are supported or loaded.
 */
GSList *srd_list_decoders(void)
{
	return list_pds;
}

/**
 * Get the decoder with the specified ID.
 *
 * @param id The ID string of the decoder to return.
 * @return The decoder with the specified ID, or NULL if not found.
 */
struct srd_decoder *srd_get_decoder_by_id(const char *id)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_list_decoders(); l; l = l->next) {
		dec = l->data;
		if (!strcmp(dec->id, id))
			return dec;
	}

	return NULL;
}

/**
 * Helper function to handle Python strings.
 *
 * TODO: @param entries.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *         The 'outstr' argument points to a malloc()ed string upon success.
 */
static int h_str(PyObject *py_res, PyObject *py_func, PyObject *py_mod,
		 const char *key, char **outstr)
{
	PyObject *py_str;
	char *str;
	int ret;

	py_str = PyMapping_GetItemString(py_res, (char *)key);
	if (!py_str || !PyString_Check(py_str)) {
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_h_decref_func;
	}

	/*
	 * PyString_AsString()'s returned string refers to an internal buffer
	 * (not a copy), i.e. the data must not be modified, and the memory
	 * must not be free()'d.
	 */
	if (!(str = PyString_AsString(py_str))) {
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_h_decref_str;
	}

	if (!(*outstr = g_strdup(str))) {
		ret = SRD_ERR_MALLOC;
		goto err_h_decref_str;
	}

	Py_XDECREF(py_str);

	return SRD_OK;

err_h_decref_str:
	Py_XDECREF(py_str);
err_h_decref_func:
	Py_XDECREF(py_func);
	Py_XDECREF(py_mod);

	if (PyErr_Occurred())
		PyErr_Print(); /* Returns void. */

	return ret;
}

/**
 * TODO
 *
 * @param name TODO
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
static int srd_load_decoder(const char *name,
			      struct srd_decoder **dec)
{
	struct srd_decoder *d;
	PyObject *py_mod, *py_func, *py_res /* , *py_tuple */;
	int r;

	/* "Import" the Python module. */
	if (!(py_mod = PyImport_ImportModule(name))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* Get the 'register' function name as Python callable object. */
	py_func = PyObject_GetAttrString(py_mod, "register"); /* NEWREF */
	if (!py_func || !PyCallable_Check(py_func)) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_XDECREF(py_mod);
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* Call the 'register' function without arguments, get the result. */
	if (!(py_res = PyObject_CallFunction(py_func, NULL))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_XDECREF(py_func);
		Py_XDECREF(py_mod);
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	if (!(d = malloc(sizeof(struct srd_decoder))))
		return SRD_ERR_MALLOC;

	if ((r = h_str(py_res, py_func, py_mod, "id", &(d->id))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "name", &(d->name))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "longname",
		       &(d->longname))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "desc", &(d->desc))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "longdesc",
		       &(d->longdesc))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "author", &(d->author))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "email", &(d->email))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "license", &(d->license))) < 0)
		return r;

	d->py_mod = py_mod;

	Py_XDECREF(py_res);
	Py_XDECREF(py_func);

	/* Get the 'decode' function name as Python callable object. */
	py_func = PyObject_GetAttrString(py_mod, "decode"); /* NEWREF */
	if (!py_func || !PyCallable_Check(py_func)) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_XDECREF(py_mod);
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	d->py_func = py_func;

	/* TODO: Handle func, inputformats, outputformats. */
	/* Note: They must at least be set to NULL, will segfault otherwise. */
	d->func = NULL;
	d->inputformats = NULL;
	d->outputformats = NULL;

	*dec = d;

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
int srd_run_decoder(struct srd_decoder *dec,
			     uint8_t *inbuf, uint64_t inbuflen,
			     uint8_t **outbuf, uint64_t *outbuflen)
{
	PyObject *py_mod, *py_func, *py_args, *py_value, *py_res;
	int r, ret;

	/* TODO: Use #defines for the return codes. */

	/* Return an error upon unusable input. */
	if (dec == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (inbuf == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (outbuf == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */
	if (outbuflen == NULL)
		return SRD_ERR_ARGS; /* TODO: More specific error? */

	/* TODO: Error handling. */
	py_mod = dec->py_mod;
	Py_XINCREF(py_mod);
	py_func = dec->py_func;
	Py_XINCREF(py_func);

	/* Create a Python tuple of size 1. */
	if (!(py_args = PyTuple_New(1))) { /* NEWREF */
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_run_decref_func;
	}

	/* Get the input buffer as Python "string" (byte array). */
	/* TODO: int vs. uint64_t for 'inbuflen'? */
	if (!(py_value = Py_BuildValue("s#", inbuf, inbuflen))) { /* NEWREF */
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_run_decref_args;
	}

	/*
	 * IMPORTANT: PyTuple_SetItem() "steals" a reference to py_value!
	 * That means we are no longer responsible for Py_XDECREF()'ing it.
	 * It will automatically be free'd when the 'py_args' tuple is free'd.
	 */
	if (PyTuple_SetItem(py_args, 0, py_value) != 0) { /* STEAL */
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		Py_XDECREF(py_value); /* TODO: Ref. stolen upon error? */
		goto err_run_decref_args;
	}

	if (!(py_res = PyObject_CallObject(py_func, py_args))) { /* NEWREF */
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_run_decref_args;
	}

	if ((r = PyObject_AsCharBuffer(py_res, (const char **)outbuf,
				      (Py_ssize_t *)outbuflen))) {
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		Py_XDECREF(py_res);
		goto err_run_decref_args;
	}

	ret = SRD_OK;

	Py_XDECREF(py_res);

err_run_decref_args:
	Py_XDECREF(py_args);
err_run_decref_func:
	Py_XDECREF(py_func);
	Py_XDECREF(py_mod);

	if (PyErr_Occurred())
		PyErr_Print(); /* Returns void. */

	return ret;
}

/**
 * TODO
 */
static int srd_unload_decoder(struct srd_decoder *dec)
{
	g_free(dec->id);
	g_free(dec->name);
	g_free(dec->desc);
	g_free(dec->func);

	/* TODO: Free everything in inputformats and outputformats. */

	if (dec->inputformats != NULL)
		g_slist_free(dec->inputformats);
	if (dec->outputformats != NULL)
		g_slist_free(dec->outputformats);

	Py_XDECREF(dec->py_func);
	Py_XDECREF(dec->py_mod);

	return SRD_OK;
}

/**
 * TODO
 */
static int srd_unload_all_decoders(void)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_list_decoders(); l; l = l->next) {
		dec = l->data;
		/* TODO: Error handling. */
		srd_unload_decoder(dec);
	}

	return SRD_OK;
}

/**
 * Shutdown libsigrokdecode.
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
