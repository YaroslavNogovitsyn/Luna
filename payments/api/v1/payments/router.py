__all__ = [
    'router',
]

from fastapi import APIRouter


router = APIRouter(
    prefix='/payments',
)
