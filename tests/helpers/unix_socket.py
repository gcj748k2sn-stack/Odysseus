"""Bind an ``AF_UNIX`` socket at a path short enough for macOS.

``sockaddr_un.sun_path`` is **104 bytes on macOS** (108 on Linux), and macOS
hands processes a deep per-user ``$TMPDIR``. A socket under pytest's ``tmp_path``
therefore overflows on macOS while fitting comfortably on Linux:

    /private/var/folders/96/…/T/pytest-of-…/pytest-3/test_…0/docker.sock   126 B
    /tmp/pytest-of-…/pytest-3/test_…0/docker.sock                           74 B

That difference is why ``OSError: AF_UNIX path too long`` was invisible in CI and
on Linux dev machines for as long as these tests existed. Bind under a short
root instead of ``tmp_path``; see notes/todo.md item 19.
"""
import os
import socket
import tempfile
from contextlib import contextmanager

# Short enough that the socket path stays well inside 104 bytes. Not tmp_path:
# its length is the whole problem.
_SHORT_ROOT = "/tmp"


@contextmanager
def bound_unix_socket(name: str = "s.sock"):
    """Yield the path of a bound ``AF_UNIX`` socket, cleaned up on exit.

    The socket is bound (so ``stat.S_ISSOCK`` holds for anything probing the
    path) but never listens or accepts — callers here only need a real socket
    inode to exist. Keep ``name`` short; the budget is 104 bytes total.
    """
    with tempfile.TemporaryDirectory(dir=_SHORT_ROOT) as tmp_root:
        sock_path = os.path.join(tmp_root, name)
        if len(sock_path) >= 104:
            raise AssertionError(
                f"socket path is {len(sock_path)} bytes, over the 104-byte "
                f"AF_UNIX limit on macOS: {sock_path}"
            )
        with socket.socket(socket.AF_UNIX) as unix_socket:
            unix_socket.bind(sock_path)
            yield sock_path
