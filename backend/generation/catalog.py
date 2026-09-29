"""Catalog scope belongs to the authenticated actor, not the generated record."""
from functools import wraps
from common.api import api_error_response
from prompts.catalog_runtime import prompt_scope


def catalog_request(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            with prompt_scope(request.user_id):
                return view(request, *args, **kwargs)
        except ValueError as error:
            return api_error_response(str(error), status=getattr(error, "status", 400))
    return wrapped
