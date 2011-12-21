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

#include <stdarg.h>
#include <stdio.h>
#include "sigrokdecode.h"
#include "sigrokdecode-internal.h"

static int srd_loglevel = SRD_LOG_WARN; /* Show errors+warnings per default. */

/**
 * Set the libsigrokdecode loglevel.
 *
 * This influences the amount of log messages (debug messages, error messages,
 * and so on) libsigrokdecode will output. Using SRD_LOG_NONE disables all
 * messages.
 *
 * @param loglevel The loglevel to set (SRD_LOG_NONE, SRD_LOG_ERR,
 *                 SRD_LOG_WARN, SRD_LOG_INFO, SRD_LOG_DBG, or SRD_LOG_SPEW).
 * @return SRD_OK upon success, SRD_ERR_ARGS upon invalid loglevel.
 */
int srd_set_loglevel(int loglevel)
{
	if (loglevel < SRD_LOG_NONE || loglevel > SRD_LOG_SPEW) {
		srd_err("log: %s: invalid loglevel %d", __func__, loglevel);
		return SRD_ERR_ARGS;
	}

	srd_loglevel = loglevel;

	srd_dbg("log: %s: libsigrokdecode loglevel set to %d",
		__func__, loglevel);

	return SRD_OK;
}

/**
 * Get the libsigrokdecode loglevel.
 *
 * @return The currently configured libsigrokdecode loglevel.
 */
int srd_get_loglevel(void)
{
	return srd_loglevel;
}

static int srd_logv(int loglevel, const char *format, va_list args)
{
	int ret;

	/* Only output messages of at least the selected loglevel(s). */
	if (loglevel > srd_loglevel)
		return SRD_OK; /* TODO? */

	ret = vfprintf(stderr, format, args);
	fprintf(stderr, "\n");

	return ret;
}

int srd_log(int loglevel, const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(loglevel, format, args);
	va_end(args);

	return ret;
}

int srd_spew(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(SRD_LOG_SPEW, format, args);
	va_end(args);

	return ret;
}

int srd_dbg(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(SRD_LOG_DBG, format, args);
	va_end(args);

	return ret;
}

int srd_info(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(SRD_LOG_INFO, format, args);
	va_end(args);

	return ret;
}

int srd_warn(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(SRD_LOG_WARN, format, args);
	va_end(args);

	return ret;
}

int srd_err(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_logv(SRD_LOG_ERR, format, args);
	va_end(args);

	return ret;
}
