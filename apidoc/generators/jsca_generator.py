#!/usr/bin/env python
#
# Copyright (c) 2010-2011 Appcelerator, Inc. All Rights Reserved.
# Licensed under the Apache Public License (version 2)

import os, sys, re

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(this_dir, "..")))

from common import dict_has_non_empty_member, strip_tags, not_real_titanium_types, to_ordered_dict

android_support_dir = os.path.abspath(os.path.join(this_dir, "..", "..", "support", "android"))
sys.path.append(android_support_dir)

# We package the python markdown module already in /support/module/support/markdown.
module_support_dir = os.path.abspath(os.path.join(this_dir, "..", "..", "support", "module", "support"))
sys.path.append(module_support_dir)
from markdown import markdown

from tilogger import *
log = None
all_annotated_apis = None

try:
	import json
except:
	import simplejson as json

def markdown_to_html(s):
	# TODO our type stuff
	return markdown(s)

# Fixes illegal names like "2DMatrix" (not valid Javascript name)
def clean_namespace(ns_in):
	def clean_part(part):
		if len(part) and part[0].isdigit():
			return "_" + part
		else:
			return part
	return ".".join([clean_part(s) for s in ns_in.split(".") ])

def to_jsca_description(desc):
	if desc is None:
		return ""
	return markdown_to_html(desc)

def to_jsca_example(example):
	return {
			"name": example["title"],
			"code": markdown_to_html(example["example"])
			}

def to_jsca_examples(api):
	if dict_has_non_empty_member(api.api_obj, "examples"):
		return [to_jsca_example(example) for example in api.api_obj["examples"]]
	else:
		return []

def to_jsca_type_name(type_info):
	if isinstance(type_info, list) or isinstance(type_info, tuple) and len(type_info) > 0:
		return to_jsca_type_name(type_info[0])
	type_test = type_info
	if type_test.startswith("Callback"):
		type_test ="Function"
	elif type_test.startswith("Array"):
		type_test = "Array"
	return clean_namespace(type_test)

def to_jsca_property(prop, for_event=False):
	result = {
			"name": prop.name,
			"description": to_jsca_description(prop.api_obj["description"]),
			"type": "" if "type" not in prop.api_obj else to_jsca_type_name(prop.api_obj["type"])
			}
	if not for_event:
		result["isClassProperty"] = (prop.name == prop.name.upper())
		result["isInstanceProperty"] = (prop.name != prop.name.upper())
		result["since"] = to_jsca_since(prop.platforms)
		result["userAgents"] = to_jsca_userAgents(prop.platforms)
		result["isInternal"] = False
		result["examples"] = to_jsca_examples(prop)
	return to_ordered_dict(result, ("name",))

def to_jsca_properties(props, for_event=False):
	return [to_jsca_property(prop, for_event) for prop in props]

def to_jsca_return_types(return_types):
	if return_types is None or len(return_types) == 0:
		return []
	orig_types = return_types
	if not isinstance(orig_types, list):
		orig_types = [orig_types]
	return [{
		"type": to_jsca_type_name(t["type"]),
		"description": "" if "description" not in t else to_jsca_description(t["description"])
		} for t in orig_types]

def to_jsca_method_parameter(p):
	type_spec = p.api_obj["type"]
	if isinstance(type_spec,str) or isinstance(type_spec,unicode):
		if type_spec.lower().startswith("dictionary<") and p.parent.name.startswith("create"):
			# jsca wants the parameter type for createXXXX to be the type that is created by it.
			if "returns" in p.parent.api_obj:
				method_return_type = p.parent.api_obj["returns"]["type"]
				if method_return_type in type_spec:
					type_spec = method_return_type

	result = {
			"name": p.name,
			"description": to_jsca_description(p.api_obj["description"]),
			"type": to_jsca_type_name(type_spec),
			"usage": "optional" if "optional" in p.api_obj and p.api_obj["optional"] else "required"
			}
	return to_ordered_dict(result, ('name',))

