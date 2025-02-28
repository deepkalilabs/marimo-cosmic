# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
import pathlib
import signal
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, List, Optional

from marimo import _loggers
from marimo._config.config import WidthType
from marimo._runtime.requests import SerializedQueryParams
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.files.os_file_system import natural_sort_file
from marimo._server.models.files import FileInfo
from marimo._server.models.home import MarimoFile
from marimo._types.ids import SessionId
from marimo._utils.marimo_path import MarimoPath
from helpers.backend.supabase import client
from helpers.backend.aws.s3 import s3
import tempfile
import subprocess

if TYPE_CHECKING:
    from types import FrameType

LOGGER = _loggers.marimo_logger()

# Some unique identifier for a file
MarimoFileKey = str

class FileImportError(Exception):
    pass

class AppFileRouter(abc.ABC):
    """
    Abstract class for routing files to an AppFileManager.
    """

    NEW_FILE: MarimoFileKey = "__new__"

    @property
    def directory(self) -> str | None:
        return None

    @staticmethod
    def infer(path: str) -> AppFileRouter:
        if os.path.isfile(path):
            LOGGER.debug("Routing to file %s", path)
            return AppFileRouter.from_filename(MarimoPath(path))
        if os.path.isdir(path):
            LOGGER.debug("Routing to directory %s", path)
            return AppFileRouter.from_directory(path)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Path {0} is not a valid file or directory".format(path),
        )

    @staticmethod
    def from_filename(file: MarimoPath) -> AppFileRouter:
        files = [
            MarimoFile(
                name=file.relative_name,
                path=file.absolute_name,
                last_modified=file.last_modified,
            )
        ]
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def from_directory(directory: str) -> AppFileRouter:
        return LazyListOfFilesAppFileRouter(directory, include_markdown=False)

    @staticmethod
    def from_files(files: List[MarimoFile]) -> AppFileRouter:
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def new_file() -> AppFileRouter:
        return NewFileAppFileRouter()

    def get_single_app_file_manager(
        self, default_width: WidthType | None = None
    ) -> AppFileManager:
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.get_file_manager(key, default_width)
    
    def fix_import_file_name(self, name: str) -> str:
        if " " in name:
            name = name.replace(" ", "_")
        if "." in name:
            name = name.split(".")[0]
        return (name + ".py", name + ".ipynb")
    
    def import_notebook_from_s3(self, query_params: SerializedQueryParams) -> str:
        marimo_name, notebook_name = self.fix_import_file_name(query_params.get('file'))
        notebook_id = query_params.get('notebook_id')
        user_id = query_params.get('user_id')

        s3_file_url = s3.get_notebook_file_path(notebook_id, user_id, notebook_name)        
        s3_response = s3.load_notebook(s3_file_url)

        notebook_contents, status_code, message = s3_response['response'], s3_response['statusCode'], s3_response['message']

        if status_code != 200:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Fetching notebook {notebook_name} from s3 failed with message {message}",
            )

        temp_file = tempfile.NamedTemporaryFile(suffix='.ipynb', delete=False)
        with open(temp_file.name, 'w') as f:
            f.write(notebook_contents)
        
        subprocess.run(['marimo', 'convert', temp_file.name, '-o', marimo_name])

        return marimo_name
    
    def import_template_from_s3(self, filename: str, query_params: SerializedQueryParams) -> str:
        template_id = query_params.get('template_id')

        supabase_client = client.get_supabase_client()
        template_uri = supabase_client.table('templates').select('s3_file_uri').eq('id', template_id).execute().data[0]['s3_file_uri']
        s3_response = s3.load_notebook(template_uri)

        notebook_contents, status_code, message = s3_response['response'], s3_response['statusCode'], s3_response['message']

        if status_code != 200:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Fetching notebook {filename} from s3 failed with message {message}",
            )
        
        with open(filename, 'w') as f:
            f.write(notebook_contents)
        
        return filename
        
    def get_file_manager(
        self,
        key: MarimoFileKey,
        query_params: SerializedQueryParams,
        default_width: WidthType | None = None,
    ) -> AppFileManager:
        """
        Given a key, return an AppFileManager.
        """
        if key.startswith(AppFileRouter.NEW_FILE):
            return AppFileManager(None, default_width)
        
        LOGGER.info("query_params: %s", query_params)

        if not os.path.exists(key) and query_params.get('notebook_id') is not None:
            if query_params.get('imported') == 'true':
                try:
                    filename = self.import_notebook_from_s3(query_params)
                    return AppFileManager(filename, default_width)
                except FileImportError as e:
                    LOGGER.warn("Error creating local notebook from s3: %s", e)
                    return AppFileManager(key, default_width)
                except Exception as e:
                    if os.path.exists(key):
                        os.remove(key)
                    LOGGER.warn("Error creating local notebook from s3: %s", e)
                    raise e
            elif query_params.get('template_id') is not None:
                try:
                    filename = self.import_template_from_s3(key, query_params)
                    return AppFileManager(filename, default_width)
                except Exception as e:
                    if os.path.exists(key):
                        os.remove(key)
                    LOGGER.warn("Error creating local notebook from s3: %s", e)
                    raise e
            else:
                f = open(key, "w")
                f.close()
                return AppFileManager(key, default_width)

        if os.path.exists(key):
            return AppFileManager(key, default_width)

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="File {0} not found".format(key),
        )

    @abc.abstractmethod
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        """
        If there is a unique file key, return it. Otherwise, return None.
        """
        pass

    @abc.abstractmethod
    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        """
        If there is a single file, return it. Otherwise, return None.
        """
        pass

    @property
    @abc.abstractmethod
    def files(self) -> List[FileInfo]:
        """
        Get all files in a recursive tree.
        """
        pass


