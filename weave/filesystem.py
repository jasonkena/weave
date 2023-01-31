# Official sync/async interface for filesystem operations. All
# weave interactions with the filesystem should go through this
# interface.
#
# Important features:
# - Threadsafe atomic read/write operations
# - Root directory controlled via context for access control
#
# Note: The above is not the case yet! We're in the middle of migrating
# to this interface.

import dataclasses
import typing
import contextlib
import contextvars
import os
import aiofiles
import aiofiles.os as aiofiles_os
from aiofiles.threadpool import text as aiofiles_text
from aiofiles.threadpool import binary as aiofiles_binary

from . import engine_trace
from . import errors
from . import util
from . import environment
from . import context_state


tracer = engine_trace.tracer()  # type: ignore


@dataclasses.dataclass
class FilesystemContext:
    path: typing.Optional[str]

    @classmethod
    def from_json(cls, json: typing.Any) -> "FilesystemContext":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return dataclasses.asdict(self)


_filesystem_context: contextvars.ContextVar[
    typing.Optional[FilesystemContext]
] = contextvars.ContextVar("_filesystem_context", default=None)


@contextlib.contextmanager
def filesystem_context(ctx: FilesystemContext) -> typing.Generator[None, None, None]:
    token = _filesystem_context.set(ctx)
    try:
        yield
    finally:
        _filesystem_context.reset(token)


def get_filesystem_context() -> FilesystemContext:
    context = _filesystem_context.get()
    if context is not None:
        return context
    # Default to cache namespace if no context is set.
    cache_namespace = context_state._cache_namespace_token.get()
    return FilesystemContext(cache_namespace)


def is_subdir(path: str, root: str) -> bool:
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return os.path.commonpath([path, root]) == root


def safe_path(path: str, root: str) -> str:
    ctx = get_filesystem_context()
    if ctx is not None and ctx.path is not None:
        root = os.path.join(root, ctx.path)
    result = os.path.join(root, path)
    if not is_subdir(result, root):
        raise errors.WeaveAccessDeniedError(f"Path {path} is not allowed")
    return result


class Filesystem:
    def __init__(self, root: str) -> None:
        self.root = root

    def path(self, path: str) -> str:
        return safe_path(path, self.root)

    def exists(self, path: str) -> bool:
        return os.path.exists(self.path(path))

    def getsize(self, path: str) -> int:
        return os.path.getsize(self.path(path))

    def makedirs(self, path: str, exist_ok: bool) -> None:
        os.makedirs(self.path(path), exist_ok=exist_ok)

    @contextlib.contextmanager
    def open_write(
        self, path: str, mode: str = "wb"
    ) -> typing.Generator[typing.IO, None, None]:
        path = self.path(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_name = f"{path}.tmp-{util.rand_string_n(16)}"
        with open(tmp_name, mode) as f:
            yield f
        with tracer.trace("rename"):
            os.rename(tmp_name, path)

    @contextlib.contextmanager
    def open_read(
        self, path: str, mode: str = "rb"
    ) -> typing.Generator[typing.IO, None, None]:
        with open(self.path(path), mode) as f:
            yield f


class FilesystemAsync:
    def __init__(self, root: str) -> None:
        self.root = root

    def path(self, path: str) -> str:
        return safe_path(path, self.root)

    async def exists(self, path: str) -> bool:
        return await aiofiles_os.path.exists(self.path(path))

    async def getsize(self, path: str) -> int:
        return await aiofiles_os.path.getsize(self.path(path))

    async def makedirs(self, path: str, exist_ok: bool) -> None:
        await aiofiles_os.makedirs(self.path(path), exist_ok=exist_ok)

    # Whew! These type shenaningans were tough to figure out!

    @typing.overload
    def open_write(
        self,
        path: str,
        mode: typing.Literal["w"],
    ) -> typing.AsyncContextManager[aiofiles_text.AsyncTextIOWrapper]:
        ...

    @typing.overload
    def open_write(
        self,
        path: str,
        mode: typing.Literal["wb"] = "wb",
    ) -> typing.AsyncContextManager[aiofiles_binary.AsyncBufferedIOBase]:
        ...

    @contextlib.asynccontextmanager
    async def open_write(
        self,
        path: str,
        mode: typing.Union[typing.Literal["w"], typing.Literal["wb"]] = "wb",
    ) -> typing.Any:
        path = self.path(path)
        await aiofiles_os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_name = f"{path}.tmp-{util.rand_string_n(16)}"
        async with aiofiles.open(tmp_name, mode) as f:
            yield f
        with tracer.trace("rename"):
            await aiofiles_os.rename(tmp_name, path)

    @typing.overload
    def open_read(
        self,
        path: str,
        mode: typing.Literal["r"],
    ) -> typing.AsyncContextManager[aiofiles_text.AsyncTextIOWrapper]:
        ...

    @typing.overload
    def open_read(
        self,
        path: str,
        mode: typing.Literal["rb"] = "rb",
    ) -> typing.AsyncContextManager[aiofiles_binary.AsyncBufferedIOBase]:
        ...

    @contextlib.asynccontextmanager
    async def open_read(
        self,
        path: str,
        mode: typing.Union[typing.Literal["r"], typing.Literal["rb"]] = "rb",
    ) -> typing.Any:
        async with aiofiles.open(self.path(path), mode) as f:
            yield f


def get_filesystem() -> Filesystem:
    return Filesystem(environment.weave_filesystem_dir())


def get_filesystem_async() -> FilesystemAsync:
    return FilesystemAsync(environment.weave_filesystem_dir())