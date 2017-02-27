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

#include <config.h>
#include "libsigrokdecode-internal.h" /* First, so we avoid a _POSIX_C_SOURCE warning. */
#include "libsigrokdecode.h"
#include <glib.h>
#include <inttypes.h>
#include <stdlib.h>
#include <stdint.h>

/** @cond PRIVATE */

extern SRD_PRIV GSList *sessions;

/* module_sigrokdecode.c */
extern SRD_PRIV PyObject *srd_logic_type;

/** @endcond */

/**
 * @file
 *
 * Decoder instance handling.
 */

/**
 * @defgroup grp_instances Decoder instances
 *
 * Decoder instance handling.
 *
 * @{
 */

/**
 * Set one or more options in a decoder instance.
 *
 * Handled options are removed from the hash.
 *
 * @param di Decoder instance.
 * @param options A GHashTable of options to set.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.1.0
 */
SRD_API int srd_inst_option_set(struct srd_decoder_inst *di,
		GHashTable *options)
{
	struct srd_decoder_option *sdo;
	PyObject *py_di_options, *py_optval;
	GVariant *value;
	GSList *l;
	double val_double;
	gint64 val_int;
	int ret;
	const char *val_str;

	if (!di) {
		srd_err("Invalid decoder instance.");
		return SRD_ERR_ARG;
	}

	if (!options) {
		srd_err("Invalid options GHashTable.");
		return SRD_ERR_ARG;
	}

	if (!PyObject_HasAttrString(di->decoder->py_dec, "options")) {
		/* Decoder has no options. */
		if (g_hash_table_size(options) == 0) {
			/* No options provided. */
			return SRD_OK;
		} else {
			srd_err("Protocol decoder has no options.");
			return SRD_ERR_ARG;
		}
		return SRD_OK;
	}

	ret = SRD_ERR_PYTHON;
	py_optval = NULL;

	/*
	 * The 'options' tuple is a class variable, but we need to
	 * change it. Changing it directly will affect the entire class,
	 * so we need to create a new object for it, and populate that
	 * instead.
	 */
	if (!(py_di_options = PyObject_GetAttrString(di->py_inst, "options")))
		goto err_out;
	Py_DECREF(py_di_options);
	py_di_options = PyDict_New();
	PyObject_SetAttrString(di->py_inst, "options", py_di_options);

	for (l = di->decoder->options; l; l = l->next) {
		sdo = l->data;
		if ((value = g_hash_table_lookup(options, sdo->id))) {
			/* A value was supplied for this option. */
			if (!g_variant_type_equal(g_variant_get_type(value),
				  g_variant_get_type(sdo->def))) {
				srd_err("Option '%s' should have the same type "
					"as the default value.", sdo->id);
				goto err_out;
			}
		} else {
			/* Use default for this option. */
			value = sdo->def;
		}
		if (g_variant_is_of_type(value, G_VARIANT_TYPE_STRING)) {
			val_str = g_variant_get_string(value, NULL);
			if (!(py_optval = PyUnicode_FromString(val_str))) {
				/* Some UTF-8 encoding error. */
				PyErr_Clear();
				srd_err("Option '%s' requires a UTF-8 string value.", sdo->id);
				goto err_out;
			}
		} else if (g_variant_is_of_type(value, G_VARIANT_TYPE_INT64)) {
			val_int = g_variant_get_int64(value);
			if (!(py_optval = PyLong_FromLong(val_int))) {
				/* ValueError Exception */
				PyErr_Clear();
				srd_err("Option '%s' has invalid integer value.", sdo->id);
				goto err_out;
			}
		} else if (g_variant_is_of_type(value, G_VARIANT_TYPE_DOUBLE)) {
			val_double = g_variant_get_double(value);
			if (!(py_optval = PyFloat_FromDouble(val_double))) {
				/* ValueError Exception */
				PyErr_Clear();
				srd_err("Option '%s' has invalid float value.",
					sdo->id);
				goto err_out;
			}
		}
		if (PyDict_SetItemString(py_di_options, sdo->id, py_optval) == -1)
			goto err_out;
		/* Not harmful even if we used the default. */
		g_hash_table_remove(options, sdo->id);
	}
	if (g_hash_table_size(options) != 0)
		srd_warn("Unknown options specified for '%s'", di->inst_id);

	ret = SRD_OK;

err_out:
	Py_XDECREF(py_optval);
	if (PyErr_Occurred()) {
		srd_exception_catch("Stray exception in srd_inst_option_set()");
		ret = SRD_ERR_PYTHON;
	}

	return ret;
}

