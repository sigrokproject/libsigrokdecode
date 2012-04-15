/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
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

SRD_API int srd_package_version_major_get(void)
{
	return SRD_PACKAGE_VERSION_MAJOR;
}

SRD_API int srd_package_version_minor_get(void)
{
	return SRD_PACKAGE_VERSION_MINOR;
}

SRD_API int srd_package_version_micro_get(void)
{
	return SRD_PACKAGE_VERSION_MICRO;
}

SRD_API const char *srd_package_version_string_get(void)
{
	return SRD_PACKAGE_VERSION_STRING;
}

SRD_API int srd_lib_version_current_get(void)
{
	return SRD_LIB_VERSION_CURRENT;
}

SRD_API int srd_lib_version_revision_get(void)
{
	return SRD_LIB_VERSION_REVISION;
}

SRD_API int srd_lib_version_age_get(void)
{
	return SRD_LIB_VERSION_AGE;
}

SRD_API const char *srd_lib_version_string_get(void)
{
	return SRD_LIB_VERSION_STRING;
}
