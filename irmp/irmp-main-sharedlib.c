/*
 * irmp-main-sharedlib.c
 *
 * Copyright (c) 2009-2019 Frank Meyer - frank(at)fli4l.de
 * Copyright (c) 2009-2019 René Staffen - r.staffen(at)gmx.de
 * Copyright (c) 2020-2021 Gerhard Sittig <gerhard.sittig@gmx.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

/*
 * Declare the library's public API first. Prove it's consistent and
 * complete as a standalone header file.
 */
#include "irmp-main-sharedlib.h"

#include <errno.h>
#include <glib.h>
#include <Python.h>
#include <stdlib.h>
#include <string.h>

/*
 * Include the IRMP core logic. This approach is required because of
 * static variables which hold internal state. The core logic started
 * as an MCU project where resources are severely constrained.
 *
 * This libsigrokdecode incarnation of IRMP will always be used in the
 * UNIX_OR_WINDOWS configuration. But libtool(1) breaks the upstream
 * logic's platform detection. Check reliably available conditions here
 * and provide expected symbols to the library, to reduce changes to the
 * upstream project.
 */
#if defined _WIN32
#  if !defined WIN32
#    define WIN32
#  endif
#else
#  if !defined unix
#    define unix
#  endif
#endif
#include "irmp.h"
#include "irmp.c"

/*
 * The remaining source code implements the PC library, which accepts
 * sample data from API callers, and provides detector results as they
 * become available after seeing input data.
 *
 * TODO items, known constraints
 * - Counters in the IRMP core logic and the library wrapper are 32bit
 *   only. In the strictest sense they only need to cover the span of
 *   an IR frame. In the PC side library case they need to cover "a
 *   detection phase", which happens to be under calling applications'
 *   control. The library shall not mess with the core's internal state,
 *   and may even not be able to reliably tell whether detection of a
 *   frame started in the core. Fortunately the 32bit counters only roll
 *   over after some 2.5 days at the highest available sample rate. So
 *   this limitation is not a blocker.
 * - The IRMP core keeps internal state in global variables. Which is
 *   appropriate for MCU configurations. For the PC library use case
 *   this constraint prevents concurrency, only a single data stream
 *   can get processed at any time. This limitation can get addressed
 *   later, making the flexible and featureful IRMP detection available
 *   in the first place is considered highly desirable, and is a great
 *   improvement in itself.
 * - The detection of IR frames from buffered data is both limited and
 *   complicated at the same time. The routine re-uses the caller's
 *   buffer _and_ internal state across multiple calls. Thus windowed
 *   operation over a larger set of input data is not available. The
 *   API lacks a flag for failed detection, thus applications need to
 *   guess from always returned payload data.
 * - Is it worth adding a "detection in progress" query to the API? Is
 *   the information available to the library wrapper, and reliable?
 *   Shall applications be able to "poll" the started, and completed
 *   state for streamed operation including periodic state resets which
 *   won't interfere with pending detection? (It's assumed that this
 *   is only required when feeding single values in individual calls is
 *   found to be rather expensive.
 * - Some of the result data reflects the core's internal presentation
 *   while there is no declaration in the library's API. This violates
 *   API layers, and needs to get addressed properly.
 * - The IRMP core logic (strictly speaking the specific details of
 *   preprocessor symbol arrangements in the current implementation)
 *   appears to assume either to run on an MCU and capture IR signals
 *   from hardware pins, falling back to AVR if no other platform got
 *   detected. Or assumes to run on a (desktop) PC, and automatically
 *   enables ANALYZE mode, which results in lots of stdio traffic that
 *   is undesirable for application code which uses the shared library
 *   for strict detection purposes but no further analysis or research.
 *   It's a pity that turning off ANALYZE switches to MCU mode, and that
 *   keeping ANALYZE enabled but silencing the output is rather messy
 *   and touches the innards of the core logic (the irmp.c source file
 *   and its dependency header files).
 */

#ifndef ARRAY_SIZE
#  define ARRAY_SIZE(x) (sizeof(x) / sizeof(x[0]))
#endif

static int irmp_lib_initialized;
static size_t irmp_lib_client_id;
static GMutex irmp_lib_mutex;

struct irmp_instance {
	size_t client_id;
	GMutex *mutex;
};

static void irmp_lib_autoinit(void)
{
	if (irmp_lib_initialized)
		return;

	irmp_lib_client_id = 0;
	g_mutex_init(&irmp_lib_mutex);

	irmp_lib_initialized = 1;
}

