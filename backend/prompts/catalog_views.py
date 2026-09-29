"""Authenticated HTTP endpoints for the versioned prompt catalog."""
from functools import wraps

from django.http import JsonResponse

from accounts.models import User
from common.api import api_error_response, json_body, require_auth
from library.models import LibraryOrder
from . import catalog
from .models import PromptVersion


def endpoint(method):
    def decorate(function):
        @require_auth
        @wraps(function)
        def view(request, **kwargs):
            if request.method != method:
                return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
            try:
                user = catalog.actor(request.user_id)
                data = json_body(request) if method == "POST" else {}
                if not isinstance(data, dict):
                    raise catalog.CatalogError("请求必须是 JSON 对象")
                return JsonResponse({"success": True, **function(request, user, data, **kwargs)})
            except catalog.CatalogError as error:
                return JsonResponse({"success": False, "error_message": str(error)}, status=error.status)
            except Exception as error:
                return api_error_response(error, context={"endpoint": request.path})
        return view
    return decorate


@endpoint("GET")
def listing(request, user, data):
    entries = catalog.entries_for(user, manage=request.GET.get("manage") == "1")
    orders = {}
    for item in catalog.CATEGORIES:
        key = f'{item["module"]}.{item["category"]}'
        row = LibraryOrder.objects.filter(user=user, resource="prompt-center", kind=key).first()
        orders[key] = {
            "ids": catalog.ordered_ids(user, item["module"], item["category"], row.order if row else []),
            "revision": row.revision if row else 0,
        }
    return {"entries": [catalog.serialize(entry, user) for entry in entries],
            "categories": catalog.CATEGORIES, "orders": orders}


@endpoint("POST")
def save(request, user, data):
    return {"entry": catalog.save(user, data)}


@endpoint("POST")
def copy(request, user, data):
    return {"entry": catalog.copy(user, data)}


@endpoint("POST")
def restore(request, user, data):
    return {"entry": catalog.restore(user, data)}


@endpoint("POST")
def reorder(request, user, data):
    return {"revision": catalog.reorder(user, data)}


@endpoint("GET")
def versions(request, user, data, entry_id):
    entry = catalog.get_entry(user, entry_id, edit=True)
    return {"versions": [
        {"revision": version.number, **version.snapshot, "snapshot": version.snapshot,
         "actor_name": version.actor.username if version.actor_id else "系统",
         "created_at": version.created_at.isoformat()}
        for version in PromptVersion.objects.filter(entry=entry).select_related("actor")
    ]}


@endpoint("GET")
def users(request, user, data):
    return {"users": list(User.objects.order_by("username").values("id", "username"))}
