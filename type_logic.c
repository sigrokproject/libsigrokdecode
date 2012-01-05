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


PyObject *srd_logic_iter(PyObject *self)
{

	return self;
}

PyObject *srd_logic_iternext(PyObject *self)
{
	PyObject *py_samplenum, *py_samples;
	srd_logic *logic;
	uint64_t sample;
	int i;
	unsigned char probe_samples[SRD_MAX_NUM_PROBES];

	logic = (srd_logic *) self;
	if (logic->itercnt >= logic->inbuflen / logic->di->unitsize) {
		/* End iteration loop. */
		return NULL;
	}

	/* TODO: use number of probes defined in the PD, in the order the PD
	 * defined them -- not whatever came in from the driver.
	 */
	/* Convert the bit-packed sample to an array of bytes, with only 0x01
	 * and 0x00 values, so the PD doesn't need to do any bitshifting.
	 */
	memcpy(&sample, logic->inbuf + logic->itercnt * logic->di->unitsize,
			logic->di->unitsize);
	for (i = 0; i < logic->di->num_probes; i++) {
		probe_samples[i] = sample & 0x01;
		sample >>= 1;
	}

	/* TODO: samplenum should be in the inbuf feed, instead of time/duration.
	 * fake it for now...
	 */
	/* Prepare the next samplenum/sample list in this iteration. */
	py_samplenum = PyLong_FromUnsignedLongLong(logic->itercnt++);
	PyList_SetItem(logic->sample, 0, py_samplenum);
	py_samples = PyBytes_FromStringAndSize((const char *)probe_samples,
			logic->di->num_probes);
	PyList_SetItem(logic->sample, 1, py_samples);
	Py_INCREF(logic->sample);

	return logic->sample;
}

PyTypeObject srd_logic_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "srd_logic",
	.tp_basicsize = sizeof(srd_logic),
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_doc = "Sigrokdecode logic sample object",
	.tp_iter = srd_logic_iter,
	.tp_iternext = srd_logic_iternext,
};

