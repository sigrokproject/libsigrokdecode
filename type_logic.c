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
#include <inttypes.h>
#include <string.h>

static PyObject *srd_logic_iter(PyObject *self)
{
	return self;
}

static PyObject *srd_logic_iternext(PyObject *self)
{
	int i;
	PyObject *py_samplenum, *py_samples;
	srd_logic *logic;
	uint64_t sample;
	uint8_t probe_samples[SRD_MAX_NUM_PROBES + 1];

	logic = (srd_logic *)self;
	if (logic->itercnt >= logic->inbuflen / logic->di->data_unitsize) {
		/* End iteration loop. */
		return NULL;
	}

	/*
	 * Convert the bit-packed sample to an array of bytes, with only 0x01
	 * and 0x00 values, so the PD doesn't need to do any bitshifting.
	 */

	/* Get probe bits into the 'sample' variable. */
	memcpy(&sample,
	       logic->inbuf + logic->itercnt * logic->di->data_unitsize,
	       logic->di->data_unitsize);

	/* All probe values (required + optional) are pre-set to 42. */
	memset(probe_samples, 42, logic->di->dec_num_probes);
	/* TODO: None or -1 in Python would be better. */

	/*
	 * Set probe values of specified/used probes to their resp. values.
	 * Unused probe values (those not specified by the user) remain at 42.
	 */
	for (i = 0; i < logic->di->dec_num_probes; i++) {
		/* A probemap value of -1 means "unused optional probe". */
		if (logic->di->dec_probemap[i] == -1)
			continue;
		probe_samples[i] = sample & (1 << logic->di->dec_probemap[i]) ? 1 : 0;
	}

	/* Prepare the next samplenum/sample list in this iteration. */
	py_samplenum =
	    PyLong_FromUnsignedLongLong(logic->start_samplenum +
					logic->itercnt);
	PyList_SetItem(logic->sample, 0, py_samplenum);
	py_samples = PyBytes_FromStringAndSize((const char *)probe_samples,
					       logic->di->dec_num_probes);
	PyList_SetItem(logic->sample, 1, py_samples);
	Py_INCREF(logic->sample);
	logic->itercnt++;

	return logic->sample;
}

SRD_PRIV PyTypeObject srd_logic_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "srd_logic",
	.tp_basicsize = sizeof(srd_logic),
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_doc = "Sigrokdecode logic sample object",
	.tp_iter = srd_logic_iter,
	.tp_iternext = srd_logic_iternext,
};
