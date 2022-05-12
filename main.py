"""Endpoints to control a Minecraft Bedrock server running in a docker container."""
from __future__ import annotations

import json
import os
import pathlib
from enum import Enum
from uuid import UUID

import docker as docker_package
import tomli
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, conlist

MC_SERVER_NAME = os.environ.get("MC_DOCKER_NAME", "mc-server")
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
    if pyproject_path.is_file():
        with pyproject_path.open("rb") as pyproject:
            __version__ = tomli.load(pyproject).get("tool", {}).get("poetry", {}).get("version", "???")
            # TODO: # TODO Make a log
            print(f"Version {__version__}")
    else:
        __version__ = "???"


class Version(BaseModel):
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


class BehaviorPack(BaseModel):
    name: str | None = None
    can_be_redownloaded: bool | None = None
    uuid: UUID
    version: conlist(int, min_items=3, max_items=3)  # type: ignore


class ResourcePack(BaseModel):
    name: str | None = None
    can_be_redownloaded: bool | None = None
    uuid: UUID
    version: conlist(int, min_items=3, max_items=3)  # type: ignore


class Level(BaseModel):
    name: str
    behavior_packs: list[BehaviorPack] | None = None
    resource_packs: list[ResourcePack] | None = None


@app.get(
    "/levels/",
    response_model=list[Level],
    response_model_exclude_unset=True,
)
def read_levels():
    """Return a list of levels."""
    level_list: list[Level] = list(read_level(level.name) for level in LEVELS_DIR.iterdir())
    return level_list


@app.get(
    "/level/{level_name}",
    response_model=Level,
    response_model_exclude_unset=True,
)
def read_level(level_name: str):
    """Return the details of a level."""
    level_dir = LEVELS_DIR / level_name
    if level_dir.is_dir():
        level: Level = Level(name=level_name)

        if (level_dir / "world_behavior_packs.json").is_file():
            with (level_dir / "world_behavior_packs.json").open() as bp_file:
                level.behavior_packs = json.load(bp_file)

        if (level_dir / "world_resource_packs.json").is_file():
            with (level_dir / "world_resource_packs.json").open() as rp_file:
                level.resource_packs = json.load(rp_file)

        return level

    raise HTTPException(status_code=404, detail="That level was not fu*king found!")


@app.get(
    "/current_level/",
    response_model=Level,
    response_model_exclude_unset=True,
)
def read_current_level():
    """Return the current level."""
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


class Actions(str, Enum):
    start = "start"
    stop = "stop"
    restart = "restart"
    status = "status"


class ControlOut(BaseModel):
    action: Actions
    message: str | None = None


class ControlIn(BaseModel):
    action: Actions


class Statuses(str, Enum):
    running = "running"
    exited = "exited"


class Status(BaseModel):
    status: Statuses


@app.post(
    "/control/",
    response_model=ControlOut,
    response_model_exclude_unset=True,
    response_model_exclude_none=True,
)
def create_control(control_in: ControlIn = Body(..., embed=True)):
    """Issue control commands to the Minecraft server."""
    container = docker.containers.get(MC_SERVER_NAME)

    # Get the desired method for the MC server docker container action and execute.
    action = getattr(container, control_in.action)
    if callable(action):
        action()
        return control_in
    else:
        return ControlOut(**control_in.dict(), message=action)


@app.get(
    "/status/",
    response_model=Status,
)
def read_status():
    """Return whether the server is running or not."""
    control = ControlIn()
    control.action = Actions.status
    return create_control(control)
