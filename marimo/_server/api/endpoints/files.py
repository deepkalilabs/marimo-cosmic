# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    CopyNotebookRequest,
    ReadCodeResponse,
    RenameFileRequest,
    SaveAppConfigurationRequest,
    SaveNotebookRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId
from marimo._server.api.endpoints.packages import _get_package_manager
from typing import List

import sys
sys.path.append(os.path.dirname(os.getcwd()))
from helpers.backend.aws.s3 import s3
from helpers.backend.supabase import notebooks

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post("/read_code")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> ReadCodeResponse:
    """
    responses:
        200:
            description: Read the code from the server
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ReadCodeResponse"
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    session = app_state.require_current_session()

    if not session.app_file_manager.path:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must be saved before downloading",
        )

    contents = session.app_file_manager.read_file()

    return ReadCodeResponse(contents=contents)


@router.post("/rename")
@requires("edit")
async def rename_file(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/RenameFileRequest"
    responses:
        200:
            description: Rename the current app
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    body = await parse_request(request, cls=RenameFileRequest)
    app_state = AppState(request)
    session = app_state.require_current_session()
    prev_path = session.app_file_manager.path

    session.app_file_manager.rename(body.filename)
    new_path = session.app_file_manager.path

    if prev_path and new_path:
        app_state.session_manager.recents.rename(prev_path, new_path)
    elif new_path:
        app_state.session_manager.recents.touch(new_path)

    app_state.require_current_session().put_control_request(
        body.as_execution_request(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    if new_path:
        # Handle rename for watch
        app_state.session_manager.handle_file_rename_for_watch(
            app_state.require_current_session_id(), prev_path, new_path
        )

    notebooks.rename_notebook(
        notebook_id=body.notebook_id, 
        user_id=body.user_id,
        new_path=body.filename,
    )

    return SuccessResponse()


@router.post("/save")
@requires("edit")
async def save(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SaveNotebookRequest"
    responses:
        200:
            description: Save the current app
            content:
                text/plain:
                    schema:
                        type: string
    """
    aws_contents = {}
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveNotebookRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.save(body)

    aws_contents["marimo_notebook.py"] = contents
    aws_contents["requirements.txt"] = _get_dependencies(request)
    aws_contents["python_script.py"] = "\n".join(body.codes) if len(body.codes) > 0 else ""

    response = s3.save_or_update_notebook(
        notebook_id=body.notebook_id, 
        user_id=body.user_id, 
        contents=aws_contents, 
        project_name=body.filename,
    )

    notebooks.save_notebook(
        notebook_id=body.notebook_id, 
        user_id=body.user_id, 
        url=response.get('url'), 
        project_name=body.filename,
    )

    if response.get('status_code') == 200:
        return PlainTextResponse(content=contents)
    else:
        return PlainTextResponse(content=f"Failed to save notebook. Error: {response.get('body')}")

def _get_dependencies(request: Request) -> List[str]:
    # TODO: Exclude base marimo packages from the dependencies
    package_manager = _get_package_manager(request)
    all_packages = package_manager.list_packages()
    return "\n".join([f"{package.name}" for package in all_packages])

@router.post("/copy")
@requires("edit")
async def copy(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/CopyNotebookRequest"
    responses:
        200:
            description: Copy notebook
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=CopyNotebookRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.copy(body)

    return PlainTextResponse(content=contents)


@router.post("/save_app_config")
@requires("edit")
async def save_app_config(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SaveAppConfigurationRequest"
    responses:
        200:
            description: Save the app configuration
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveAppConfigurationRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.save_app_config(body.config)

    return PlainTextResponse(content=contents)