/* Helper GComparefunc for g_slist_find_custom() in srd_inst_channel_set_all() */
static gint compare_channel_id(const struct srd_channel *pdch,
			const char *channel_id)
{
	return strcmp(pdch->id, channel_id);
}

/**
 * Set all channels in a decoder instance.
 *
 * This function sets _all_ channels for the specified decoder instance, i.e.,
 * it overwrites any channels that were already defined (if any).
 *
 * @param di Decoder instance.
 * @param new_channels A GHashTable of channels to set. Key is channel name,
 *                     value is the channel number. Samples passed to this
 *                     instance will be arranged in this order.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.4.0
 */
SRD_API int srd_inst_channel_set_all(struct srd_decoder_inst *di,
		GHashTable *new_channels)
{
	GVariant *channel_val;
	GList *l;
	GSList *sl;
	struct srd_channel *pdch;
	int *new_channelmap, new_channelnum, num_required_channels, i;
	char *channel_id;

	srd_dbg("Setting channels for instance %s with list of %d channels.",
		di->inst_id, g_hash_table_size(new_channels));

	if (g_hash_table_size(new_channels) == 0)
		/* No channels provided. */
		return SRD_OK;

	if (di->dec_num_channels == 0) {
		/* Decoder has no channels. */
		srd_err("Protocol decoder %s has no channels to define.",
			di->decoder->name);
		return SRD_ERR_ARG;
	}

	new_channelmap = g_malloc(sizeof(int) * di->dec_num_channels);

	/*
	 * For now, map all indexes to channel -1 (can be overridden later).
	 * This -1 is interpreted as an unspecified channel later.
	 */
	for (i = 0; i < di->dec_num_channels; i++)
		new_channelmap[i] = -1;

	for (l = g_hash_table_get_keys(new_channels); l; l = l->next) {
		channel_id = l->data;
		channel_val = g_hash_table_lookup(new_channels, channel_id);
		if (!g_variant_is_of_type(channel_val, G_VARIANT_TYPE_INT32)) {
			/* Channel name was specified without a value. */
			srd_err("No channel number was specified for %s.",
					channel_id);
			g_free(new_channelmap);
			return SRD_ERR_ARG;
		}
		new_channelnum = g_variant_get_int32(channel_val);
		if (!(sl = g_slist_find_custom(di->decoder->channels, channel_id,
				(GCompareFunc)compare_channel_id))) {
			/* Fall back on optional channels. */
			if (!(sl = g_slist_find_custom(di->decoder->opt_channels,
			     channel_id, (GCompareFunc)compare_channel_id))) {
				srd_err("Protocol decoder %s has no channel "
					"'%s'.", di->decoder->name, channel_id);
				g_free(new_channelmap);
				return SRD_ERR_ARG;
			}
		}
		pdch = sl->data;
		new_channelmap[pdch->order] = new_channelnum;
		srd_dbg("Setting channel mapping: %s (index %d) = channel %d.",
			pdch->id, pdch->order, new_channelnum);
	}

	srd_dbg("Final channel map:");
	num_required_channels = g_slist_length(di->decoder->channels);
	for (i = 0; i < di->dec_num_channels; i++) {
		srd_dbg(" - index %d = channel %d (%s)", i, new_channelmap[i],
			(i < num_required_channels) ? "required" : "optional");
	}

	/* Report an error if not all required channels were specified. */
	for (i = 0; i < num_required_channels; i++) {
		if (new_channelmap[i] != -1)
			continue;
		pdch = g_slist_nth(di->decoder->channels, i)->data;
		srd_err("Required channel '%s' (index %d) was not specified.",
			pdch->id, i);
		return SRD_ERR;
	}

	g_free(di->dec_channelmap);
	di->dec_channelmap = new_channelmap;

	return SRD_OK;
}

/**
 * Create a new protocol decoder instance.
 *
 * @param sess The session holding the protocol decoder instance.
 * @param decoder_id Decoder 'id' field.
 * @param options GHashtable of options which override the defaults set in
 *                the decoder class. May be NULL.
 *
 * @return Pointer to a newly allocated struct srd_decoder_inst, or
 *         NULL in case of failure.
 *
 * @since 0.3.0
 */
