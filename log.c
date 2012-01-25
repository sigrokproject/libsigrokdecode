/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2011-2012 Uwe Hermann <uwe@hermann-uwe.de>
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

#include "sigrokdecode.h"
#include "sigrokdecode-internal.h"
#include <stdarg.h>
#include <stdio.h>

/* Currently selected libsigrokdecode loglevel. Default: SRD_LOG_WARN. */
static int srd_loglevel = SRD_LOG_WARN; /* Show errors+warnings per default. */

/* Function prototype. */
static int srd_logv(void *data, int loglevel, const char *format, va_list args);

/* Pointer to the currently selected log handler. Default: srd_logv(). */
static srd_log_handler_t srd_handler = srd_logv;

/*
 * Pointer to private data that can be passed to the log handler.
 * This can be used (for example) by C++ GUIs to pass a "this" pointer.
 */
static void *srd_handler_data = NULL;

/* Log domain (a short string that is used as prefix for all messages). */
#define LOGDOMAIN_MAXLEN 30
#define LOGDOMAIN_DEFAULT "srd: "
static char srd_log_domain[LOGDOMAIN_MAXLEN + 1] = LOGDOMAIN_DEFAULT;

/**
 * Set the libsigrokdecode loglevel.
 *
 * This influences the amount of log messages (debug messages, error messages,
 * and so on) libsigrokdecode will output. Using SRD_LOG_NONE disables all
 * messages.
 *
 * @param loglevel The loglevel to set (SRD_LOG_NONE, SRD_LOG_ERR,
 *                 SRD_LOG_WARN, SRD_LOG_INFO, SRD_LOG_DBG, or SRD_LOG_SPEW).
 * @return SRD_OK upon success, SRD_ERR_ARG upon invalid loglevel.
 */
int srd_set_loglevel(int loglevel)
{
	if (loglevel < SRD_LOG_NONE || loglevel > SRD_LOG_SPEW) {
		srd_err("Invalid loglevel %d.", loglevel);
		return SRD_ERR_ARG;
	}

	srd_loglevel = loglevel;

	srd_dbg("srd: loglevel set to %d", loglevel);

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

/**
 * TODO.
 *
 * @param logdomain TODO
 * @return TODO.
 */
int srd_log_set_logdomain(const char *logdomain)
{
	if (!logdomain) {
		srd_err("log: %s: logdomain was NULL", __func__);
		return SRD_ERR_ARG;
	}

	/* TODO: Error handling. */
	snprintf((char *)&srd_log_domain, LOGDOMAIN_MAXLEN, "%s", logdomain);

	srd_dbg("log domain set to '%s'", (const char *)&srd_log_domain);

	return SRD_OK;
}

/**
 * TODO.
 *
 * @return TODO.
 */
char *srd_log_get_logdomain(void)
{
	return g_strdup((char *)srd_log_domain);
}

/**
 * Set the libsigrokdecode log handler to the specified function.
 *
 * @param handler Function pointer to the log handler function to use.
 *                Must not be NULL.
 * @param data Pointer to private data to be passed on. This can be used by
 *             the caller pass arbitrary data to the log functions. This
 *             pointer is only stored or passed on by libsigrokdecode, and
 *             is never used or interpreted in any way.
 * @return SRD_OK upon success, SRD_ERR_ARG upon invalid arguments.
 */
int srd_log_set_handler(srd_log_handler_t handler, void *data)
{
	if (!handler) {
		srd_err("log: %s: handler was NULL", __func__);
		return SRD_ERR_ARG;
	}

	/* Note: 'data' is allowed to be NULL. */

	srd_handler = handler;
	srd_handler_data = data;

	return SRD_OK;
}

/**
 * Set the libsigrokdecode log handler to the default built-in one.
 *
 * Additionally, the internal 'srd_handler_data' pointer is set to NULL.
 *
 * @return SRD_OK upon success, a negative error code otherwise.
 */
int srd_log_set_default_handler(void)
{
	/*
	 * Note: No log output in this function, as it should safely work
	 * even if the currently set log handler is buggy/broken.
	 */
	srd_handler = srd_logv;
	srd_handler_data = NULL;

	return SRD_OK;
}

static int srd_logv(void *data, int loglevel, const char *format, va_list args)
{
	int ret;

	/* This specific log handler doesn't need the void pointer data. */
	(void)data;

	/* Only output messages of at least the selected loglevel(s). */
	if (loglevel > srd_loglevel)
		return SRD_OK; /* TODO? */

	if (srd_log_domain[0] != '\0')
		fprintf(stderr, srd_log_domain);
	ret = vfprintf(stderr, format, args);
	fprintf(stderr, "\n");

	return ret;
}

int srd_log(int loglevel, const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, loglevel, format, args);
	va_end(args);

	return ret;
}

int srd_spew(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, SRD_LOG_SPEW, format, args);
	va_end(args);

	return ret;
}

int srd_dbg(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, SRD_LOG_DBG, format, args);
	va_end(args);

	return ret;
}

int srd_info(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, SRD_LOG_INFO, format, args);
	va_end(args);

	return ret;
}

int srd_warn(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, SRD_LOG_WARN, format, args);
	va_end(args);

	return ret;
}

int srd_err(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_handler(srd_handler_data, SRD_LOG_ERR, format, args);
	va_end(args);

	return ret;
}
