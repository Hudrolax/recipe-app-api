"""
Datebase models.
"""

from enum import unique
from django.db import models
from django.contrib.auth import (
    AbstractBaseUser,
    BaseUserManager,
    PermisionsMixin,
)


class User(AbstractBaseUser, PermisionsMixin):
    """User in the system."""
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