SRD_API struct srd_decoder_inst *srd_inst_new(struct srd_session *sess,
		const char *decoder_id, GHashTable *options)
{
	int i;
	struct srd_decoder *dec;
	struct srd_decoder_inst *di;
	char *inst_id;

	i = 1;
	srd_dbg("Creating new %s instance.", decoder_id);

	if (session_is_valid(sess) != SRD_OK) {
		srd_err("Invalid session.");
		return NULL;
	}

	if (!(dec = srd_decoder_get_by_id(decoder_id))) {
		srd_err("Protocol decoder %s not found.", decoder_id);
		return NULL;
	}

	di = g_malloc0(sizeof(struct srd_decoder_inst));

	di->decoder = dec;
	di->sess = sess;

	if (options) {
		inst_id = g_hash_table_lookup(options, "id");
		if (inst_id)
			di->inst_id = g_strdup(inst_id);
		g_hash_table_remove(options, "id");
	}

	/* Create a unique instance ID (as none was provided). */
	if (!di->inst_id) {
		di->inst_id = g_strdup_printf("%s-%d", decoder_id, i++);
		while (srd_inst_find_by_id(sess, di->inst_id)) {
			g_free(di->inst_id);
			di->inst_id = g_strdup_printf("%s-%d", decoder_id, i++);
		}
	}

	/*
	 * Prepare a default channel map, where samples come in the
	 * order in which the decoder class defined them.
	 */
	di->dec_num_channels = g_slist_length(di->decoder->channels) +
			g_slist_length(di->decoder->opt_channels);
	if (di->dec_num_channels) {
		di->dec_channelmap =
				g_malloc(sizeof(int) * di->dec_num_channels);
		for (i = 0; i < di->dec_num_channels; i++)
			di->dec_channelmap[i] = i;
		/*
		 * Will be used to prepare a sample at every iteration
		 * of the instance's decode() method.
		 */
		di->channel_samples = g_malloc(di->dec_num_channels);
	}

	/* Create a new instance of this decoder class. */
	if (!(di->py_inst = PyObject_CallObject(dec->py_dec, NULL))) {
		if (PyErr_Occurred())
			srd_exception_catch("Failed to create %s instance",
					decoder_id);
		g_free(di->dec_channelmap);
		g_free(di);
		return NULL;
	}

	if (options && srd_inst_option_set(di, options) != SRD_OK) {
		g_free(di->dec_channelmap);
		g_free(di);
		return NULL;
	}

	di->condition_list = NULL;
	di->match_array = NULL;
	di->abs_start_samplenum = 0;
	di->abs_end_samplenum = 0;
	di->inbuf = NULL;
	di->inbuflen = 0;
	di->abs_cur_samplenum = 0;
	di->old_pins_array = NULL;
	di->thread_handle = NULL;
	di->got_new_samples = FALSE;
	di->handled_all_samples = FALSE;

	/* Instance takes input from a frontend by default. */
	sess->di_list = g_slist_append(sess->di_list, di);
	srd_dbg("Created new %s instance with ID %s.", decoder_id, di->inst_id);

	return di;
}

/**
 * Stack a decoder instance on top of another.
 *
 * @param sess The session holding the protocol decoder instances.
 * @param di_bottom The instance on top of which di_top will be stacked.
 * @param di_top The instance to go on top.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @since 0.3.0
 */
SRD_API int srd_inst_stack(struct srd_session *sess,
		struct srd_decoder_inst *di_bottom,
		struct srd_decoder_inst *di_top)
{

	if (session_is_valid(sess) != SRD_OK) {
		srd_err("Invalid session.");
		return SRD_ERR_ARG;
	}

	if (!di_bottom || !di_top) {
		srd_err("Invalid from/to instance pair.");
		return SRD_ERR_ARG;
	}

	if (g_slist_find(sess->di_list, di_top)) {
		/* Remove from the unstacked list. */
		sess->di_list = g_slist_remove(sess->di_list, di_top);
	}

	/* Stack on top of source di. */
	di_bottom->next_di = g_slist_append(di_bottom->next_di, di_top);

	srd_dbg("Stacked %s onto %s.", di_top->inst_id, di_bottom->inst_id);

	return SRD_OK;
}

/**
 * Search a decoder instance and its stack for instance ID.
 *
 * @param[in] inst_id ID to search for.
 * @param[in] stack A decoder instance, potentially with stacked instances.
 *
 * @return The matching instance, or NULL.
 */
static struct srd_decoder_inst *srd_inst_find_by_id_stack(const char *inst_id,
		struct srd_decoder_inst *stack)
{
	const GSList *l;
	struct srd_decoder_inst *tmp, *di;

