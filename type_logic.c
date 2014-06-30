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

#include "libsigrokdecode-internal.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode.h"
#include "config.h"
#include <inttypes.h>
#include <string.h>

static PyObject *srd_logic_iter(PyObject *self)
{
	return self;
}

static PyObject *srd_logic_iternext(PyObject *self)
{
	srd_logic *logic;
	PyObject *py_samplenum, *py_samples;
	uint8_t *sample_pos, sample;
	int byte_offset, bit_offset, i;

	logic = (srd_logic *)self;
	if (logic->itercnt >= logic->inbuflen / logic->di->data_unitsize) {
		/* End iteration loop. */
		return NULL;
	}

	/*
	 * Convert the bit-packed sample to an array of bytes, with only 0x01
	 * and 0x00 values, so the PD doesn't need to do any bitshifting.
	 */
	sample_pos = logic->inbuf + logic->itercnt * logic->di->data_unitsize;
	for (i = 0; i < logic->di->dec_num_channels; i++) {
		/* A channelmap value of -1 means "unused optional channel". */
		if (logic->di->dec_channelmap[i] == -1) {
			/* Value of unused channel is 0xff, instead of 0 or 1. */
			logic->di->channel_samples[i] = 0xff;
		} else {
			byte_offset = logic->di->dec_channelmap[i] / 8;
			bit_offset = logic->di->dec_channelmap[i] % 8;
			sample = *(sample_pos + byte_offset) & (1 << bit_offset) ? 1 : 0;
			logic->di->channel_samples[i] = sample;
		}
	}

	/* Prepare the next samplenum/sample list in this iteration. */
	py_samplenum =
	    PyLong_FromUnsignedLongLong(logic->start_samplenum +
					logic->itercnt);
	PyList_SetItem(logic->sample, 0, py_samplenum);
	py_samples = PyBytes_FromStringAndSize((const char *)logic->di->channel_samples,
					       logic->di->dec_num_channels);
	PyList_SetItem(logic->sample, 1, py_samples);
	Py_INCREF(logic->sample);
	logic->itercnt++;

	return logic->sample;
}

/** @cond PRIVATE */
SRD_PRIV PyTypeObject srd_logic_type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name = "srd_logic",
	.tp_basicsize = sizeof(srd_logic),
	.tp_flags = Py_TPFLAGS_DEFAULT,
	.tp_doc = "Sigrokdecode logic sample object",
	.tp_iter = srd_logic_iter,
	.tp_iternext = srd_logic_iternext,
};
/** @endcond */
