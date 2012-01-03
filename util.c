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
#include "sigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */


/**
 * Helper function to get the value of a python object's attribute,
 * returned as a newly allocated char *.
 *
 * @param py_obj The object to probe.
 * @param key Name of the attribute to retrieve.
 * @param outstr ptr to char * storage to be filled in.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *         The 'outstr' argument points to a malloc()ed string upon success.
 */
int h_str(PyObject *py_obj, const char *key, char **outstr)
{
	PyObject *py_str, *py_encstr;
	char *str;
	int ret;

	py_str = py_encstr = NULL;
	str = NULL;
	ret = SRD_OK;

	if (!(py_str = PyObject_GetAttrString(py_obj, (char *)key))) {
		/* TODO: log level 4 debug message */
		ret = SRD_ERR_PYTHON;
		goto err_out;
	}

	if (!(py_encstr = PyUnicode_AsEncodedString(py_str, "utf-8", NULL))) {
		/* TODO: log level 4 debug message */
		ret = SRD_ERR_PYTHON;
		goto err_out;
	}
	if (!(str = PyBytes_AS_STRING(py_encstr))) {
		/* TODO: log level 4 debug message */
		ret = SRD_ERR_PYTHON;
		goto err_out;
	}

	if (!(*outstr = g_strdup(str))) {
		/* TODO: log level 4 debug message */
		ret = SRD_ERR_MALLOC;
		goto err_out;
	}

err_out:
	if (py_str)
		Py_XDECREF(py_str);
	if (py_encstr)
		Py_XDECREF(py_encstr);

	if (PyErr_Occurred())
		PyErr_Print();

	return ret;
}