	if (!strcmp(stack->inst_id, inst_id))
		return stack;

	/* Otherwise, look recursively in our stack. */
	di = NULL;
	if (stack->next_di) {
		for (l = stack->next_di; l; l = l->next) {
			tmp = l->data;
			if (!strcmp(tmp->inst_id, inst_id)) {
				di = tmp;
				break;
			}
		}
	}

	return di;
}

/**
 * Find a decoder instance by its instance ID.
 *
 * This will recurse to find the instance anywhere in the stack tree of the
 * given session.
 *
 * @param sess The session holding the protocol decoder instance.
 * @param inst_id The instance ID to be found.
 *
 * @return Pointer to struct srd_decoder_inst, or NULL if not found.
 *
 * @since 0.3.0
 */
SRD_API struct srd_decoder_inst *srd_inst_find_by_id(struct srd_session *sess,
		const char *inst_id)
{
	GSList *l;
	struct srd_decoder_inst *tmp, *di;

	if (session_is_valid(sess) != SRD_OK) {
		srd_err("Invalid session.");
		return NULL;
	}

	di = NULL;
	for (l = sess->di_list; l; l = l->next) {
		tmp = l->data;
		if ((di = srd_inst_find_by_id_stack(inst_id, tmp)) != NULL)
			break;
	}

	return di;
}

static struct srd_decoder_inst *srd_sess_inst_find_by_obj(
		struct srd_session *sess, const GSList *stack,
		const PyObject *obj)
{
	const GSList *l;
	struct srd_decoder_inst *tmp, *di;

	if (session_is_valid(sess) != SRD_OK) {
		srd_err("Invalid session.");
		return NULL;
	}

	di = NULL;
	for (l = stack ? stack : sess->di_list; di == NULL && l != NULL; l = l->next) {
		tmp = l->data;
		if (tmp->py_inst == obj)
			di = tmp;
		else if (tmp->next_di)
			di = srd_sess_inst_find_by_obj(sess, tmp->next_di, obj);
	}

	return di;
}

/**
 * Find a decoder instance by its Python object.
 *
 * I.e. find that instance's instantiation of the sigrokdecode.Decoder class.
 * This will recurse to find the instance anywhere in the stack tree of all
 * sessions.
 *
 * @param stack Pointer to a GSList of struct srd_decoder_inst, indicating the
 *              stack to search. To start searching at the bottom level of
 *              decoder instances, pass NULL.
 * @param obj The Python class instantiation.
 *
 * @return Pointer to struct srd_decoder_inst, or NULL if not found.
 *
 * @private
 *
 * @since 0.1.0
 */
SRD_PRIV struct srd_decoder_inst *srd_inst_find_by_obj(const GSList *stack,
		const PyObject *obj)
{
	struct srd_decoder_inst *di;
	struct srd_session *sess;
	GSList *l;

	di = NULL;
	for (l = sessions; di == NULL && l != NULL; l = l->next) {
		sess = l->data;
		di = srd_sess_inst_find_by_obj(sess, stack, obj);
	}

	return di;
}

/**
 * Set the list of initial (assumed) pin values.
 *
 * If the list already exists, do nothing.
 *
 * @param di Decoder instance to use. Must not be NULL.
 *
 * @private
 */
static void set_initial_pin_values(struct srd_decoder_inst *di)
{
	int i;
	GString *s;
	PyObject *py_initial_pins;

	if (!di || !di->py_inst) {
		srd_err("Invalid decoder instance.");
		return;
	}

	/* Nothing to do if di->old_pins_array is already != NULL. */
	if (di->old_pins_array) {
		srd_dbg("Initial pins already set, nothing to do.");
		return;
	}

	/* Create an array of old (previous sample) pins, init to 0. */
	di->old_pins_array = g_array_sized_new(FALSE, TRUE, sizeof(uint8_t), di->dec_num_channels);
	g_array_set_size(di->old_pins_array, di->dec_num_channels);

	/* Check if the decoder has set self.initial_pins. */
	if (!PyObject_HasAttrString(di->py_inst, "initial_pins")) {
		srd_dbg("Initial pins: all 0 (self.initial_pins not set).");
		return;
	}

	/* Get self.initial_pins. */
	py_initial_pins = PyObject_GetAttrString(di->py_inst, "initial_pins");

	/* Fill di->old_pins_array based on self.initial_pins. */
	s = g_string_sized_new(100);
	for (i = 0; i < di->dec_num_channels; i++) {
		di->old_pins_array->data[i] = PyLong_AsLong(PyList_GetItem(py_initial_pins, i));
		g_string_append_printf(s, "%d, ", di->old_pins_array->data[i]);
	}
	s = g_string_truncate(s, s->len - 2);
	srd_dbg("Initial pins: %s.", s->str);
	g_string_free(s, TRUE);
}

