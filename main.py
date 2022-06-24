"""Endpoints to control a Minecraft Bedrock server running in a docker container."""
from __future__ import annotations

import json
import os
import pathlib
from enum import Enum
from uuid import UUID

import docker as docker_package
import docker.errors as docker_errors
import tomli
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError, validator

MC_DOCKER_NAME = os.environ.get("MC_DOCKER_NAME", "mc-server")
DOCKER_BASE_URL = os.environ.get("DOCKER_BASE_URL", "unix://var/run/docker.sock")

app = FastAPI()
docker = docker_package.DockerClient(base_url=DOCKER_BASE_URL)
MC_ROOT = pathlib.Path("/data")
LEVELS_DIR = MC_ROOT / "worlds"

__version__ = None


@app.on_event("startup")
def startup_event():
    """Single source the version number from the pyproject.toml file."""
    global __version__
    pyproject_path = pathlib.Path("pyproject.toml")
    try:
        with pyproject_path.open("rb") as pyproject:
            __version__ = tomli.load(pyproject).get("tool", {}).get("poetry", {}).get("version", "???")
            # TODO: # TODO Make a logger, replace print statements
            print(f"Version {__version__}")
    except FileNotFoundError:
        __version__ = "???"


class Version(BaseModel):
    """Model for the level app version."""

    version: int


@app.get(
    "/",
    response_model=Version,
)
async def root():
    """Return the version of the API."""
    ver = Version()
    ver.version = __version__
    return ver


# --- --- --- --- --- --- --- --- --- ---


class MCPack(BaseModel):
    """Parent model for MC behavior and resource packs."""

    name: str | None = None
    subpack: str | None = None
    can_be_redownloaded: bool | None = None
    pack_id: UUID
    version: list[int] = Field(example=[1, 11, 9])

    # noinspection PyMethodParameters
    @validator("version")
    def _check_version_format(cls, ver):
        if len(ver) != 3:
            raise ValidationError("Pack version requires major, minor, and patch versions.")


class BehaviorPack(MCPack):
    """Model for an MC behavior pack."""


class ResourcePack(MCPack):
    """Model for an MC resource pack."""


class Level(BaseModel):
    """Model for an MC level."""

    name: str
    behavior_packs: list[BehaviorPack] | None = None
    resource_packs: list[ResourcePack] | None = None


@app.get(
    "/levels/",
    response_model=list[Level],
    response_model_exclude_unset=True,
)
def read_levels():
    """Return a list of levels currently installed on the server."""
    level_list: list[Level] = list(read_level(level.name) for level in LEVELS_DIR.iterdir())
    return level_list


@app.get(
    "/level/{level_name}",
    response_model=Level,
    response_model_exclude_unset=True,
)
def read_level(level_name: str):
    """Return the details of a level.

    Details include the name of the level and any installed mod packs.
    """
    level_dir = LEVELS_DIR / level_name
    if not level_dir.is_dir():
        raise HTTPException(status_code=404, detail="That level was not flippin found!")

    level: Level = Level(name=level_name)

    try:
        with (level_dir / "world_behavior_packs.json").open() as bp_file:
            level.behavior_packs = json.load(bp_file)
    except FileNotFoundError:
        pass

    try:
        with (level_dir / "world_resource_packs.json").open() as rp_file:
            level.resource_packs = json.load(rp_file)
    except FileNotFoundError:
        pass

    print(level)

    return level


@app.get(
    "/current_level/",
    response_model=Level,
    response_model_exclude_unset=True,
)
def read_current_level():
    """Return the details of the current level.

    Details include the name of the level and any installed mod packs.
    """
    # TODO: # TODO STUB
    pass


@app.put(
    "/current_level/",
    response_model=Level,
    response_model_exclude_unset=True,
)
def update_current_level():
    """Set the current level."""
    # TODO: # TODO STUB
    pass


# --- --- --- --- --- --- --- --- --- ---


class ContainerAction(str, Enum):
    """List of server actions.

    These are allowed attributes and methods of the `docker.models.containers.Container` class.
    """

    start = "start"
    stop = "stop"
    restart = "restart"


class ControlIn(BaseModel):
    """Model for server control request."""

    action: ContainerAction


class ControlOut(BaseModel):
    """Model for server control response."""

    action: ContainerAction
    message: str | None = None


@app.post(
    "/control/",
    response_model=ControlOut,
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
def create_control(control_in: ControlIn) -> ControlOut:
    """Issue control commands to the Minecraft server."""
    try:
        # Get the desired method or attribute for the MC server docker container action and execute.
        container = docker.containers.get(MC_DOCKER_NAME)

        # If action is a method
        match control_in.action:
            case ContainerAction.start:
                container.start()
            case ContainerAction.stop:
                container.stop()
            case ContainerAction.restart:
                container.restart()
            case _:
                raise HTTPException(
                    status_code=500,
                    detail="Whoops! The developer forgot to implement that!",
                )

        return ControlOut(**control_in.dict(), message="success")

    except docker_errors.NotFound:
        raise HTTPException(
            status_code=404,
            detail=f"That container ({MC_DOCKER_NAME}) was not flippin found!",
        )
    except docker_errors.APIError:
        raise HTTPException(status_code=500, detail="There was an error from the Docker API!")


class ContainerStatusValue(str, Enum):
    """List of valid docker container statuses."""

    running = "running"
    exited = "exited"


class ContainerStatus(BaseModel):
    """Response model for docker container status."""

    status: ContainerStatusValue


@app.get(
    "/status/",
    response_model=ContainerStatus,
)
def read_status():
    """Return whether the server is running or not.

    Equivalent to a POST to the control path for status.
    """
    try:
        container = docker.containers.get(MC_DOCKER_NAME)
        container_status = container.status
        try:
            return ContainerStatus(container_status)
        except ValidationError:
            raise HTTPException(
                status_code=500,
                detail=f"Ack! The container returned and invalid status: {container_status}",
            )

    except docker_errors.NotFound:
        raise HTTPException(
            status_code=404,
            detail=f"That container ({MC_DOCKER_NAME}) was not flippin found!",
        )
    except docker_errors.APIError:
        raise HTTPException(status_code=500, detail="There was an error from the Docker API!")
