/*
 * This file is part of the libsigrokdecode project.
 *
 * Copyright (C) 2012-2013 Uwe Hermann <uwe@hermann-uwe.de>
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
 * along with this program; if not, see <http://www.gnu.org/licenses/>.
 */

#include <config.h>
#include "libsigrokdecode-internal.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode.h"

/**
 * @file
 *
 * Version number querying functions, definitions, and macros.
 */

/**
 * @defgroup grp_versions Versions
 *
 * Version number querying functions, definitions, and macros.
 *
 * This set of API calls returns two different version numbers related
 * to libsigrokdecode. The "package version" is the release version number
 * of the libsigrokdecode tarball in the usual "major.minor.micro" format,
 * e.g. "0.1.0".
 *
 * The "library version" is independent of that; it is the libtool version
 * number in the "current:revision:age" format, e.g. "2:0:0".
 * See http://www.gnu.org/software/libtool/manual/libtool.html#Libtool-versioning for details.
 *
 * Both version numbers (and/or individual components of them) can be
 * retrieved via the API calls at runtime, and/or they can be checked at
 * compile/preprocessor time using the respective macros.
 *
 * @{
 */

/**
 * Get the major libsigrokdecode package version number.
 *
 * @return The major package version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_package_version_major_get(void)
{
	return SRD_PACKAGE_VERSION_MAJOR;
}

/**
 * Get the minor libsigrokdecode package version number.
 *
 * @return The minor package version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_package_version_minor_get(void)
{
	return SRD_PACKAGE_VERSION_MINOR;
}

/**
 * Get the micro libsigrokdecode package version number.
 *
 * @return The micro package version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_package_version_micro_get(void)
{
	return SRD_PACKAGE_VERSION_MICRO;
}

/**
 * Get the libsigrokdecode package version number as a string.
 *
 * @return The package version number string. The returned string is
 *         static and thus should NOT be free'd by the caller.
 *
 * @since 0.1.0
 */
SRD_API const char *srd_package_version_string_get(void)
{
	return SRD_PACKAGE_VERSION_STRING;
}

/**
 * Get the "current" part of the libsigrokdecode library version number.
 *
 * @return The "current" library version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_lib_version_current_get(void)
{
	return SRD_LIB_VERSION_CURRENT;
}

/**
 * Get the "revision" part of the libsigrokdecode library version number.
 *
 * @return The "revision" library version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_lib_version_revision_get(void)
{
	return SRD_LIB_VERSION_REVISION;
}

/**
 * Get the "age" part of the libsigrokdecode library version number.
 *
 * @return The "age" library version number.
 *
 * @since 0.1.0
 */
SRD_API int srd_lib_version_age_get(void)
{
	return SRD_LIB_VERSION_AGE;
}

/**
 * Get the libsigrokdecode library version number as a string.
 *
 * @return The library version number string. The returned string is
 *         static and thus should NOT be free'd by the caller.
 *
 * @since 0.1.0
 */
SRD_API const char *srd_lib_version_string_get(void)
{
	return SRD_LIB_VERSION_STRING;
}

SRD_API GSList *srd_buildinfo_libs_get(void)
{
	GSList *l = NULL, *m = NULL;

	m = g_slist_append(NULL, g_strdup("glib"));
	m = g_slist_append(m, g_strdup_printf("%d.%d.%d (rt: %d.%d.%d/%d:%d)",
		GLIB_MAJOR_VERSION, GLIB_MINOR_VERSION, GLIB_MICRO_VERSION,
		glib_major_version, glib_minor_version, glib_micro_version,
		glib_binary_age, glib_interface_age));
	l = g_slist_append(l, m);

	m = g_slist_append(NULL, g_strdup("Python"));
	m = g_slist_append(m, g_strdup_printf("%s / 0x%x (API %s, ABI %s)",
		PY_VERSION, PY_VERSION_HEX, PYTHON_API_STRING, PYTHON_ABI_STRING));
	l = g_slist_append(l, m);

	return l;
}

SRD_API char *srd_buildinfo_host_get(void)
{
	return g_strdup_printf("%s, %s-endian", CONF_HOST,
#ifdef WORDS_BIGENDIAN
	"big"
#else
	"little"
#endif
	);
}

/** @} */