/** @private */
SRD_PRIV int srd_inst_start(struct srd_decoder_inst *di)
{
	PyObject *py_res;
	GSList *l;
	struct srd_decoder_inst *next_di;
	int ret;

	srd_dbg("Calling start() method on protocol decoder instance %s.",
			di->inst_id);

	/* Run self.start(). */
	if (!(py_res = PyObject_CallMethod(di->py_inst, "start", NULL))) {
		srd_exception_catch("Protocol decoder instance %s",
				di->inst_id);
		return SRD_ERR_PYTHON;
	}
	Py_DecRef(py_res);

	/* Set the initial pins based on self.initial_pins. */
	set_initial_pin_values(di);

	/* Set self.samplenum to 0. */
	PyObject_SetAttrString(di->py_inst, "samplenum", PyLong_FromLong(0));

	/* Set self.matched to None. */
	PyObject_SetAttrString(di->py_inst, "matched", Py_None);

	/* Start all the PDs stacked on top of this one. */
	for (l = di->next_di; l; l = l->next) {
		next_di = l->data;
		if ((ret = srd_inst_start(next_di)) != SRD_OK)
			return ret;
	}

	return SRD_OK;
}

/**
 * Check whether the specified sample matches the specified term.
 *
 * In the case of SRD_TERM_SKIP, this function can modify
 * term->num_samples_already_skipped.
 *
 * @param old_sample The value of the previous sample (0/1).
 * @param sample The value of the current sample (0/1).
 * @param term The term that should be checked for a match. Must not be NULL.
 *
 * @retval TRUE The current sample matches the specified term.
 * @retval FALSE The current sample doesn't match the specified term, or an
 *               invalid term was provided.
 *
 * @private
 */
static gboolean sample_matches(uint8_t old_sample, uint8_t sample, struct srd_term *term)
{
	if (!term)
		return FALSE;

	switch (term->type) {
	case SRD_TERM_HIGH:
		if (sample == 1)
			return TRUE;
		break;
	case SRD_TERM_LOW:
		if (sample == 0)
			return TRUE;
		break;
	case SRD_TERM_RISING_EDGE:
		if (old_sample == 0 && sample == 1)
			return TRUE;
		break;
	case SRD_TERM_FALLING_EDGE:
		if (old_sample == 1 && sample == 0)
			return TRUE;
		break;
	case SRD_TERM_EITHER_EDGE:
		if ((old_sample == 1 && sample == 0) || (old_sample == 0 && sample == 1))
			return TRUE;
		break;
	case SRD_TERM_NO_EDGE:
		if ((old_sample == 0 && sample == 0) || (old_sample == 1 && sample == 1))
			return TRUE;
		break;
	case SRD_TERM_SKIP:
		if (term->num_samples_already_skipped == term->num_samples_to_skip)
			return TRUE;
		term->num_samples_already_skipped++;
		break;
	default:
		srd_err("Unknown term type %d.", term->type);
		break;
	}

	return FALSE;
}

SRD_PRIV void match_array_free(struct srd_decoder_inst *di)
{
	if (!di || !di->match_array)
		return;

	g_array_free(di->match_array, TRUE);
	di->match_array = NULL;
}

SRD_PRIV void condition_list_free(struct srd_decoder_inst *di)
{
	GSList *l, *ll;

	if (!di)
		return;

	for (l = di->condition_list; l; l = l->next) {
		ll = l->data;
		if (ll)
			g_slist_free_full(ll, g_free);
	}

	di->condition_list = NULL;
}

static gboolean have_non_null_conds(const struct srd_decoder_inst *di)
{
	GSList *l, *cond;

	if (!di)
		return FALSE;

	for (l = di->condition_list; l; l = l->next) {
		cond = l->data;
		if (cond)
			return TRUE;
	}

	return FALSE;
}

