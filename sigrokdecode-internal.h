/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2011 Uwe Hermann <uwe@hermann-uwe.de>
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

#ifndef SIGROKDECODE_SIGROKDECODE_INTERNAL_H
#define SIGROKDECODE_SIGROKDECODE_INTERNAL_H

// #include <stdarg.h>
// #include <glib.h>

/*--- Macros ----------------------------------------------------------------*/

#ifndef ARRAY_SIZE
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#endif

#ifndef ARRAY_AND_SIZE
#define ARRAY_AND_SIZE(a) (a), ARRAY_SIZE(a)
#endif

/*--- log.c -----------------------------------------------------------------*/

int srd_log(int loglevel, const char *format, ...);
int srd_spew(const char *format, ...);
int srd_dbg(const char *format, ...);
int srd_info(const char *format, ...);
int srd_warn(const char *format, ...);
int srd_err(const char *format, ...);

#endif
