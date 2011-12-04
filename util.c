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


/**
 * Helper function to handle Python strings.
 *
 * TODO: @param entries.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *         The 'outstr' argument points to a malloc()ed string upon success.
 */
int h_str(PyObject *py_res, PyObject *py_mod, const char *key, char **outstr)
{
	PyObject *py_str;
	char *str;
	int ret;

	py_str = PyObject_GetAttrString(py_res, (char *)key); /* NEWREF */
	if (!py_str || !PyString_Check(py_str)) {
		ret = SRD_ERR_PYTHON; /* TODO: More specific error? */
		goto err_h_decref_mod;
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
err_h_decref_mod:
	Py_XDECREF(py_mod);

	if (PyErr_Occurred())
		PyErr_Print(); /* Returns void. */

	return ret;
}