static void update_old_pins_array(struct srd_decoder_inst *di,
		const uint8_t *sample_pos)
{
	uint8_t sample;
	int i, byte_offset, bit_offset;

	if (!di || !di->dec_channelmap || !sample_pos)
		return;

	for (i = 0; i < di->dec_num_channels; i++) {
		byte_offset = di->dec_channelmap[i] / 8;
		bit_offset = di->dec_channelmap[i] % 8;
		sample = *(sample_pos + byte_offset) & (1 << bit_offset) ? 1 : 0;
		di->old_pins_array->data[i] = sample;
	}
}

static gboolean term_matches(const struct srd_decoder_inst *di,
		struct srd_term *term, const uint8_t *sample_pos)
{
	uint8_t old_sample, sample;
	int byte_offset, bit_offset, ch;

	if (!di || !di->dec_channelmap || !term || !sample_pos)
		return FALSE;

	/* Overwritten below (or ignored for SRD_TERM_SKIP). */
	old_sample = sample = 0;

	if (term->type != SRD_TERM_SKIP) {
		ch = term->channel;
		byte_offset = di->dec_channelmap[ch] / 8;
		bit_offset = di->dec_channelmap[ch] % 8;
		sample = *(sample_pos + byte_offset) & (1 << bit_offset) ? 1 : 0;
		old_sample = di->old_pins_array->data[ch];
	}

	return sample_matches(old_sample, sample, term);
}

static gboolean all_terms_match(const struct srd_decoder_inst *di,
		const GSList *cond, const uint8_t *sample_pos)
{
	const GSList *l;
	struct srd_term *term;

	if (!di || !cond || !sample_pos)
		return FALSE;

	for (l = cond; l; l = l->next) {
		term = l->data;
		if (!term_matches(di, term, sample_pos))
			return FALSE;
	}

	return TRUE;
}

static gboolean at_least_one_condition_matched(
		const struct srd_decoder_inst *di, unsigned int num_conditions)
{
	unsigned int i;

	if (!di)
		return FALSE;

	for (i = 0; i < num_conditions; i++) {
		if (di->match_array->data[i])
			return TRUE;
	}

	return FALSE;
}

static gboolean find_match(struct srd_decoder_inst *di)
{
	static uint64_t s = 0;
	uint64_t i, j, num_samples_to_process;
	GSList *l, *cond;
	const uint8_t *sample_pos;
	unsigned int num_conditions;

	/* Check whether the condition list is NULL/empty. */
	if (!di->condition_list) {
		srd_dbg("NULL/empty condition list, automatic match.");
		return TRUE;
	}

	/* Check whether we have any non-NULL conditions. */
	if (!have_non_null_conds(di)) {
		srd_dbg("Only NULL conditions in list, automatic match.");
		return TRUE;
	}

	num_samples_to_process = di->abs_end_samplenum - di->abs_cur_samplenum;
	num_conditions = g_slist_length(di->condition_list);

	/* di->match_array is NULL here. Create a new GArray. */
	di->match_array = g_array_sized_new(FALSE, TRUE, sizeof(gboolean), num_conditions);
	g_array_set_size(di->match_array, num_conditions);

	for (i = 0, s = 0; i < num_samples_to_process; i++, s++, (di->abs_cur_samplenum)++) {

		sample_pos = di->inbuf + ((di->abs_cur_samplenum - di->abs_start_samplenum) * di->data_unitsize);

		/* Check whether the current sample matches at least one of the conditions (logical OR). */
		/* IMPORTANT: We need to check all conditions, even if there was a match already! */
		for (l = di->condition_list, j = 0; l; l = l->next, j++) {
			cond = l->data;
			if (!cond)
				continue;
			/* All terms in 'cond' must match (logical AND). */
			di->match_array->data[j] = all_terms_match(di, cond, sample_pos);
		}

		update_old_pins_array(di, sample_pos);

		/* If at least one condition matched we're done. */
		if (at_least_one_condition_matched(di, num_conditions))
			return TRUE;
	}

	return FALSE;
}

/**
 * Process available samples and check if they match the defined conditions.
 *
 * This function returns if there is an error, or when a match is found, or
 * when all samples have been processed (whether a match was found or not).
 *
 * @param di The decoder instance to use. Must not be NULL.
 * @param found_match Will be set to TRUE if at least one condition matched,
 *                    FALSE otherwise. Must not be NULL.
 *
 * @retval SRD_OK No errors occured, see found_match for the result.
 * @retval SRD_ERR_ARG Invalid arguments.
 *
 * @private
 */