class NewFileAppFileRouter(AppFileRouter):
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        return AppFileRouter.NEW_FILE

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        return None

    @property
    def files(self) -> List[FileInfo]:
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, files: List[MarimoFile]) -> None:
        self._files = files

    @property
    def files(self) -> List[FileInfo]:
        return [
            FileInfo(
                id=file.path,
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
                is_directory=False,
                is_marimo_file=True,
            )
            for file in self._files
        ]

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        if len(self.files) == 1:
            return self.files[0].path
        return None

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        if len(self.files) == 1:
            file = self.files[0]
            return MarimoFile(
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
            )
        return None


class LazyListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, directory: str, include_markdown: bool) -> None:
        # pass through Path to canonicalize, strips trailing slashes
        self._directory = str(pathlib.Path(directory))
        self.include_markdown = include_markdown
        self._lazy_files: Optional[List[FileInfo]] = None

    @property
    def directory(self) -> str:
        return self._directory

    def toggle_markdown(
        self, include_markdown: bool
    ) -> LazyListOfFilesAppFileRouter:
        # Only create a new instance if the include_markdown flag is different
        if include_markdown != self.include_markdown:
            return LazyListOfFilesAppFileRouter(
                self.directory, include_markdown
            )
        return self

    def mark_stale(self) -> None:
        self._lazy_files = None

    @property
    def files(self) -> List[FileInfo]:
        if self._lazy_files is None:
            self._lazy_files = self._load_files()
        return self._lazy_files

    def _load_files(self) -> List[FileInfo]:
        import time

        start_time = time.time()
        MAX_EXECUTION_TIME = 5  # 5 seconds timeout

        def recurse(
            directory: str, depth: int = 0
        ) -> Optional[List[FileInfo]]:
            if depth > MAX_DEPTH:
                return None

            if time.time() - start_time > MAX_EXECUTION_TIME:
                raise HTTPException(
                    status_code=HTTPStatus.REQUEST_TIMEOUT,
                    detail="Request timed out: Loading workspace files took too long.",  # noqa: E501
                )

            try:
                entries = os.scandir(directory)
            except OSError as e:
                LOGGER.debug("OSError scanning directory: %s", str(e))
                return None

            files: List[FileInfo] = []
            folders: List[FileInfo] = []

            for entry in entries:
                # Skip hidden files and directories
                if entry.name.startswith("."):
                    continue

                if entry.is_dir():
                    if entry.name in skip_dirs or depth == MAX_DEPTH:
                        continue
                    children = recurse(entry.path, depth + 1)
                    if children:
                        folders.append(
                            FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=True,
                                is_marimo_file=False,
                                children=children,
                            )
                        )
                elif entry.name.endswith(tuple(allowed_extensions)):
                    if self._is_marimo_app(entry.path):
                        files.append(
                            FileInfo(
                                id=entry.path,
                                path=entry.path,
                                name=entry.name,
                                is_directory=False,
                                is_marimo_file=True,
                                last_modified=entry.stat().st_mtime,
                            )
                        )

            # Sort folders then files, based on natural sort (alpha, then num)
            return sorted(folders, key=natural_sort_file) + sorted(
                files, key=natural_sort_file
            )

        MAX_DEPTH = 5
        skip_dirs = {
            "venv",
            "__pycache__",
            "node_modules",
            "site-packages",
            "eggs",
        }
        allowed_extensions = (
            (".py", ".md") if self.include_markdown else (".py",)
        )

        return recurse(self.directory) or []

    def _is_marimo_app(self, full_path: str) -> bool:
        try:
            path = MarimoPath(full_path)
            contents = path.read_text()
            if path.is_markdown():
                return "marimo-version:" in contents
            if path.is_python():
                return "marimo.App" in contents and "import marimo" in contents
            return False
        except Exception as e:
            LOGGER.debug("Error reading file %s: %s", full_path, e)
            return False

    def get_unique_file_key(self) -> str | None:
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        return None


@contextmanager
def timeout(seconds: int, message: str) -> Generator[None, None, None]:
    def timeout_handler(signum: int, frame: Optional[FrameType]) -> None:
        del signum, frame
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_TIMEOUT,
            detail="Request timed out: {0}".format(message),
        )

    # Set the timeout handler
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)
