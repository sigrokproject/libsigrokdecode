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
#include "sigrokdecode-internal.h"
#include <glib.h>

/* The list of protocol decoders. */
GSList *pd_list = NULL;

/* lives in module_sigrokdecode.c */
extern PyObject *mod_sigrokdecode;


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
 * Load a protocol decoder module into the embedded Python interpreter.
 *
 * @param name The module name to be loaded.
 * @param dec Pointer to the struct srd_decoder filled with the loaded module.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_load_decoder(const char *name, struct srd_decoder **dec)
{
	PyObject *py_basedec, *py_method, *py_annlist, *py_ann;
	struct srd_decoder *d;
	int alen, ret, i;
	char **ann;

	py_basedec = py_method = NULL;

	srd_dbg("decoder: %s: loading module '%s'", __func__, name);

	if (!(d = g_try_malloc0(sizeof(struct srd_decoder)))) {
		srd_err("decoder: %s: d malloc failed", __func__);
		ret = SRD_ERR_MALLOC;
		goto err_out;
	}

	ret = SRD_ERR_PYTHON;

	/* Import the Python module. */
	if (!(d->py_mod = PyImport_ImportModule(name))) {
		/* TODO: Report exception message/traceback to err/dbg. */
		srd_warn("decoder: %s: import of '%s' failed", __func__, name);
		PyErr_Print();
		PyErr_Clear();
		goto err_out;
	}

	/* Get the 'Decoder' class as Python object. */
	if (!(d->py_dec = PyObject_GetAttrString(d->py_mod, "Decoder"))) {
		/* This generated an AttributeError exception. */
		PyErr_Print();
		PyErr_Clear();
		srd_err("Decoder class not found in protocol decoder %s", name);
		goto err_out;
	}

	if (!(py_basedec = PyObject_GetAttrString(mod_sigrokdecode, "Decoder"))) {
		srd_dbg("sigrokdecode module not loaded");
		goto err_out;
	}

	if (!PyObject_IsSubclass(d->py_dec, py_basedec)) {
		srd_err("Decoder class in protocol decoder module %s is not "
				"a subclass of sigrokdecode.Decoder", name);
		goto err_out;
	}
	Py_DecRef(py_basedec);

	/* Check for a proper start() method. */
	if (!PyObject_HasAttrString(d->py_dec, "start")) {
		srd_err("Protocol decoder %s has no start() method Decoder "
				"class.", name);
		goto err_out;
	}
	py_method = PyObject_GetAttrString(d->py_dec, "start");
	if (!PyFunction_Check(py_method)) {
		srd_err("Protocol decoder %s Decoder class attribute 'start'"
				"is not a method.", name);
		goto err_out;
	}
	Py_DecRef(py_method);

	/* Check for a proper decode() method. */
	if (!PyObject_HasAttrString(d->py_dec, "decode")) {
		srd_err("Protocol decoder %s has no decode() method Decoder "
				"class.", name);
		goto err_out;
	}
	py_method = PyObject_GetAttrString(d->py_dec, "decode");
	if (!PyFunction_Check(py_method)) {
		srd_err("Protocol decoder %s Decoder class attribute 'decode' "
				"is not a method.", name);
		goto err_out;
	}
	Py_DecRef(py_method);

	if (py_attr_as_str(d->py_dec, "id", &(d->id)) != SRD_OK)
		goto err_out;

	if (py_attr_as_str(d->py_dec, "name", &(d->name)) != SRD_OK)
		goto err_out;

	if (py_attr_as_str(d->py_dec, "longname", &(d->longname)) != SRD_OK)
		goto err_out;

	if (py_attr_as_str(d->py_dec, "desc", &(d->desc)) != SRD_OK)
		goto err_out;

	if (py_attr_as_str(d->py_dec, "license", &(d->license)) != SRD_OK)
		goto err_out;

	/* TODO: Handle inputformats, outputformats. */
	d->inputformats = NULL;
	d->outputformats = NULL;

	/* Convert class annotation attribute to GSList of **char */
	d->annotations = NULL;
	if (PyObject_HasAttrString(d->py_dec, "annotations")) {
		py_annlist = PyObject_GetAttrString(d->py_dec, "annotations");
		if (!PyList_Check(py_annlist)) {
			srd_err("Protocol decoder module %s annotations should be a list", name);
			goto err_out;
		}
		alen = PyList_Size(py_annlist);
		for (i = 0; i < alen; i++) {
			py_ann = PyList_GetItem(py_annlist, i);
			if (!PyList_Check(py_ann) || PyList_Size(py_ann) != 2) {
				srd_err("Protocol decoder module %s annotation %d should be a list with two elements",
						name, i+1);
				goto err_out;
			}

			if (py_strlist_to_char(py_ann, &ann) != SRD_OK) {
				goto err_out;
			}
			d->annotations = g_slist_append(d->annotations, ann);
		}
	}

	*dec = d;
	ret = SRD_OK;

err_out:
	if (ret != SRD_OK) {
		Py_XDECREF(py_method);
		Py_XDECREF(py_basedec);
		Py_XDECREF(d->py_dec);
		Py_XDECREF(d->py_mod);
		g_free(d);
	}

	return ret;
}

char *srd_decoder_doc(struct srd_decoder *dec)
{
	PyObject *py_str;
	char *doc;

	if (!PyObject_HasAttrString(dec->py_mod, "__doc__"))
		return NULL;

	if (!(py_str = PyObject_GetAttrString(dec->py_mod, "__doc__"))) {
		PyErr_Clear();
		return NULL;
	}

	doc = NULL;
	if (py_str != Py_None)
		py_str_as_str(py_str, &doc);
	Py_DecRef(py_str);

	return doc;
}


/**
 * Unload decoder module.
 *
 * @param dec The decoder struct to be unloaded.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
int srd_unload_decoder(struct srd_decoder *dec)
{

	g_free(dec->id);
	g_free(dec->name);
	g_free(dec->longname);
	g_free(dec->desc);
	g_free(dec->license);

	/* TODO: Free everything in inputformats and outputformats. */
	if (dec->inputformats != NULL)
		g_slist_free(dec->inputformats);
	if (dec->outputformats != NULL)
		g_slist_free(dec->outputformats);

	Py_XDECREF(dec->py_dec);
	Py_XDECREF(dec->py_mod);

	/* TODO: (g_)free dec itself? */

	return SRD_OK;
}

int srd_load_all_decoders(void)
{
	GDir *dir;
	GError *error;
	struct srd_decoder *dec;
	int ret;
	const gchar *direntry;
	char *decodername;

	if (!(dir = g_dir_open(DECODERS_DIR, 0, &error))) {
		return SRD_ERR_DECODERS_DIR;
	}

	while ((direntry = g_dir_read_name(dir)) != NULL) {
		/* The decoder name is the PD directory name (e.g. "i2c"). */
		decodername = g_strdup(direntry);

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
	g_dir_close(dir);

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