def to_jsca_function(method):
	log.trace("%s.%s" % (method.parent.name, method.name))
	result = {
			"name": method.name,
			"description": "" if "description" not in method.api_obj else to_jsca_description(method.api_obj["description"])
			}
	if dict_has_non_empty_member(method.api_obj, "returns") and method.api_obj["returns"] != "void":
		result["returnTypes"] = to_jsca_return_types(method.api_obj["returns"])
	if method.parameters is not None and len(method.parameters) > 0:
		result["parameters"] = [to_jsca_method_parameter(p) for p in method.parameters]
	result["since"] = to_jsca_since(method.platforms)
	result['userAgents'] = to_jsca_userAgents(method.platforms)
	result['isInstanceProperty'] = True # we don't have class static methods
	result['isClassProperty'] = False # we don't have class static methods
	result['isInternal'] = False # we don't make this distinction (yet anyway)
	result['examples'] = to_jsca_examples(method)
	result['references'] = [] # we don't use the notion of 'references' (yet anyway)
	result['exceptions'] = [] # we don't specify exceptions (yet anyway)
	result['isConstructor'] = False # we don't expose native class constructors
	result['isMethod'] = True # all of our functions are class instance functions, ergo methods
	return to_ordered_dict(result, ('name',))

def to_jsca_functions(methods):
	return [to_jsca_function(method) for method in methods]

def to_jsca_event(event):
	return to_ordered_dict({
			"name": event.name,
			"description": "" if "description" not in event.api_obj else to_jsca_description(event.api_obj["description"]),
			"properties": to_jsca_properties(event.properties, for_event=True)
			}, ("name",))

def to_jsca_events(events):
	return [to_jsca_event(event) for event in events]

def to_jsca_remarks(api):
	if dict_has_non_empty_member(api.api_obj, "notes"):
		return [markdown_to_html(api.api_obj["notes"])]
	else:
		return []

def to_jsca_userAgents(platforms):
	return [{"platform": platform["name"]} for platform in platforms]

def to_jsca_since(platforms):
	return [to_ordered_dict({
		"name": "Titanium Mobile SDK - %s" % platform["pretty_name"],
		"version": platform["since"]
		}, ("name",)) for platform in platforms]

def to_jsca_type(api):
	if api.name in not_real_titanium_types:
		return None
	log.trace("Converting %s to jsca" % api.name)
	result = {
			"name": clean_namespace(api.name),
			"description": to_jsca_description(api.api_obj["description"]),
			"deprecated": api.deprecated is not None and len(api.deprecated) > 0,
			"examples": to_jsca_examples(api),
			"properties": to_jsca_properties(api.properties),
			"functions": to_jsca_functions(api.methods),
			"events": to_jsca_events(api.events),
			"remarks": to_jsca_remarks(api),
			"userAgents": to_jsca_userAgents(api.platforms),
			"since": to_jsca_since(api.platforms)
			}
	return to_ordered_dict(result, ('name',))

def generate(raw_apis, annotated_apis, options):
	global all_annotated_apis, log
	log_level = TiLogger.INFO
	if options.verbose:
		log_level = TiLogger.TRACE
	all_annotated_apis = annotated_apis
	log = TiLogger(None, level=log_level, output_stream=sys.stderr)
	log.info("Generating JSCA")
	result = {'aliases': [ {'name': 'Ti', 'type': 'Titanium'} ]}
	types = []
	result['types'] = types

	for key in all_annotated_apis.keys():
		jsca_type = to_jsca_type(all_annotated_apis[key])
		if jsca_type is not None:
			types.append(jsca_type)

	if options.stdout:
		json.dump(result, sys.stdout, sort_keys=False, indent=4)
	if options.output is not None and len(options.output) > 0:
		if not os.path.exists(options.output):
			os.makedirs(options.output)
		out_path = os.path.join(options.output, "api.jsca")
		f = open(out_path, "w")
		json.dump(result, f, sort_keys=False, indent=4)
		f.close()

