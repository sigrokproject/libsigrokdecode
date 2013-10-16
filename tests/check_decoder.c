/*
 * This file is part of the libsigrokdecode project.
 *
 * Copyright (C) 2013 Uwe Hermann <uwe@hermann-uwe.de>
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

#include "../libsigrokdecode.h" /* First, to avoid compiler warning. */
#include <stdlib.h>
#include <check.h>

/*
 * Check whether srd_decoder_load_all() works.
 * If it returns != SRD_OK (or segfaults) this test will fail.
 */
START_TEST(test_load_all)
{
	int ret;

	srd_init(NULL);
	ret = srd_decoder_load_all();
	fail_unless(ret == SRD_OK, "srd_decoder_load_all() failed: %d.", ret);
	srd_exit();
}
END_TEST

/*
 * Check whether srd_decoder_load() works.
 * If it returns != SRD_OK (or segfaults) this test will fail.
 */
START_TEST(test_load)
{
	int ret;

	srd_init(NULL);
	ret = srd_decoder_load("uart");
	fail_unless(ret == SRD_OK, "srd_decoder_load(uart) failed: %d.", ret);
	ret = srd_decoder_load("spi");
	fail_unless(ret == SRD_OK, "srd_decoder_load(spi) failed: %d.", ret);
	ret = srd_decoder_load("usb_signalling");
	fail_unless(ret == SRD_OK, "srd_decoder_load(usb_signalling) failed: %d.", ret);
	srd_exit();
}
END_TEST

/*
 * Check whether srd_decoder_load() fails for non-existing or bogus PDs.
 * If it returns SRD_OK (or segfaults) this test will fail.
 */
START_TEST(test_load_bogus)
{
	srd_init(NULL);
	fail_unless(srd_decoder_load(NULL) != SRD_OK);
	fail_unless(srd_decoder_load("") != SRD_OK);
	fail_unless(srd_decoder_load(" ") != SRD_OK);
	fail_unless(srd_decoder_load("nonexisting") != SRD_OK);
	fail_unless(srd_decoder_load("UART") != SRD_OK);
	fail_unless(srd_decoder_load("UaRt") != SRD_OK);
	fail_unless(srd_decoder_load("u a r t") != SRD_OK);
	fail_unless(srd_decoder_load("uart ") != SRD_OK);
	fail_unless(srd_decoder_load(" uart") != SRD_OK);
	fail_unless(srd_decoder_load(" uart ") != SRD_OK);
	fail_unless(srd_decoder_load("uart spi") != SRD_OK);
	srd_exit();
}
END_TEST

Suite *suite_decoder(void)
{
	Suite *s;
	TCase *tc;

	s = suite_create("decoder");

	tc = tcase_create("load");
	tcase_add_test(tc, test_load_all);
	tcase_add_test(tc, test_load);
	tcase_add_test(tc, test_load_bogus);
	suite_add_tcase(s, tc);

	return s;
}
