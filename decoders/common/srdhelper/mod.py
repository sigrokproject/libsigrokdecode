# -*- coding: utf-8 -*-
"""
This file is part of the libsigrokdecode project.

Copyright (C) 2012-2014 Uwe Hermann <uwe@hermann-uwe.de>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <http://www.gnu.org/licenses/>.
"""


def bcd2int(b):
    """Return the specified BCD number (max. 8 bits) as integer."""
    return (b & 0x0f) + ((b >> 4) * 10)


def bin2int(s):
    """Return the specified string as integer."""
    return int('0b' + s, 2)


def bitpack(bits):
    """Return the specified bit tuple as integer."""
    return sum([b << i for i, b in enumerate(bits)])


def bitunpack(num, minbits=0):
    """Return the specified number as bit tuple."""
    res = []
    while num or minbits > 0:
        res.append(num & 1)
        num >>= 1
        minbits -= 1
    return tuple(res)


def format_data(data, radix="Hex"):
    """Format data value according to the radix option."""
    radix = radix.upper()
    if radix == "DEC":
        format = "{:#d}"
    elif radix == "BIN":
        format = "{:#b}"
    elif radix == "OCT":
        format = "{:#o}"
    else:
        format = "{:#04x}"
    return format.format(data)


def create_annots(annots_dict):
    """Create a tuple with all annotation definitions dictionary.

    Arguments
    ---------
    annots_dict : dictionary
        Dictionary of annotation definitions in the scheme {prefix: def_dict},
        where:
        prefix : string
            Key of the annotation dictionary as a prefix of the annotation
            name in the Decoder class. It is going to be appended with numeric
            key from the value of the annotation dictionary.
        def_dict : dictionary
            Value of the annotation dictioniary, which is again a dictionary
            defining particular set of annotations.
            - The key of the dictionary is the index of the definition, which
              is an attribute of corresponding annotation class defined in the
              Decoder module outside the Decoder class.
            - The vallue of the dictionary is the list of annotation strings,
              usually from the longest to the shortest.

    Returns
    -------
    tuple of str
        Annotations definitions compliant with Protocol Decoder API.

    """
    annots = []
    for prefix, ann_def in annots_dict.items():
        for ann_idx, ann_list in ann_def.items():
            annots.insert(ann_idx, tuple([prefix + "-" + ann_list[0].lower(),
                                         ann_list[0]]))
    return tuple(annots)


def compose_annot(ann_label="", ann_value=None, ann_unit=None,
                  ann_action=None):
    """Compose list of annotations enriched with value and unit.

    Arguments
    ---------
    ann_label : list
        List of annotation labels for enriching with values and units and
        prefixed with actions.
        If label is none or empty string, there is used neither it nor its
        delimiter, just other arguments, if any.
    ann_value : list
        List of values to be added item by item to all annotations.
    ann_unit : list
        List of measurement units to be added item by item to all
        annotations. The method does not add separation space between
        the value and the unit.
    ann_action : list
        List of action prefixes prepend item by item to all annotations.
        The method separates action and annotation with a space.

    Returns
    -------
    list of str
        List of a annotations potentially enriched with values and units
        with items sorted by length descending.

    Notes
    -----
    - Usually just one value and one unit is used. However for flexibility
      more of them can be used.
    - If the annotation values list is not defined, the annotation units
      list is not used, even if it is defined.

    """
    if ann_label is None:
        ann_label = ""
    if not isinstance(ann_label, list):
        tmp = ann_label
        ann_label = []
        ann_label.append(tmp)

    if ann_value is None:
        ann_value = []
    elif not isinstance(ann_value, list):
        tmp = ann_value
        ann_value = []
        ann_value.append(tmp)

    if ann_unit is None:
        ann_unit = []
    elif not isinstance(ann_unit, list):
        tmp = ann_unit
        ann_unit = []
        ann_unit.append(tmp)

    if ann_action is None:
        ann_action = []
    elif not isinstance(ann_action, list):
        tmp = ann_action
        ann_action = []
        ann_action.append(tmp)
    if len(ann_action) == 0:
        ann_action = [""]

    # Compose annotation
    annots = []
    for act in ann_action:
        for lbl in ann_label:
            ann = "{} {}".format(act, lbl).strip()
            ann_item = None
            for val in ann_value:
                if len(ann) > 0:
                    ann_item = "{}: {}".format(ann, val)
                else:
                    ann_item = "{}".format(val)
                annots.append(ann_item)  # Without units
                for unit in ann_unit:
                    ann_item += "{}".format(unit)
                    annots.append(ann_item)  # With units
            if ann_item is None:
                annots.append(ann)

    # Add last 2 annotation items without values
    if len(ann_value) > 0:
        for ann in ann_label[-2:]:
            if len(ann) > 0:
                annots.append(ann)
    annots.sort(key=len, reverse=True)
    return annots
