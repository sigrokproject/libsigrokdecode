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

#include "sigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "sigrokdecode-internal.h"
#include <stdarg.h>
#include <stdio.h>

/* Currently selected libsigrokdecode loglevel. Default: SRD_LOG_WARN. */
static int srd_loglevel = SRD_LOG_WARN; /* Show errors+warnings per default. */

/* Function prototype. */
static int srd_logv(void *cb_data, int loglevel, const char *format,
		    va_list args);

/* Pointer to the currently selected log callback. Default: srd_logv(). */
static srd_log_callback_t srd_log_callback = srd_logv;

/*
 * Pointer to private data that can be passed to the log callback.
 * This can be used (for example) by C++ GUIs to pass a "this" pointer.
 */
static void *srd_log_callback_data = NULL;

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
 * Note that this function itself will also output log messages. After the
 * loglevel has changed, it will output a debug message with SRD_LOG_DBG for
 * example. Whether this message is shown depends on the (new) loglevel.
 *
 * @param loglevel The loglevel to set (SRD_LOG_NONE, SRD_LOG_ERR,
 *                 SRD_LOG_WARN, SRD_LOG_INFO, SRD_LOG_DBG, or SRD_LOG_SPEW).
 *
 * @return SRD_OK upon success, SRD_ERR_ARG upon invalid loglevel.
 */
SRD_API int srd_log_loglevel_set(int loglevel)
{
	if (loglevel < SRD_LOG_NONE || loglevel > SRD_LOG_SPEW) {
		srd_err("Invalid loglevel %d.", loglevel);
		return SRD_ERR_ARG;
	}

	srd_loglevel = loglevel;

	srd_dbg("libsigrokdecode loglevel set to %d.", loglevel);

	return SRD_OK;
}

/**
 * Get the libsigrokdecode loglevel.
 *
 * @return The currently configured libsigrokdecode loglevel.
 */
SRD_API int srd_log_loglevel_get(void)
{
	return srd_loglevel;
}

/**
 * Set the libsigrokdecode logdomain string.
 *
 * @param logdomain The string to use as logdomain for libsigrokdecode log
 *                  messages from now on. Must not be NULL. The maximum
 *                  length of the string is 30 characters (this does not
 *                  include the trailing NUL-byte). Longer strings are
 *                  silently truncated.
 *                  In order to not use a logdomain, pass an empty string.
 *                  The function makes its own copy of the input string, i.e.
 *                  the caller does not need to keep it around.
 *
 * @return SRD_OK upon success, SRD_ERR_ARG upon invalid logdomain.
 */
SRD_API int srd_log_logdomain_set(const char *logdomain)
{
	if (!logdomain) {
		srd_err("log: %s: logdomain was NULL", __func__);
		return SRD_ERR_ARG;
	}

	/* TODO: Error handling. */
	snprintf((char *)&srd_log_domain, LOGDOMAIN_MAXLEN, "%s", logdomain);

	srd_dbg("Log domain set to '%s'.", (const char *)&srd_log_domain);

	return SRD_OK;
}

/**
 * Get the currently configured libsigrokdecode logdomain.
 *
 * @return A copy of the currently configured libsigrokdecode logdomain
 *         string. The caller is responsible for g_free()ing the string when
 *         it is no longer needed.
 */
SRD_API char *srd_log_logdomain_get(void)
{
	return g_strdup((const char *)&srd_log_domain);
}

/**
 * Set the libsigrokdecode log callback to the specified function.
 *
 * @param cb Function pointer to the log callback function to use.
 *           Must not be NULL.
 * @param cb_data Pointer to private data to be passed on. This can be used
 *                by the caller to pass arbitrary data to the log functions.
 *                This pointer is only stored or passed on by libsigrokdecode,
 *                and is never used or interpreted in any way. The pointer
 *                is allowed to be NULL if the caller doesn't need/want to
 *                pass any data.
 *
 * @return SRD_OK upon success, SRD_ERR_ARG upon invalid arguments.
 */
SRD_API int srd_log_callback_set(srd_log_callback_t cb, void *cb_data)
{
	if (!cb) {
		srd_err("log: %s: cb was NULL", __func__);
		return SRD_ERR_ARG;
	}

	/* Note: 'cb_data' is allowed to be NULL. */

	srd_log_callback = cb;
	srd_log_callback_data = cb_data;

	return SRD_OK;
}

/**
 * Set the libsigrokdecode log callback to the default built-in one.
 *
 * Additionally, the internal 'srd_log_callback_data' pointer is set to NULL.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_log_callback_set_default(void)
{
	/*
	 * Note: No log output in this function, as it should safely work
	 * even if the currently set log callback is buggy/broken.
	 */
	srd_log_callback = srd_logv;
	srd_log_callback_data = NULL;

	return SRD_OK;
}

static int srd_logv(void *cb_data, int loglevel, const char *format,
		    va_list args)
{
	int ret;

	/* This specific log callback doesn't need the void pointer data. */
	(void)cb_data;

	/* Only output messages of at least the selected loglevel(s). */
	if (loglevel > srd_loglevel)
		return SRD_OK; /* TODO? */

	if (srd_log_domain[0] != '\0')
		fprintf(stderr, "%s", srd_log_domain);
	ret = vfprintf(stderr, format, args);
	fprintf(stderr, "\n");

	return ret;
}

SRD_PRIV int srd_log(int loglevel, const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, loglevel, format, args);
	va_end(args);

	return ret;
}

SRD_PRIV int srd_spew(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, SRD_LOG_SPEW,
			       format, args);
	va_end(args);

	return ret;
}

SRD_PRIV int srd_dbg(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, SRD_LOG_DBG,
			       format, args);
	va_end(args);

	return ret;
}

SRD_PRIV int srd_info(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, SRD_LOG_INFO,
			       format, args);
	va_end(args);

	return ret;
}

SRD_PRIV int srd_warn(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, SRD_LOG_WARN,
			       format, args);
	va_end(args);

	return ret;
}

SRD_PRIV int srd_err(const char *format, ...)
{
	int ret;
	va_list args;

	va_start(args, format);
	ret = srd_log_callback(srd_log_callback_data, SRD_LOG_ERR,
			       format, args);
	va_end(args);

	return ret;
}