static size_t irmp_next_client_id(void)
{
	size_t id;

	do {
		id = ++irmp_lib_client_id;
	} while (!id);

	return id;
}

IRMP_DLLEXPORT struct irmp_instance *irmp_instance_alloc(void)
{
	struct irmp_instance *inst;

	irmp_lib_autoinit();

	inst = g_malloc0(sizeof(*inst));
	if (!inst)
		return NULL;

	inst->client_id = irmp_next_client_id();
	inst->mutex = &irmp_lib_mutex;

	return inst;
}

IRMP_DLLEXPORT void irmp_instance_free(struct irmp_instance *state)
{

	irmp_lib_autoinit();

	if (!state)
		return;

	g_free(state);
}

IRMP_DLLEXPORT size_t irmp_instance_id(struct irmp_instance *state)
{

	irmp_lib_autoinit();

	return state ? state->client_id : 0;
}

IRMP_DLLEXPORT int irmp_instance_lock(struct irmp_instance *state, int wait)
{
	int rc;
	PyGILState_STATE pyst;

	irmp_lib_autoinit();

	if (!state || !state->mutex)
		return -EINVAL;

	pyst = PyGILState_Ensure();
	Py_BEGIN_ALLOW_THREADS
	if (wait) {
		g_mutex_lock(state->mutex);
		rc = 0;
	} else {
		rc = g_mutex_trylock(state->mutex);
	}
	Py_END_ALLOW_THREADS
	PyGILState_Release(pyst);
	if (rc != 0)
		return rc;

	return 0;
}

IRMP_DLLEXPORT void irmp_instance_unlock(struct irmp_instance *state)
{

	irmp_lib_autoinit();

	if (!state || !state->mutex)
		return;

	g_mutex_unlock(state->mutex);
}

static uint32_t s_end_sample;

IRMP_DLLEXPORT uint32_t irmp_get_sample_rate(void)
{
	return F_INTERRUPTS;
}

IRMP_DLLEXPORT void irmp_reset_state(void)
{
	size_t i;
	IRMP_DATA data;

	/*
	 * Provide the equivalent of 1s idle input signal level. Then
	 * drain any potentially accumulated result data. This clears
	 * the internal decoder state.
	 */
	IRMP_PIN = 0xff;
	i = F_INTERRUPTS;
	while (i-- > 0) {
		(void)irmp_ISR();
	}
	(void)irmp_get_data(&data);

	time_counter = 0;
	s_startBitSample = 0;
	s_curSample = 0;
	s_end_sample = 0;

	/*
	 * TODO This is not the most appropriate location to control the
	 * core logic's verbosity. But out of the public set of library
	 * routines this call is closest to some initialization routine.
	 * The query for compile time parameter values is optional, the
	 * state reset is not. Multiple verbosity setup activities in
	 * the same program lifetime won't harm. This HACK is clearly
	 * preferrable over more fiddling with core logic innards, or
	 * the introduction of yet another DLL routine.
	 */
	silent = 1;
	verbose = 0;
}

IRMP_DLLEXPORT int irmp_add_one_sample(int sample)
{
	int ret;

	IRMP_PIN = sample ? 0xff : 0x00;
	ret = irmp_ISR() ? 1 : 0;
	s_end_sample = s_curSample++;
	return ret;
}

IRMP_DLLEXPORT int irmp_get_result_data(struct irmp_result_data *data)
{
	IRMP_DATA d;

	if (!irmp_get_data(&d))
		return 0;

	data->address = d.address;
	data->command = d.command;
	data->protocol = d.protocol;
	data->protocol_name = irmp_get_protocol_name(d.protocol);
	data->flags = d.flags;
	data->start_sample = s_startBitSample;
	data->end_sample = s_end_sample;
	return 1;
}

#if WITH_IRMP_DETECT_BUFFER
IRMP_DLLEXPORT struct irmp_result_data irmp_detect_buffer(const uint8_t *buff, size_t len)
{
	struct irmp_result_data ret;

	memset(&ret, 0, sizeof(ret));
	while (s_curSample < len) {
		if (irmp_add_one_sample(buff[s_curSample])) {
			irmp_get_result_data(&ret);
			return ret;
		}
	}
	return ret;
}
#endif

IRMP_DLLEXPORT const char *irmp_get_protocol_name(uint32_t protocol)
{
	const char *name;

	if (protocol >= ARRAY_SIZE(irmp_protocol_names))
		return "unknown";
	name = irmp_protocol_names[protocol];
	if (!name || !*name)
		return "unknown";
	return name;
}

static __attribute__((constructor)) void init(void)
{
	irmp_lib_autoinit();
}
