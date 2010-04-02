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

#ifndef LIBSIGROKDECODE_SIGROKDECODE_H
#define LIBSIGROKDECODE_SIGROKDECODE_H

#include <Python.h> /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <stdint.h>

int sigrokdecode_init(void);
int sigrokdecode_load_decoder_file(const char *name);
int sigrokdecode_run_decoder(const char *decodername, uint8_t *inbuf,
			     uint64_t inbuflen, uint8_t **outbuf,
			     uint64_t *outbuflen);
int sigrokdecode_shutdown(void);

#endif
