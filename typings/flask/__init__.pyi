from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


class Flask:
    def __init__(self, import_name: str) -> None: ...

    def get(self, rule: str, **options: object) -> Callable[[F], F]: ...

    def run(self, host: str | None = ..., port: int | None = ..., **options: object) -> None: ...


def jsonify(*args: object, **kwargs: object) -> object: ...