SRD_PRIV int process_samples_until_condition_match(struct srd_decoder_inst *di, gboolean *found_match)
{
	if (!di || !found_match)
		return SRD_ERR_ARG;

	/* Check if any of the current condition(s) match. */
	while (TRUE) {
		/* Feed the (next chunk of the) buffer to find_match(). */
		*found_match = find_match(di);

		/* Did we handle all samples yet? */
		if (di->abs_cur_samplenum >= di->abs_end_samplenum) {
			srd_dbg("Done, handled all samples (abs cur %" PRIu64
				" / abs end %" PRIu64 ").",
				di->abs_cur_samplenum, di->abs_end_samplenum);
			return SRD_OK;
		}

		/* If we didn't find a match, continue looking. */
		if (!(*found_match))
			continue;

		/* At least one condition matched, return. */
		return SRD_OK;
	}

	return SRD_OK;
}

/**
 * Worker thread (per PD-stack).
 *
 * @param data Pointer to the lowest-level PD's device instance.
 *             Must not be NULL.
 *
 * @return NULL if there was an error.
 */
static gpointer di_thread(gpointer data)
{
	PyObject *py_res;
	struct srd_decoder_inst *di;

	if (!data)
		return NULL;

	di = data;

	/* Call self.decode(). Only returns if the PD throws an exception. */
	Py_IncRef(di->py_inst);
	if (!(py_res = PyObject_CallMethod(di->py_inst, "decode", NULL))) {
		srd_exception_catch("Protocol decoder instance %s: ", di->inst_id);
		exit(1); /* TODO: Proper shutdown. This is a hack. */
		return NULL;
	}
	Py_DecRef(py_res);

	return NULL;
}

/**
 * Decode a chunk of samples.
 *
 * The calls to this function must provide the samples that shall be
 * used by the protocol decoder
 *  - in the correct order ([...]5, 6, 4, 7, 8[...] is a bug),
 *  - starting from sample zero (2, 3, 4, 5, 6[...] is a bug),
 *  - consecutively, with no gaps (0, 1, 2, 4, 5[...] is a bug).
 *
 * The start- and end-sample numbers are absolute sample numbers (relative
 * to the start of the whole capture/file/stream), i.e. they are not relative
 * sample numbers within the chunk specified by 'inbuf' and 'inbuflen'.
 *
 * Correct example (4096 samples total, 4 chunks @ 1024 samples each):
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *   srd_inst_decode(di, 1024, 2048, inbuf, 1024, 1);
 *   srd_inst_decode(di, 2048, 3072, inbuf, 1024, 1);
 *   srd_inst_decode(di, 3072, 4096, inbuf, 1024, 1);
 *
 * The chunk size ('inbuflen') can be arbitrary and can differ between calls.
 *
 * Correct example (4096 samples total, 7 chunks @ various samples each):
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *   srd_inst_decode(di, 1024, 1124, inbuf,  100, 1);
 *   srd_inst_decode(di, 1124, 1424, inbuf,  300, 1);
 *   srd_inst_decode(di, 1424, 1643, inbuf,  219, 1);
 *   srd_inst_decode(di, 1643, 2048, inbuf,  405, 1);
 *   srd_inst_decode(di, 2048, 3072, inbuf, 1024, 1);
 *   srd_inst_decode(di, 3072, 4096, inbuf, 1024, 1);
 *
 * INCORRECT example (4096 samples total, 4 chunks @ 1024 samples each, but
 * the start- and end-samplenumbers are not absolute):
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *   srd_inst_decode(di, 0,    1024, inbuf, 1024, 1);
 *
 * @param di The decoder instance to call. Must not be NULL.
 * @param abs_start_samplenum The absolute starting sample number for the
 * 		buffer's sample set, relative to the start of capture.
 * @param abs_end_samplenum The absolute ending sample number for the
 * 		buffer's sample set, relative to the start of capture.
 * @param inbuf The buffer to decode. Must not be NULL.
 * @param inbuflen Length of the buffer. Must be > 0.
 * @param unitsize The number of bytes per sample. Must be > 0.
 *
 * @return SRD_OK upon success, a (negative) error code otherwise.
 *
 * @private
 */
