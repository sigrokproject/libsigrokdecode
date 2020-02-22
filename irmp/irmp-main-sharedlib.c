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


#include "irmp.h"
#include "irmp.c"


#ifndef IRMP_DLLEXPORT

#if defined WIN32 && defined _MSC_VER
# define IRMP_DLLEXPORT __declspec(dllexport)
#else
# define IRMP_DLLEXPORT
#endif
#endif // !IRMP_DLLEXPORT

#include "irmp-main-sharedlib.h"



static uint32_t s_endSample = 0;

uint32_t IRMP_GetSampleRate(void) {
    return F_INTERRUPTS;
}


void IRMP_Reset(void) {
    IRMP_PIN = 0xff;
    IRMP_DATA data;
    int i;
    for (i = 0; i < (int)(( F_INTERRUPTS )); i++)  // long pause of 1s
    {
        (void)irmp_ISR();
    }
    (void)irmp_get_data(&data);
    time_counter = 0;
    s_startBitSample = 0;
    s_curSample = 0;
    s_endSample = 0;
}


uint32_t IRMP_AddSample(const uint8_t i_sample) {
    IRMP_PIN = i_sample;
    uint_fast8_t r = irmp_ISR();
    if (r) {
        s_endSample = s_curSample;
        return 1;
    }
    s_curSample++;
    return 0;
}


uint32_t IRMP_GetData(IRMP_DataExt* o_data) {

    IRMP_DATA d;
    if (irmp_get_data(&d))
    {  
        o_data->address      = d.address;
        o_data->command      = d.command;
        o_data->protocol     = d.protocol;
        o_data->protocolName = IRMP_GetProtocolName(d.protocol);
        o_data->flags        = d.flags;
        o_data->startSample  = s_startBitSample;
        o_data->endSample    = s_endSample;
        return TRUE;
    }
    return FALSE;
}


IRMP_DataExt IRMP_Detect(const uint8_t* i_buff, uint32_t i_len) {
    IRMP_DataExt ret = { 0 };
    while (s_curSample < i_len) {
        if (IRMP_AddSample(i_buff[s_curSample])) {
            IRMP_GetData(&ret);
            return ret;
        }
    }
    return ret;
}


const char* IRMP_GetProtocolName(uint32_t i_protocol) {
    if (i_protocol < IRMP_N_PROTOCOLS) {
        return irmp_protocol_names[i_protocol];
    }
    else {
        return "unknown";
    }
}

