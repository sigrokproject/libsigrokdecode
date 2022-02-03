/*
 * irmp-main-sharedlib.h
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

#ifndef IRMP_SHAREDLIB_H
#define IRMP_SHAREDLIB_H

#include <stdint.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Export the public API routines. */
#ifndef IRMP_DLLEXPORT
#  if defined WIN32 && defined _MSC_VER
#    define IRMP_DLLEXPORT __declspec(dllexport)
#  else
#    define IRMP_DLLEXPORT __attribute__((visibility("default")))
#  endif
#endif

/* Part of the library API is optional. */
#define WITH_IRMP_DETECT_BUFFER 0

/**
 * @brief State container for a decoder core instance. Opaque to clients.
 */
struct irmp_instance;

/**
 * @brief Allocate a decoder instance.
 *
 * @returns Reference to the allocated instance state.
 */
IRMP_DLLEXPORT struct irmp_instance *irmp_instance_alloc(void);

/**
 * @brief Release a decoder instance.
 *
 * @param[in] state Reference to the instance's state.
 */
IRMP_DLLEXPORT void irmp_instance_free(struct irmp_instance *state);

/**
 * @brief Get the client ID of an IRMP decoder core instance.
 */
IRMP_DLLEXPORT size_t irmp_instance_id(struct irmp_instance *state);

/**
 * @brief Acquire a decoder instance's lock.
 *
 * @param[in] state Reference to the instance's state.
 * @param[in] wait Whether to block until the lock is acquired.
 *
 * @returns 0 upon success, non-zero upon failure
 */
IRMP_DLLEXPORT int irmp_instance_lock(struct irmp_instance *state, int wait);

/**
 * @brief Release a decoder instance's lock.
 *
 * @param[in] state Reference to the instance's state.
 *
 * @returns 0 upon success, non-zero upon failure
 */
IRMP_DLLEXPORT void irmp_instance_unlock(struct irmp_instance *state);

/**
 * @brief IR decoder result data at the library's public API.
 */
struct irmp_result_data {
	uint32_t protocol;	/**!< protocol, e.g. NEC_PROTOCOL */
	const char *protocol_name;	/**!< name of the protocol */
	uint32_t address;	/**!< address */
	uint32_t command;	/**!< command */
	uint32_t flags;		/**!< flags currently only repetition (bit 0) */
	uint32_t start_sample;	/**!< the sampleindex there the detected command started */
	uint32_t end_sample;	/**!< the sampleindex there the detected command ended */
};

#define IRMP_DATA_FLAG_REPETITION	(1 << 0)
#define IRMP_DATA_FLAG_RELEASE		(1 << 1)

/**
 * @brief Query the IRMP library's configured sample rate.
 *
 * The internally used sample rate is a compile time option. Any data
 * that is provided at runtime needs to match this rate, or detection
 * will fail.
 */
IRMP_DLLEXPORT uint32_t irmp_get_sample_rate(void);

/**
 * @brief Reset internal decoder state.
 *
 * This must be called before data processing starts.
 */
IRMP_DLLEXPORT void irmp_reset_state(void);

/**
 * @brief Feed an individual sample to the detector.
 *
 * See @ref irmp_get_result_data() for result retrieval when detection
 * of an IR frame completes. Make sure @ref irmp_reset_state() was
 * called before providing the first sample.
 *
 * @param[in] sample The pin value to feed to the detector.
 *
 * @returns Non-zero when an IR frame was detected.
 */
IRMP_DLLEXPORT int irmp_add_one_sample(int sample);

#if WITH_IRMP_DETECT_BUFFER
/**
 * @brief Process the given buffer until an IR frame is found.
 *
 * Stops at the first detected IR frame, and returns its data. Subsequent
 * calls resume processing at the previously stopped position. Make sure
 * @ref irmp_reset_state() was called before the first detect call.
 *
 * @param[in] buf Pointer to the data buffer.
 * @param[in] len Number of samples in the Buffer.
 */
IRMP_DLLEXPORT struct irmp_result_data irmp_detect_buffer(const uint8_t *buf, size_t len);
#endif

/**
 * @brief Query result data after detection succeeded.
 *
 * @param[out] data The caller provided result buffer.
 *
 * @returns Non-zero if data was available, zero otherwise.
 */
IRMP_DLLEXPORT int irmp_get_result_data(struct irmp_result_data *data);

/**
 * @brief Resolve the protocol identifer to the protocol's name.
 *
 * @param[in] protocol The numerical identifier.
 *
 * @returns A pointer to the string literal, or #NULL in case of failure.
 */
IRMP_DLLEXPORT const char *irmp_get_protocol_name(uint32_t protocol);

#ifdef __cplusplus
}
#endif

#endif