SRD_PRIV int srd_inst_decode(struct srd_decoder_inst *di,
		uint64_t abs_start_samplenum, uint64_t abs_end_samplenum,
		const uint8_t *inbuf, uint64_t inbuflen, uint64_t unitsize)
{
	PyObject *py_res;
	srd_logic *logic;
	long apiver;

	/* Return an error upon unusable input. */
	if (!di) {
		srd_dbg("empty decoder instance");
		return SRD_ERR_ARG;
	}
	if (!inbuf) {
		srd_dbg("NULL buffer pointer");
		return SRD_ERR_ARG;
	}
	if (inbuflen == 0) {
		srd_dbg("empty buffer");
		return SRD_ERR_ARG;
	}
	if (unitsize == 0) {
		srd_dbg("unitsize 0");
		return SRD_ERR_ARG;
	}

	if (abs_start_samplenum != di->abs_cur_samplenum ||
	    abs_end_samplenum < abs_start_samplenum) {
		srd_dbg("Incorrect sample numbers: start=%" PRIu64 ", cur=%"
			PRIu64 ", end=%" PRIu64 ".", abs_start_samplenum,
			di->abs_cur_samplenum, abs_end_samplenum);
		return SRD_ERR_ARG;
	}

	di->data_unitsize = unitsize;

	srd_dbg("Decoding: abs start sample %" PRIu64 ", abs end sample %"
		PRIu64 " (%" PRIu64 " samples, %" PRIu64 " bytes, unitsize = "
		"%d), instance %s.", abs_start_samplenum, abs_end_samplenum,
		abs_end_samplenum - abs_start_samplenum, inbuflen, di->data_unitsize,
		di->inst_id);

	apiver = srd_decoder_apiver(di->decoder);

	if (apiver == 2) {
		/*
		 * Create new srd_logic object. Each iteration around the PD's
		 * loop will fill one sample into this object.
		 */
		logic = PyObject_New(srd_logic, (PyTypeObject *)srd_logic_type);
		Py_INCREF(logic);
		logic->di = (struct srd_decoder_inst *)di;
		logic->abs_start_samplenum = abs_start_samplenum;
		logic->itercnt = 0;
		logic->inbuf = (uint8_t *)inbuf;
		logic->inbuflen = inbuflen;
		logic->sample = PyList_New(2);
		Py_INCREF(logic->sample);

		Py_IncRef(di->py_inst);
		if (!(py_res = PyObject_CallMethod(di->py_inst, "decode",
			"KKO", abs_start_samplenum, abs_end_samplenum, logic))) {
			srd_exception_catch("Protocol decoder instance %s",
					di->inst_id);
			return SRD_ERR_PYTHON;
		}
		di->abs_cur_samplenum = abs_end_samplenum;
		Py_DecRef(py_res);
	} else {
		/* If this is the first call, start the worker thread. */
		if (!di->thread_handle) {
			srd_dbg("No worker thread for this decoder stack "
				"exists yet, creating one: %s.", di->inst_id);
			di->thread_handle = g_thread_new(di->inst_id,
							 di_thread, di);
		}

		/* Push the new sample chunk to the worker thread. */
		g_mutex_lock(&di->data_mutex);
		di->abs_start_samplenum = abs_start_samplenum;
		di->abs_end_samplenum = abs_end_samplenum;
		di->inbuf = inbuf;
		di->inbuflen = inbuflen;
		di->got_new_samples = TRUE;
		di->handled_all_samples = FALSE;

		/* Signal the thread that we have new data. */
		g_cond_signal(&di->got_new_samples_cond);
		g_mutex_unlock(&di->data_mutex);

		/* When all samples in this chunk were handled, return. */
		g_mutex_lock(&di->data_mutex);
		while (!di->handled_all_samples)
			g_cond_wait(&di->handled_all_samples_cond, &di->data_mutex);
		g_mutex_unlock(&di->data_mutex);
	}

	return SRD_OK;
}

/** @private */
SRD_PRIV void srd_inst_free(struct srd_decoder_inst *di)
{
	GSList *l;
	struct srd_pd_output *pdo;

	srd_dbg("Freeing instance %s", di->inst_id);

	Py_DecRef(di->py_inst);
	g_free(di->inst_id);
	g_free(di->dec_channelmap);
	g_free(di->channel_samples);
	g_slist_free(di->next_di);
	for (l = di->pd_output; l; l = l->next) {
		pdo = l->data;
		g_free(pdo->proto_id);
		g_free(pdo);
	}
	g_slist_free(di->pd_output);
	g_free(di);
}

/** @private */
SRD_PRIV void srd_inst_free_all(struct srd_session *sess)
{
	if (session_is_valid(sess) != SRD_OK) {
		srd_err("Invalid session.");
		return;
	}

	g_slist_free_full(sess->di_list, (GDestroyNotify)srd_inst_free);
}

/** @} */
