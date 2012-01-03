/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
 * Copyright (C) 2011 Bert Vermeulen <bert@biot.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "config.h"
#include "sigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include <dirent.h>

/* The list of protocol decoders. */
GSList *pd_list = NULL;
GSList *di_list = NULL;


/**
 * Returns the list of supported/loaded protocol decoders.
 *
 * This is a GSList containing the names of the decoders as strings.
 *
 * @return List of decoders, NULL if none are supported or loaded.
 */
GSList *srd_list_decoders(void)
{

	return pd_list;
}


/**
 * Get the decoder with the specified ID.
 *
 * @param id The ID string of the decoder to return.
 * @return The decoder with the specified ID, or NULL if not found.
 */
struct srd_decoder *srd_get_decoder_by_id(const char *id)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_list_decoders(); l; l = l->next) {
		dec = l->data;
		if (!strcmp(dec->id, id))
			return dec;
	}

	return NULL;
}


/**
 * TODO
 *
 * @param name TODO
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_load_decoder(const char *name, struct srd_decoder **dec)
{
	struct srd_decoder *d;
	PyObject *py_mod, *py_res;
	int r;

	fprintf(stdout, "%s: %s\n", __func__, name);

	/* "Import" the Python module. */
	if (!(py_mod = PyImport_ImportModule(name))) { /* NEWREF */
		PyErr_Print(); /* Returns void. */
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	/* Get the 'Decoder' class as Python object. */
	py_res = PyObject_GetAttrString(py_mod, "Decoder"); /* NEWREF */
	if (!py_res) {
		if (PyErr_Occurred())
			PyErr_Print(); /* Returns void. */
		Py_XDECREF(py_mod);
		fprintf(stderr, "Decoder class not found in PD module %s\n", name);
		return SRD_ERR_PYTHON; /* TODO: More specific error? */
	}

	if (!(d = malloc(sizeof(struct srd_decoder))))
		return SRD_ERR_MALLOC;

	if ((r = h_str(py_res, "id", &(d->id))) < 0)
		return r;

	if ((r = h_str(py_res, "name", &(d->name))) < 0)
		return r;

	if ((r = h_str(py_res, "longname",
		       &(d->longname))) < 0)
		return r;

	if ((r = h_str(py_res, "desc", &(d->desc))) < 0)
		return r;

	if ((r = h_str(py_res, "longdesc",
		       &(d->longdesc))) < 0)
		return r;

	if ((r = h_str(py_res, "author", &(d->author))) < 0)
		return r;

	if ((r = h_str(py_res, "email", &(d->email))) < 0)
		return r;

	if ((r = h_str(py_res, "license", &(d->license))) < 0)
		return r;

	d->py_mod = py_mod;
	d->py_decobj = py_res;

	/* TODO: Handle func, inputformats, outputformats. */
	/* Note: They must at least be set to NULL, will segfault otherwise. */
	d->func = NULL;
	d->inputformats = NULL;
	d->outputformats = NULL;

	*dec = d;

	return SRD_OK;
}


/**
 * TODO
 */
int srd_unload_decoder(struct srd_decoder *dec)
{
	g_free(dec->id);
	g_free(dec->name);
	g_free(dec->desc);
	g_free(dec->func);

	/* TODO: Free everything in inputformats and outputformats. */

	if (dec->inputformats != NULL)
		g_slist_free(dec->inputformats);
	if (dec->outputformats != NULL)
		g_slist_free(dec->outputformats);

	Py_XDECREF(dec->py_decobj);
	Py_XDECREF(dec->py_mod);

	/* TODO: (g_)free dec itself? */

	return SRD_OK;
}


int srd_load_all_decoders(void)
{
	DIR *dir;
	struct dirent *dp;
	int ret;
	char *decodername;
	struct srd_decoder *dec;

	if (!(dir = opendir(DECODERS_DIR))) {
		Py_Finalize(); /* Returns void. */
		return SRD_ERR_DECODERS_DIR;
	}

	while ((dp = readdir(dir)) != NULL) {
		/* Ignore filenames which don't end with ".py". */
		if (!g_str_has_suffix(dp->d_name, ".py"))
			continue;

		/* Decoder name == filename (without .py suffix). */
		decodername = g_strndup(dp->d_name, strlen(dp->d_name) - 3);

		/* TODO: Error handling. Use g_try_malloc(). */
		if (!(dec = malloc(sizeof(struct srd_decoder)))) {
			Py_Finalize(); /* Returns void. */
			return SRD_ERR_MALLOC;
		}

		/* Load the decoder. */
		/* TODO: Warning if loading fails for a decoder. */
		if ((ret = srd_load_decoder(decodername, &dec)) == SRD_OK) {
			/* Append it to the list of supported/loaded decoders. */
			pd_list = g_slist_append(pd_list, dec);
		}
	}
	closedir(dir);

	return SRD_OK;
}


/**
 * TODO
 */
int srd_unload_all_decoders(void)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_list_decoders(); l; l = l->next) {
		dec = l->data;
		/* TODO: Error handling. */
		srd_unload_decoder(dec);
	}

	return SRD_OK;
}



