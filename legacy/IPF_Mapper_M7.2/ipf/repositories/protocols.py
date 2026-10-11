"""Repository contracts marker for V1.
Concrete SQLite repositories expose persistence only. Services own use-cases,
transactions and copy-on-write semantics. Domain/engines must not import SQLite.
"""
from typing import Protocol
class Repository(Protocol): ...
