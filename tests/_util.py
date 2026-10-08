"""テストの共通処理."""

import os
import shutil
import stat
import sys
from pathlib import Path


def rmtree(path: Path) -> None:
    """一時ディレクトリを消す. Windows では git のオブジェクトが読み取り専用なので、書き込み可にしてから消す."""

    def make_writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)
    else:
        shutil.rmtree(path, onerror=make_writable)
