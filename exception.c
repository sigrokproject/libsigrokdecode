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
#include <stdarg.h>
#include <glib.h>

static char *py_stringify(PyObject *py_obj)
{
	PyObject *py_str, *py_bytes;
	char *str = NULL;

	/* Note: Caller already ran PyGILState_Ensure(). */

	if (!py_obj)
		return NULL;

	py_str = PyObject_Str(py_obj);
	if (!py_str || !PyUnicode_Check(py_str))
		goto cleanup;

	py_bytes = PyUnicode_AsUTF8String(py_str);
	if (!py_bytes)
		goto cleanup;

	str = g_strdup(PyBytes_AsString(py_bytes));
	Py_DECREF(py_bytes);

cleanup:
	Py_XDECREF(py_str);
	if (!str) {
		PyErr_Clear();
		srd_dbg("Failed to stringify object.");
	}
	return str;
}

static char *py_get_string_attr(PyObject *py_obj, const char *attr)
{
	PyObject *py_str, *py_bytes;
	char *str = NULL;

	/* Note: Caller already ran PyGILState_Ensure(). */

	if (!py_obj)
		return NULL;

	py_str = PyObject_GetAttrString(py_obj, attr);
	if (!py_str || !PyUnicode_Check(py_str))
		goto cleanup;

	py_bytes = PyUnicode_AsUTF8String(py_str);
	if (!py_bytes)
		goto cleanup;

	str = g_strdup(PyBytes_AsString(py_bytes));
	Py_DECREF(py_bytes);

cleanup:
	Py_XDECREF(py_str);
	if (!str) {
		PyErr_Clear();
		srd_dbg("Failed to get object attribute %s.", attr);
	}
	return str;
}

/** @private */
SRD_PRIV void srd_exception_catch(const char *format, ...)
{
	va_list args;
	PyObject *py_etype, *py_evalue, *py_etraceback;
	PyObject *py_mod, *py_func, *py_tracefmt;
	char *msg, *etype_name, *evalue_str, *tracefmt_str;
	const char *etype_name_fallback;
	PyGILState_STATE gstate;

	py_etype = py_evalue = py_etraceback = py_mod = py_func = NULL;

	va_start(args, format);
	msg = g_strdup_vprintf(format, args);
	va_end(args);

	gstate = PyGILState_Ensure();

	PyErr_Fetch(&py_etype, &py_evalue, &py_etraceback);
	if (!py_etype) {
		/* No current exception, so just print the message. */
		srd_err("%s.", msg);
		goto cleanup;
	}
	PyErr_NormalizeException(&py_etype, &py_evalue, &py_etraceback);

	etype_name = py_get_string_attr(py_etype, "__name__");
	evalue_str = py_stringify(py_evalue);
	etype_name_fallback = (etype_name) ? etype_name : "(unknown exception)";

	if (evalue_str)
		srd_err("%s: %s: %s", etype_name_fallback, msg, evalue_str);
	else
		srd_err("%s: %s.", etype_name_fallback, msg);

	g_free(evalue_str);
	g_free(etype_name);

	/* If there is no traceback object, we are done. */
	if (!py_etraceback)
		goto cleanup;

	py_mod = py_import_by_name("traceback");
	if (!py_mod)
		goto cleanup;

	py_func = PyObject_GetAttrString(py_mod, "format_exception");
	if (!py_func || !PyCallable_Check(py_func))
		goto cleanup;

	/* Call into Python to format the stack trace. */
	py_tracefmt = PyObject_CallFunctionObjArgs(py_func,
			py_etype, py_evalue, py_etraceback, NULL);
	if (!py_tracefmt)
		goto cleanup;

	tracefmt_str = py_stringify(py_tracefmt);
	Py_DECREF(py_tracefmt);

	/* Log the detailed stack trace. */
	if (tracefmt_str) {
		srd_dbg("%s", tracefmt_str);
		g_free(tracefmt_str);
	}

cleanup:
	Py_XDECREF(py_func);
	Py_XDECREF(py_mod);
	Py_XDECREF(py_etraceback);
	Py_XDECREF(py_evalue);
	Py_XDECREF(py_etype);

	/* Just in case. */
	PyErr_Clear();

	PyGILState_Release(gstate);

	g_free(msg);
}
