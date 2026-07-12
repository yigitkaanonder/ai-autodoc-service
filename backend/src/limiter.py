"""
Shared slowapi rate limiter.

Defined in its own module so both main.py (which wires it into the app) and the
routers (which decorate endpoints with @limiter.limit) can import the same
instance without a circular import through main.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
