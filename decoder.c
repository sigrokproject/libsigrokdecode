/*
 * This file is part of the libsigrokdecode project.
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
#include "libsigrokdecode.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode-internal.h"
#include <glib.h>

/**
 * @file
 *
 * Listing, loading, unloading, and handling protocol decoders.
 */

/**
 * @defgroup grp_decoder Protocol decoders
 *
 * Handling protocol decoders.
 *
 * @{
 */

/** @cond PRIVATE */

/* The list of protocol decoders. */
SRD_PRIV GSList *pd_list = NULL;

/* srd.c */
extern GSList *searchpaths;

/* session.c */
extern GSList *sessions;

/* module_sigrokdecode.c */
extern SRD_PRIV PyObject *mod_sigrokdecode;

/** @endcond */

/**
 * Returns the list of supported/loaded protocol decoders.
 *
 * This is a GSList containing the names of the decoders as strings.
 *
 * @return List of decoders, NULL if none are supported or loaded.
 *
 * @since 0.1.0 (but the API changed in 0.2.0)
 */
SRD_API const GSList *srd_decoder_list(void)
{
	return pd_list;
}

/**
 * Get the decoder with the specified ID.
 *
 * @param id The ID string of the decoder to return.
 *
 * @return The decoder with the specified ID, or NULL if not found.
 *
 * @since 0.1.0
 */
SRD_API struct srd_decoder *srd_decoder_get_by_id(const char *id)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = pd_list; l; l = l->next) {
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

	py_probelist = PyObject_GetAttrString(d->py_dec, attr);
	if (!PyList_Check(py_probelist)) {
		srd_err("Protocol decoder %s %s attribute is not a list.",
				d->name, attr);
		return SRD_ERR_PYTHON;
	}

	if ((num_probes = PyList_Size(py_probelist)) == 0)
		/* Empty probelist. */
		return SRD_OK;

	ret = SRD_OK;
	for (i = 0; i < num_probes; i++) {
		py_entry = PyList_GetItem(py_probelist, i);
		if (!PyDict_Check(py_entry)) {
			srd_err("Protocol decoder %s %s attribute is not "
				"a list with dict elements.", d->name, attr);
			ret = SRD_ERR_PYTHON;
			break;
		}

		if (!(p = g_try_malloc(sizeof(struct srd_probe)))) {
			srd_err("Failed to g_malloc() struct srd_probe.");
			ret = SRD_ERR_MALLOC;
			break;
		}

		if ((py_dictitem_as_str(py_entry, "id", &p->id)) != SRD_OK) {
			ret = SRD_ERR_PYTHON;
			break;
		}
		if ((py_dictitem_as_str(py_entry, "name", &p->name)) != SRD_OK) {
			ret = SRD_ERR_PYTHON;
			break;
		}
		if ((py_dictitem_as_str(py_entry, "desc", &p->desc)) != SRD_OK) {
			ret = SRD_ERR_PYTHON;
			break;
		}
		p->order = i;

		*pl = g_slist_append(*pl, p);
	}

	Py_DecRef(py_probelist);

	return ret;
}

static int get_options(struct srd_decoder *d)
{
	PyObject *py_opts, *py_keys, *py_values, *py_val, *py_desc, *py_default;
	Py_ssize_t i;
	struct srd_decoder_option *o;
	gint64 def_long;
	int num_keys, overflow, ret;
	char *key, *def_str;

	ret = SRD_ERR_PYTHON;
	key = NULL;

	if (!PyObject_HasAttrString(d->py_dec, "options"))
		/* That's fine. */
		return SRD_OK;

	/* If present, options must be a dictionary. */
	py_opts = PyObject_GetAttrString(d->py_dec, "options");
	if (!PyDict_Check(py_opts)) {
		srd_err("Protocol decoder %s options attribute is not "
			"a dictionary.", d->name);
		goto err_out;
	}

	py_keys = PyDict_Keys(py_opts);
	py_values = PyDict_Values(py_opts);
	num_keys = PyList_Size(py_keys);
	for (i = 0; i < num_keys; i++) {
		py_str_as_str(PyList_GetItem(py_keys, i), &key);
		srd_dbg("option '%s'", key);
		py_val = PyList_GetItem(py_values, i);
		if (!PyList_Check(py_val) || PyList_Size(py_val) != 2) {
			srd_err("Protocol decoder %s option '%s' value must be "
					"a list with two elements.", d->name, key);
			goto err_out;
		}
		py_desc = PyList_GetItem(py_val, 0);
		if (!PyUnicode_Check(py_desc)) {
			srd_err("Protocol decoder %s option '%s' has no "
					"description.", d->name, key);
			goto err_out;
		}
		py_default = PyList_GetItem(py_val, 1);
		if (!PyUnicode_Check(py_default) && !PyLong_Check(py_default)) {
			srd_err("Protocol decoder %s option '%s' has default "
					"of unsupported type '%s'.", d->name, key,
					Py_TYPE(py_default)->tp_name);
			goto err_out;
		}
		if (!(o = g_try_malloc(sizeof(struct srd_decoder_option)))) {
			srd_err("option malloc failed");
			goto err_out;
		}
		o->id = g_strdup(key);
		py_str_as_str(py_desc, &o->desc);
		if (PyUnicode_Check(py_default)) {
			/* UTF-8 string */
			py_str_as_str(py_default, &def_str);
			o->def = g_variant_new_string(def_str);
			g_free(def_str);
		} else {
			/* Long */
			def_long = PyLong_AsLongAndOverflow(py_default, &overflow);
			if (overflow) {
				/* Value is < LONG_MIN or > LONG_MAX */
				PyErr_Clear();
				srd_err("Protocol decoder %s option '%s' has "
						"invalid default value.", d->name, key);
				goto err_out;
			}
			o->def = g_variant_new_int64(def_long);
		}
		g_variant_ref_sink(o->def);
		d->options = g_slist_append(d->options, o);
		g_free(key);
		key = NULL;
	}
	Py_DecRef(py_keys);
	Py_DecRef(py_values);

	ret = SRD_OK;

err_out:
	Py_XDECREF(py_opts);
	g_free(key);

	return ret;
}

