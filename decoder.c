/*
 * This file is part of the sigrok project.
 *
 * Copyright (C) 2010 Uwe Hermann <uwe@hermann-uwe.de>
 * Copyright (C) 2012 Bert Vermeulen <bert@biot.com>
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
SRD_PRIV GSList *pd_list = NULL;

/* module_sigrokdecode.c */
extern SRD_PRIV PyObject *mod_sigrokdecode;

/**
 * Returns the list of supported/loaded protocol decoders.
 *
 * This is a GSList containing the names of the decoders as strings.
 *
 * @return List of decoders, NULL if none are supported or loaded.
 */
SRD_API GSList *srd_decoder_list(void)
{
	return pd_list;
}

/**
 * Get the decoder with the specified ID.
 *
 * @param id The ID string of the decoder to return.
 *
 * @return The decoder with the specified ID, or NULL if not found.
 */
SRD_API struct srd_decoder *srd_decoder_get_by_id(const char *id)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_decoder_list(); l; l = l->next) {
		dec = l->data;
		if (!strcmp(dec->id, id))
			return dec;
	}

	return NULL;
}

static int get_probes(const struct srd_decoder *d, const char *attr,
		      GSList **pl)
{
	PyObject *py_probelist, *py_entry;
	struct srd_probe *p;
	int ret, num_probes, i;

	if (!PyObject_HasAttrString(d->py_dec, attr))
		/* No probes of this type specified. */
		return SRD_OK;

	ret = SRD_ERR_PYTHON;
	py_probelist = py_entry = NULL;

	py_probelist = PyObject_GetAttrString(d->py_dec, attr);
	if (!PyList_Check(py_probelist)) {
		srd_err("Protocol decoder %s %s attribute is not "
			"a list.", d->name, attr);
		goto err_out;
	}

	num_probes = PyList_Size(py_probelist);
	if (num_probes == 0)
		/* Empty probelist. */
		return SRD_OK;

	for (i = 0; i < num_probes; i++) {
		py_entry = PyList_GetItem(py_probelist, i);
		if (!PyDict_Check(py_entry)) {
			srd_err("Protocol decoder %s %s attribute is not "
				"a list with dict elements.", d->name, attr);
			goto err_out;
		}

		if (!(p = g_try_malloc(sizeof(struct srd_probe)))) {
			srd_err("Failed to g_malloc() struct srd_probe.");
			ret = SRD_ERR_MALLOC;
			goto err_out;
		}

		if ((py_dictitem_as_str(py_entry, "id", &p->id)) != SRD_OK)
			goto err_out;
		if ((py_dictitem_as_str(py_entry, "name", &p->name)) != SRD_OK)
			goto err_out;
		if ((py_dictitem_as_str(py_entry, "desc", &p->desc)) != SRD_OK)
			goto err_out;
		p->order = i;

		*pl = g_slist_append(*pl, p);
	}
	ret = SRD_OK;

err_out:
	Py_DecRef(py_entry);
	Py_DecRef(py_probelist);

	return ret;
}

