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

/**
 * Initialize libsigrokdecode.
 *
 * @return 0 upon success, non-zero otherwise.
 */
int sigrokdecode_init(void)
{
	/* Py_Initialize() returns void and usually cannot fail. */
	Py_Initialize();

	/* Add some more search directories for convenience. */
	/* FIXME: Check error code. */
	PyRun_SimpleString(
		"import sys;"
		"sys.path.append('libsigrokdecode/scripts');"
		"sys.path.append('../libsigrokdecode/scripts');"
		"sys.path.append('/usr/local/share/sigrok');"
		);

	return 0;
}

/**
 * TODO
 *
 * @param name TODO
 * @return 0 upon success, non-zero otherwise.
 */
int sigrokdecode_load_decoder_file(const char *name)
{
	/* QUICK HACK */
	name = name;

	/* TODO */
	return 0;
}

/**
 * Run the specified decoder function.
 *
 * @param decodername TODO
 * @param inbuf TODO
 * @param inbuflen TODO
 * @param outbuf TODO
 * @param outbuflen TODO
 * @return 0 upon success, non-zero otherwise.
 */
int sigrokdecode_run_decoder(const char *decodername, uint8_t *inbuf,
			     uint64_t inbuflen, uint8_t **outbuf,
			     uint64_t *outbuflen)
{
	const char *decoder_filename = "transitioncounter"; /* FIXME */
	// const char *decoder_filename = "i2c"; /* FIXME */
	PyObject *py_name, *py_module, *py_func, *py_args;
	PyObject *py_value, *py_result;
	int ret;

	/* TODO: Use #defines for the return codes. */

	/* Return an error upon unusable input. */
	if (decodername == NULL)
		return -1;
	if (inbuf == NULL)
		return -2;
	if (inbuflen == 0) /* No point in working on empty buffers. */
		return -3;
	if (outbuf == NULL)
		return -4;
	if (outbuflen == NULL)
		return -5;

	/* Get the name of the decoder module/file as Python string. */
	if (!(py_name = PyString_FromString(decoder_filename))) {
		PyErr_Print();
		return -6;
	}

	/* "Import" the python file/module. */
	if (!(py_module = PyImport_Import(py_name))) {
		PyErr_Print();
		Py_DECREF(py_name);
		return -7;
	}
	Py_DECREF(py_name);

	/* Get the decoder/function name as Python callable object. */
	py_func = PyObject_GetAttrString(py_module, decodername);
	if (!py_func || !PyCallable_Check(py_func)) {
		if (PyErr_Occurred())
			PyErr_Print();
		Py_DECREF(py_module);
		return -8;
	}

	/* Create a Python tuple of size 1. */
	if (!(py_args = PyTuple_New(1))) {
		PyErr_Print();
		Py_DECREF(py_func);
		Py_DECREF(py_module);
		return -9;
	}

	/* Get the input buffer as Python "string" (byte array). */
	/* TODO: int vs. uint64_t for 'inbuflen'? */
	if (!(py_value = Py_BuildValue("s#", inbuf, inbuflen))) {
		PyErr_Print();
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_module);
		return -10;
	}

	if (PyTuple_SetItem(py_args, 0, py_value) != 0) {
		PyErr_Print();
		Py_DECREF(py_value);
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_module);
		return -11;
	}

	if (!(py_result = PyObject_CallObject(py_func, py_args))) {
		PyErr_Print();
		Py_DECREF(py_value);
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_module);
		return -12;
	}

	if ((ret = PyObject_AsCharBuffer(py_result, (const char **)outbuf,
					 (Py_ssize_t *)outbuflen))) {
		PyErr_Print();
		Py_DECREF(py_result);
		Py_DECREF(py_value);
		Py_DECREF(py_args);
		Py_DECREF(py_func);
		Py_DECREF(py_module);
		return -13;
	}

	Py_DECREF(py_result);
	// Py_DECREF(py_value);
	Py_DECREF(py_args);
	Py_DECREF(py_func);
	Py_DECREF(py_module);

	return 0;
}

/**
 * Shutdown libsigrokdecode.
 *
 * @return 0 upon success, non-zero otherwise.
 */
int sigrokdecode_shutdown(void)
{
	/* Py_Finalize() returns void, any finalization errors are ignored. */
	Py_Finalize();

	return 0;
}
