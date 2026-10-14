from jinja2 import DebugUndefined, TemplateNotFound
from jinja2.sandbox import SandboxedEnvironment
import json
from .utils import cint, cstr, flt, as_json, _dict

UNSAFE_ATTRIBUTES = {
	# Generator Attributes
	"gi_frame",
	"gi_code",
	"gi_yieldfrom",
	# Coroutine Attributes
	"cr_frame",
	"cr_code",
	"cr_origin",
	"cr_await",
	# Async Generator Attributes
	"ag_code",
	"ag_frame",
	# Traceback Attributes
	"tb_frame",
	"tb_next",
	# Format Attributes
	"format",
	"format_map",
	# Frame attributes
	"f_back",
	"f_builtins",
	"f_code",
	"f_globals",
	"f_locals",
	"f_trace",
}

# @site_cache(ttl=10 * 60, maxsize=8)
def _get_jloader():
	from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

	# import frappe

	# apps = frappe.get_hooks("template_apps")
	# if not apps:
	# 	apps = list(reversed(frappe.get_active_apps(_ensure_on_bench=True)))

	# if "frappe" not in apps:
	# 	apps.append("frappe")

	jloader = ChoiceLoader(
		# search for something like app/templates/...
		[PrefixLoader({"app": PackageLoader("app", ".")})]
		# search for something like templates/...
		+ [PackageLoader("app", ".")]
	)

	return jloader

def get_jloader():
	jloader = _get_jloader()
	return jloader

def set_filters(jenv):
	jenv.filters.update(
		{
			"json": as_json,
			"len": len,
			"int": cint,
			"str": cstr,
			"flt": flt,
		}
	)

def get_jinja_hooks():
	"""Return a tuple of (methods, filters) each containing a dict of method name and method definition pair."""
	return (None, None)
	# import frappe

	# if not getattr(frappe.local, "site", None):
	# 	return (None, None)

	# from inspect import getmembers, isfunction
	# from types import FunctionType, ModuleType

	# def get_obj_dict_from_paths(object_paths):
	# 	out = {}
	# 	for obj_path in object_paths:
	# 		try:
	# 			obj = frappe.get_module(obj_path)
	# 		except ModuleNotFoundError:
	# 			obj = frappe.get_attr(obj_path)

	# 		if isinstance(obj, ModuleType):
	# 			functions = getmembers(obj, isfunction)
	# 			for function_name, function in functions:
	# 				out[function_name] = function
	# 		elif isinstance(obj, FunctionType):
	# 			function_name = obj.__name__
	# 			out[function_name] = obj
	# 	return out

	# values = frappe.get_hooks("jinja")
	# methods, filters = values.get("methods", []), values.get("filters", [])

	# method_dict = get_obj_dict_from_paths(methods)
	# filter_dict = get_obj_dict_from_paths(filters)

	# return method_dict, filter_dict

# @site_cache(ttl=10 * 60, maxsize=4)
def _get_jenv():
	# XXX: DO NOT use any thread/request specific data in this function!
	# Some functionality like `get_safe_globals` appears safe but internally uses request local
	# data.
	JENV_UNSAFE_ATTRIBUTES = UNSAFE_ATTRIBUTES - {"format", "format_map"}

	class TemplateSandboxedEnvironment(SandboxedEnvironment):
		def is_safe_attribute(self, obj, attr, *args, **kwargs):
			if attr in JENV_UNSAFE_ATTRIBUTES:
				return False

			return super().is_safe_attribute(obj, attr, *args, **kwargs)

	# frappe will be loaded last, so app templates will get precedence
	jenv = TemplateSandboxedEnvironment(loader=get_jloader(), undefined=DebugUndefined, cache_size=32)
	set_filters(jenv)

	return jenv

class NamespaceDict(_dict):
	"""Raise AttributeError if function not found in namespace"""

	def __getattr__(self, key):
		ret = self.get(key)
		if (not ret and key.startswith("__")) or (key not in self):

			def default_function(*args, **kwargs):
				raise AttributeError(f"module has no attribute '{key}'")

			return default_function
		return ret

def get_safe_globals():
	out = NamespaceDict(
		# make available limited methods of frappe
		json=NamespaceDict(loads=json.loads, dumps=json.dumps),
		as_json=as_json,
		dict=dict,
		_dict=_dict
	)
	return out

def get_jenv(*, restrict_globals=None):
	# import frappe
	# from frappe.utils.safe_exec import render_safe_globals

	# if restrict_globals is None:
	# 	restrict_globals = is_render_exec_enabled()

	# local_key = "jenv_restricted" if restrict_globals else "jenv_unrestricted"
	# if jenv := getattr(frappe.local, local_key, None):
	# 	return jenv

	default_jenv = _get_jenv()
	jenv = default_jenv.overlay()
	# XXX: This is safe to share between requests, the only reason why we are overlaying jenv is to
	# reuse cache but still have request specific jenv object.
	# if not frappe._dev_server:
	# 	jenv.cache = default_jenv.cache
	jenv.cache = default_jenv.cache

	# Note: Overlay by default is "linked", we need to copy everything we are updating.
	jenv.globals = default_jenv.globals.copy()
	jenv.filters = default_jenv.filters.copy()

	# if restrict_globals:
	# 	jenv.globals.update(render_safe_globals())
	# else:
	# 	jenv.globals.update(get_safe_globals())
	jenv.globals.update(get_safe_globals())

	methods, filters = get_jinja_hooks()
	jenv.globals.update(methods or {})
	jenv.filters.update(filters or {})

	# setattr(frappe.local, local_key, jenv)

	return jenv

def get_template(path):
	jenv = get_jenv()
	# Note: jenv globals are reapplied here because we don't have true "global"/"local" separation.
	# Ideally globals should never change as per Jinja design.
	return jenv.get_template(path, globals=jenv.globals)

def get_email_from_template(name, args):

	args = args or {}
	try:
		message = get_template("templates/emails/" + name + ".html").render(args)
	except TemplateNotFound as e:
		raise e

	try:
		text_content = get_template("templates/emails/" + name + ".txt").render(args)
	except TemplateNotFound:
		text_content = None

	return (message, text_content)