/**
 * Load a protocol decoder module into the embedded Python interpreter.
 *
 * @param module_name The module name to be loaded.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_decoder_load(const char *module_name)
{
	PyObject *py_basedec, *py_method, *py_attr, *py_annlist, *py_ann;
	struct srd_decoder *d;
	int alen, ret, i;
	char **ann;
	struct srd_probe *p;
	GSList *l;

	srd_dbg("Loading protocol decoder '%s'.", module_name);

	py_basedec = py_method = py_attr = NULL;

	if (!(d = g_try_malloc0(sizeof(struct srd_decoder)))) {
		srd_dbg("Failed to g_malloc() struct srd_decoder.");
		ret = SRD_ERR_MALLOC;
		goto err_out;
	}

	ret = SRD_ERR_PYTHON;

	/* Import the Python module. */
	if (!(d->py_mod = PyImport_ImportModule(module_name))) {
		srd_exception_catch("Import of '%s' failed.", module_name);
		goto err_out;
	}

	/* Get the 'Decoder' class as Python object. */
	if (!(d->py_dec = PyObject_GetAttrString(d->py_mod, "Decoder"))) {
		/* This generated an AttributeError exception. */
		PyErr_Clear();
		srd_err("Decoder class not found in protocol decoder %s.",
			module_name);
		goto err_out;
	}

	if (!(py_basedec = PyObject_GetAttrString(mod_sigrokdecode, "Decoder"))) {
		srd_dbg("sigrokdecode module not loaded.");
		goto err_out;
	}

	if (!PyObject_IsSubclass(d->py_dec, py_basedec)) {
		srd_err("Decoder class in protocol decoder module %s is not "
			"a subclass of sigrokdecode.Decoder.", module_name);
		goto err_out;
	}
	Py_CLEAR(py_basedec);

	/* Check for a proper start() method. */
	if (!PyObject_HasAttrString(d->py_dec, "start")) {
		srd_err("Protocol decoder %s has no start() method Decoder "
			"class.", module_name);
		goto err_out;
	}
	py_method = PyObject_GetAttrString(d->py_dec, "start");
	if (!PyFunction_Check(py_method)) {
		srd_err("Protocol decoder %s Decoder class attribute 'start' "
			"is not a method.", module_name);
		goto err_out;
	}
	Py_CLEAR(py_method);

	/* Check for a proper decode() method. */
	if (!PyObject_HasAttrString(d->py_dec, "decode")) {
		srd_err("Protocol decoder %s has no decode() method Decoder "
			"class.", module_name);
		goto err_out;
	}
	py_method = PyObject_GetAttrString(d->py_dec, "decode");
	if (!PyFunction_Check(py_method)) {
		srd_err("Protocol decoder %s Decoder class attribute 'decode' "
			"is not a method.", module_name);
		goto err_out;
	}
	Py_CLEAR(py_method);

	/* If present, options must be a dictionary. */
	if (PyObject_HasAttrString(d->py_dec, "options")) {
		py_attr = PyObject_GetAttrString(d->py_dec, "options");
		if (!PyDict_Check(py_attr)) {
			srd_err("Protocol decoder %s options attribute is not "
				"a dictionary.", d->name);
			Py_DecRef(py_attr);
			goto err_out;
		}
		Py_DecRef(py_attr);
	}

	/* Check and import required probes. */
	if (get_probes(d, "probes", &d->probes) != SRD_OK)
		goto err_out;

	/* Check and import optional probes. */
	if (get_probes(d, "optional_probes", &d->opt_probes) != SRD_OK)
		goto err_out;

	/*
	 * Fix order numbers for the optional probes.
	 *
	 * Example:
	 * Required probes: r1, r2, r3. Optional: o1, o2, o3, o4.
	 * 'order' fields in the d->probes list = 0, 1, 2.
	 * 'order' fields in the d->opt_probes list = 3, 4, 5, 6.
	 */
	for (l = d->opt_probes; l; l = l->next) {
		p = l->data;
		p->order += g_slist_length(d->probes);
	}

	/* Store required fields in newly allocated strings. */
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

	/* Convert class annotation attribute to GSList of **char. */
	d->annotations = NULL;
	if (PyObject_HasAttrString(d->py_dec, "annotations")) {
		py_annlist = PyObject_GetAttrString(d->py_dec, "annotations");
		if (!PyList_Check(py_annlist)) {
			srd_err("Protocol decoder module %s annotations "
				"should be a list.", module_name);
			goto err_out;
		}
		alen = PyList_Size(py_annlist);
		for (i = 0; i < alen; i++) {
			py_ann = PyList_GetItem(py_annlist, i);
			if (!PyList_Check(py_ann) || PyList_Size(py_ann) != 2) {
				srd_err("Protocol decoder module %s "
					"annotation %d should be a list with "
					"two elements.", module_name, i + 1);
				goto err_out;
			}

			if (py_strlist_to_char(py_ann, &ann) != SRD_OK) {
				goto err_out;
			}
			d->annotations = g_slist_append(d->annotations, ann);
		}
	}

	/* Append it to the list of supported/loaded decoders. */
	pd_list = g_slist_append(pd_list, d);

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

/**
 * Return a protocol decoder's docstring.
 *
 * @param dec The loaded protocol decoder.
 *
 * @return A newly allocated buffer containing the protocol decoder's
 *         documentation. The caller is responsible for free'ing the buffer.
 */
SRD_API char *srd_decoder_doc_get(const struct srd_decoder *dec)
{
	PyObject *py_str;
	char *doc;

	if (!PyObject_HasAttrString(dec->py_mod, "__doc__"))
		return NULL;

	if (!(py_str = PyObject_GetAttrString(dec->py_mod, "__doc__"))) {
		srd_exception_catch("");
		return NULL;
	}

	doc = NULL;
	if (py_str != Py_None)
		py_str_as_str(py_str, &doc);
	Py_DecRef(py_str);

	return doc;
}

static void free_probes(GSList *probelist)
{
	GSList *l;
	struct srd_probe *p;

	if (probelist == NULL)
		return;

	for (l = probelist; l; l = l->next) {
		p = l->data;
		g_free(p->id);
		g_free(p->name);
		g_free(p->desc);
		g_free(p);
	}
	g_slist_free(probelist);
}

/**
 * Unload decoder module.
 *
 * @param dec The struct srd_decoder to be unloaded.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_decoder_unload(struct srd_decoder *dec)
{
	srd_dbg("Unloading protocol decoder '%s'.", dec->name);

	/*
	 * Since any instances of this decoder need to be released as well,
	 * but they could be anywhere in the stack, just free the entire
	 * stack. A frontend reloading a decoder thus has to restart all
	 * instances, and rebuild the stack.
	 */
	srd_inst_free_all(NULL);

	free_probes(dec->probes);
	free_probes(dec->opt_probes);
	g_free(dec->id);
	g_free(dec->name);
	g_free(dec->longname);
	g_free(dec->desc);
	g_free(dec->license);

	/* The module's Decoder class. */
	Py_XDECREF(dec->py_dec);
	/* The module itself. */
	Py_XDECREF(dec->py_mod);

	/* TODO: (g_)free dec itself? */

	return SRD_OK;
}

/**
 * Load all installed protocol decoders.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_decoder_load_all(void)
{
	GDir *dir;
	GError *error;
	const gchar *direntry;

	if (!(dir = g_dir_open(DECODERS_DIR, 0, &error))) {
		srd_err("Unable to open %s for reading.", DECODERS_DIR);
		return SRD_ERR_DECODERS_DIR;
	}

	while ((direntry = g_dir_read_name(dir)) != NULL) {
		/* The directory name is the module name (e.g. "i2c"). */
		srd_decoder_load(direntry);
	}
	g_dir_close(dir);

	return SRD_OK;
}

/**
 * Unload all loaded protocol decoders.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 */
SRD_API int srd_decoder_unload_all(void)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = srd_decoder_list(); l; l = l->next) {
		dec = l->data;
		srd_decoder_unload(dec);
	}

	return SRD_OK;
}
