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

#include <sigrokdecode.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <stdio.h>
#include <string.h>
#include <dirent.h>
#include <config.h>

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
 *  - If it returns a "new reference", you're responsible to Py_DECREF() it.
 *
 *  - If it returns a "borrowed reference", you MUST NOT Py_DECREF() it.
 *
 *  - If a function "steals" a reference, you no longer are responsible for
 *    Py_DECREF()ing it (someone else will do it for you at some point).
 */

/**
 * Initialize libsigrokdecode.
 *
 * @return SIGROKDECODE_OK upon success, a (negative) error code otherwise.
 */
int sigrokdecode_init(void)
{
	DIR *dir;
	struct dirent *dp;
	char *tmp;

	/* Py_Initialize() returns void and usually cannot fail. */
	Py_Initialize();

	/* Add search directory for the protocol decoders. */
	/* FIXME: Check error code. */
	/* FIXME: What happens if this function is called multiple times? */
	PyRun_SimpleString("import sys;"
			   "sys.path.append(r'" DECODERS_DIR "');");

	if (!(dir = opendir(DECODERS_DIR)))
		return SIGROKDECODE_ERR_DECODERS_DIR;

	while ((dp = readdir(dir)) != NULL) {
		if (!g_str_has_suffix(dp->d_name, ".py"))
			continue;
		/* For now use the filename (without .py) as decoder name. */
		if ((tmp = g_strndup(dp->d_name, strlen(dp->d_name) - 3)))
			list_pds = g_slist_append(list_pds, tmp);
	}
	closedir(dir);

	return SIGROKDECODE_OK;
}

/**
 * Returns the list of supported/loaded protocol decoders.
 *
 * This is a GSList containing the names of the decoders as strings.
 *
 * @return List of decoders, NULL if none are supported or loaded.
 */
GSList *sigrokdecode_list_decoders(void)
{
	return list_pds;
}

/**
 * Helper function to handle Python strings.
 *
 * TODO: @param entries.
 *
 * @return SIGROKDECODE_OK upon success, a (negative) error code otherwise.
 *         The 'outstr' argument points to a malloc()ed string upon success.
 */
static int h_str(PyObject *py_res, PyObject *py_func, PyObject *py_mod,
		 const char *key, char **outstr)
{
	PyObject *py_str;
	char *str;

	py_str = PyMapping_GetItemString(py_res, (char *)key);
	if (!py_str || !PyString_Check(py_str)) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	/*
	 * PyString_AsString()'s returned string refers to an internal buffer
	 * (not a copy), i.e. the data must not be modified, and the memory
	 * must not be free()'d.
	 */
	if (!(str = PyString_AsString(py_str))) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_DECREF(py_str);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	if (!(*outstr = strdup(str))) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_DECREF(py_str);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_MALLOC;
	}

	Py_DECREF(py_str);

	return SIGROKDECODE_OK;
}

/**
 * TODO
 *
 * @param name TODO
 *
 * @return SIGROKDECODE_OK upon success, a (negative) error code otherwise.
 */
int sigrokdecode_load_decoder(const char *name,
			      struct sigrokdecode_decoder **dec)
{
	struct sigrokdecode_decoder *d;
	PyObject *py_name, *py_mod, *py_func, *py_res /* , *py_tuple */;
	int r;

	/* Get the name of the decoder module as Python string. */
	if (!(py_name = PyString_FromString(name))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* "Import" the Python module. */
	if (!(py_mod = PyImport_Import(py_name))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_name);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}
	Py_DECREF(py_name);

	/* Get the 'register' function name as Python callable object. */
	py_func = PyObject_GetAttrString(py_mod, "register"); /* NEWREF */
	if (!py_func || !PyCallable_Check(py_func)) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* Call the 'register' function without arguments, get the result. */
	if (!(py_res = PyObject_CallFunction(py_func, NULL))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	if (!(d = malloc(sizeof(struct sigrokdecode_decoder))))
		return SIGROKDECODE_ERR_MALLOC;

	if ((r = h_str(py_res, py_func, py_mod, "id", &(d->id))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "name", &(d->name))) < 0)
		return r;

	if ((r = h_str(py_res, py_func, py_mod, "desc", &(d->desc))) < 0)
		return r;

	d->py_mod = py_mod;

	Py_DECREF(py_res);
	Py_DECREF(py_func);

	/* Get the 'decode' function name as Python callable object. */
	py_func = PyObject_GetAttrString(py_mod, "decode"); /* NEWREF */
	if (!py_func || !PyCallable_Check(py_func)) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	d->py_func = py_func;

	/* TODO: Handle inputformats, outputformats. */

	*dec = d;

	return SIGROKDECODE_OK;
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
 * @return SIGROKDECODE_OK upon success, a (negative) error code otherwise.
 */
int sigrokdecode_run_decoder(struct sigrokdecode_decoder *dec,
			     uint8_t *inbuf, uint64_t inbuflen,
			     uint8_t **outbuf, uint64_t *outbuflen)
{
	PyObject *py_mod, *py_func, *py_args, *py_value, *py_res;
	int ret;

	/* TODO: Use #defines for the return codes. */

	/* Return an error upon unusable input. */
	if (dec == NULL)
		return SIGROKDECODE_ERR_ARGS; /* TODO: More specific error? */
	if (inbuf == NULL)
		return SIGROKDECODE_ERR_ARGS; /* TODO: More specific error? */
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return SIGROKDECODE_ERR_ARGS; /* TODO: More specific error? */
	if (outbuf == NULL)
		return SIGROKDECODE_ERR_ARGS; /* TODO: More specific error? */
	if (outbuflen == NULL)
		return SIGROKDECODE_ERR_ARGS; /* TODO: More specific error? */

	/* TODO: Error handling. */
	py_mod = dec->py_mod;
	Py_INCREF(py_mod);
	py_func = dec->py_func;
	Py_INCREF(py_func);

	/* Create a Python tuple of size 1. */
	if (!(py_args = PyTuple_New(1))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* Get the input buffer as Python "string" (byte array). */
	/* TODO: int vs. uint64_t for 'inbuflen'? */
	if (!(py_value = Py_BuildValue("s#", inbuf, inbuflen))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	/*
	 * IMPORTANT: PyTuple_SetItem() "steals" a reference to py_value!
	 * That means we are no longer responsible for Py_DECREF()'ing it.
	 * It will automatically be free'd when the 'py_args' tuple is free'd.
	 */
	if (PyTuple_SetItem(py_args, 0, py_value) != 0) { /* STEAL */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_value); /* TODO: Ref. stolen upon error? */
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	if (!(py_res = PyObject_CallObject(py_func, py_args))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	if ((ret = PyObject_AsCharBuffer(py_res, (const char **)outbuf,
					 (Py_ssize_t *)outbuflen))) {
		PyErr_Print(); /* Returns void. */
		Py_DECREF(py_res);
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_mod);
		return SIGROKDECODE_ERR_PYTHON; /* TODO: More specific error? */
	}

	Py_DECREF(py_res);
	Py_DECREF(py_args);
	Py_DECREF(py_func);
	Py_DECREF(py_mod);

	return SIGROKDECODE_OK;
}

/**
 * Shutdown libsigrokdecode.
 *
 * @return SIGROKDECODE_OK upon success, a (negative) error code otherwise.
 */
int sigrokdecode_shutdown(void)
{
	/* Py_Finalize() returns void, any finalization errors are ignored. */
	Py_Finalize();

	return SIGROKDECODE_OK;
}
