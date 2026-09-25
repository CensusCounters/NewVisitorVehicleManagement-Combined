"""Load a workflow module for the immutable active site profile."""

from functools import lru_cache
from importlib import import_module

from finalfrsproject import app


@lru_cache(maxsize=None)
def get_workflow(module_name):
    profile = app.config["SITE_PROFILE"]
    return import_module(f"finalfrsproject.site_workflows.{profile}.{module_name}")