/**
 * Load a protocol decoder module into the embedded Python interpreter.
 *
 * @param module_name The module name to be loaded.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.1.0
 */
SRD_API int srd_decoder_load(const char *module_name)
{
	PyObject *py_basedec, *py_method, *py_attr, *py_annlist, *py_ann, \
		*py_bin_classes, *py_bin_class;
	struct srd_decoder *d;
	int len, ret, i;
	char **ann, *bin;
	struct srd_probe *p;
	GSList *l;

	if (!srd_check_init())
		return SRD_ERR;

	if (!module_name)
		return SRD_ERR_ARG;

	if (PyDict_GetItemString(PyImport_GetModuleDict(), module_name)) {
		/* Module was already imported. */
		return SRD_OK;
	}

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

	if (get_options(d) != SRD_OK)
		goto err_out;

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

	/* Convert annotation class attribute to GSList of char **. */
	d->annotations = NULL;
	if (PyObject_HasAttrString(d->py_dec, "annotations")) {
		py_annlist = PyObject_GetAttrString(d->py_dec, "annotations");
		if (!PyList_Check(py_annlist)) {
			srd_err("Protocol decoder module %s annotations "
				"should be a list.", module_name);
			goto err_out;
		}
		len = PyList_Size(py_annlist);
		for (i = 0; i < len; i++) {
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

	/* Convert binary class to GSList of char *. */
	d->binary = NULL;
	if (PyObject_HasAttrString(d->py_dec, "binary")) {
		py_bin_classes = PyObject_GetAttrString(d->py_dec, "binary");
		if (!PyTuple_Check(py_bin_classes)) {
			srd_err("Protocol decoder module %s binary classes "
				"should be a tuple.", module_name);
			goto err_out;
		}
		len = PyTuple_Size(py_bin_classes);
		for (i = 0; i < len; i++) {
			py_bin_class = PyTuple_GetItem(py_bin_classes, i);
			if (!PyUnicode_Check(py_bin_class)) {
				srd_err("Protocol decoder module %s binary "
						"class should be a string.", module_name);
				goto err_out;
			}

			if (py_str_as_str(py_bin_class, &bin) != SRD_OK) {
				goto err_out;
			}
			d->binary = g_slist_append(d->binary, bin);
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
 *
 * @since 0.1.0
 */
SRD_API char *srd_decoder_doc_get(const struct srd_decoder *dec)
{
	PyObject *py_str;
	char *doc;

	if (!srd_check_init())
		return NULL;

	if (!dec)
		return NULL;

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
 * Unload the specified protocol decoder.
 *
 * @param dec The struct srd_decoder to be unloaded.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.1.0
 */
SRD_API int srd_decoder_unload(struct srd_decoder *dec)
{
	struct srd_decoder_option *o;
	struct srd_session *sess;
	GSList *l;

	if (!srd_check_init())
		return SRD_ERR;

	if (!dec)
		return SRD_ERR_ARG;

	srd_dbg("Unloading protocol decoder '%s'.", dec->name);

	/*
	 * Since any instances of this decoder need to be released as well,
	 * but they could be anywhere in the stack, just free the entire
	 * stack. A frontend reloading a decoder thus has to restart all
	 * instances, and rebuild the stack.
	 */
	for (l = sessions; l; l = l->next) {
		sess = l->data;
		srd_inst_free_all(sess, NULL);
	}

	for (l = dec->options; l; l = l->next) {
		o = l->data;
		g_free(o->id);
		g_free(o->desc);
		g_variant_unref(o->def);
		g_free(o);
	}
	g_slist_free(dec->options);

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

	g_free(dec);

	return SRD_OK;
}

static void srd_decoder_load_all_path(char *path)
{
	GDir *dir;
	const gchar *direntry;

	if (!(dir = g_dir_open(path, 0, NULL)))
		/* Not really fatal */
		return;

	/* This ignores errors returned by srd_decoder_load(). That
	 * function will have logged the cause, but in any case we
	 * want to continue anyway. */
	while ((direntry = g_dir_read_name(dir)) != NULL) {
		/* The directory name is the module name (e.g. "i2c"). */
		srd_decoder_load(direntry);
	}
	g_dir_close(dir);

}

/**
 * Load all installed protocol decoders.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.1.0
 */
SRD_API int srd_decoder_load_all(void)
{
	GSList *l;

	if (!srd_check_init())
		return SRD_ERR;

	for (l = searchpaths; l; l = l->next)
		srd_decoder_load_all_path(l->data);

	return SRD_OK;
}

/**
 * Unload all loaded protocol decoders.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.1.0
 */
SRD_API int srd_decoder_unload_all(void)
{
	GSList *l;
	struct srd_decoder *dec;

	for (l = pd_list; l; l = l->next) {
		dec = l->data;
		srd_decoder_unload(dec);
	}
	g_slist_free(pd_list);
	pd_list = NULL;

	return SRD_OK;
}

/** @} */
