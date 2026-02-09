from __future__ import annotations

import re

from fastapi import HTTPException, Request


_USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def get_user_id(request: Request, *, allow_query_param: bool = False) -> str:
    """Return the current user id.

    MVP auth:
    - REST requests provide `X-User-Id` header.
    - SSE requests may provide `?user_id=` because EventSource can't set headers.
    """

    user_id = request.headers.get("X-User-Id")
    if allow_query_param and not user_id:
        user_id = request.query_params.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id")

    if not _USER_RE.match(user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    return user_id
