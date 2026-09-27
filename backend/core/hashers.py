"""Password hashing tuned for this deployment.

Django's `Argon2PasswordHasher` defaults to memory_cost=102400 (100 MiB) with
parallelism=8, which is generous but costs several seconds per sign-in on a
modest or busy VPS — slow enough to be mistaken for a hung request.

These are the OWASP Password Storage Cheat Sheet's recommended Argon2id
parameters (m=19 MiB, t=2, p=1): still a deliberately expensive hash, an order
of magnitude stronger than the PBKDF2 default it replaces, and fast enough that
signing in feels instant.
"""

from django.contrib.auth.hashers import Argon2PasswordHasher


class TunedArgon2PasswordHasher(Argon2PasswordHasher):
    #: 19 MiB — OWASP minimum for Argon2id.
    memory_cost = 19456
    time_cost = 2
    parallelism = 1
