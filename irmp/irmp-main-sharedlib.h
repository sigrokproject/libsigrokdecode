/*---------------------------------------------------------------------------------------------------------------------------------------------------
 * irmpharedLib.h
 *
 * Copyright (c) 2009-2019 Frank Meyer - frank(at)fli4l.de
 * Copyright (c) 2009-2019 René Staffen - r.staffen(at)gmx.de
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *---------------------------------------------------------------------------------------------------------------------------------------------------
 */

#ifndef IRMP_SHARED_H
#define IRMP_SHARED_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef IRMP_DLLEXPORT

#if defined WIN32 && defined _MSC_VER
# define IRMP_DLLEXPORT __declspec(dllimport)
#else
# define IRMP_DLLEXPORT
#endif
#endif // !IRMP_DLLEXPORT


/**
 * result data
 */
typedef struct
{ 
    uint32_t    protocol;     ///< protocol, e.g. NEC_PROTOCOL
    const char* protocolName; ///< name of the protocol
    uint32_t    address;      ///< address
    uint32_t    command;      ///< command
    uint32_t    flags;        ///< flags currently only repetition (bit 0)
    uint32_t    startSample;  ///< the sampleindex there the detected command started
    uint32_t    endSample;    ///< the sampleindex there the detected command ended
}  IRMP_DataExt;


/**
 * Returns the sample rate for that the irmp library was compiled for.
 * Any data provided has resamble  this sample rate or detection will fail.
 */
IRMP_DLLEXPORT  uint32_t IRMP_GetSampleRate(void);

/**
 * Resets the internal state of the detector 
 * This has to be called before start processing data.
 */
IRMP_DLLEXPORT  void IRMP_Reset(void);

/**
 * Feeds a single sample into the detecor.
 * Returns 1 if a ir command was detected.
 * Use IRMP_GetData to retrieve the data.
 * Make sure, that Reset was called before adding first Sample.
 */
IRMP_DLLEXPORT  uint32_t IRMP_AddSample(const uint8_t i_sample);


/**
 * Proceses the given buffer and stops on the first found command and returns it data.
 * Further calls resume the processing at the previously stopped position.
 * Make sure, that Reset was called before first calling Detect.
 */
IRMP_DLLEXPORT  IRMP_DataExt IRMP_Detect(const uint8_t* i_buff, uint32_t i_len);


/**
 * If a valid IR frame was detected the provided output structure is filled
 * \returns 1 if data was available, 0 else
 */
IRMP_DLLEXPORT  uint32_t IRMP_GetData(IRMP_DataExt* o_data);

/** returns the the name of the given protocol number */
IRMP_DLLEXPORT  const char* IRMP_GetProtocolName(uint32_t i_protocol);


#ifdef __cplusplus
}
#endif

#endif // IRMP_SHARED_H
