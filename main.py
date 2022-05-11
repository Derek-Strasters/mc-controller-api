"""Endpoints to control a Minecraft Bedrock server running in a docker container."""
from __future__ import annotations

import json
import os
import pathlib
from enum import Enum
from typing import List
from uuid import UUID

import docker as docker_package
import tomli
from fastapi import Body, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, conlist

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
            # TODO: make a log
            print(f"Version {__version__}")
    else:
        __version__ = "???"


class Version(BaseModel):
    version: int


@app.get("/", response_model=Version)
async def root():
    """Return the version of the API."""
    ver = Version()
    ver.version = __version__
    return ver


class Behavior_Pack(BaseModel):
    name: str | None
    can_be_redownloaded: bool | None
    uuid: UUID
    version: conlist(int, min_items=3, max_items=3)


class Resource_Pack(BaseModel):
    name: str | None = None
    can_be_redownloaded: bool | None = None
    uuid: UUID
    version: conlist(int, min_items=3, max_items=3)


class Level(BaseModel):
    name: str
    behavior_packs: List[Behavior_Pack] | None
    resource_packs: List[Resource_Pack] | None


@app.get("/levels/", response_model=List[Level], response_model_exclude_unset=True)
def read_levels():
    """Return a list of levels."""
    level_list: List[Level] = list(read_level(level.name) for level in LEVELS_DIR.iterdir())
    return level_list


@app.get("/level/{level_name}", response_model=Level, response_model_exclude_unset=True)
def read_level(level_name: str = None):
    """Return the details of a level."""
    level_dir = LEVELS_DIR / level_name
    if level_dir.is_dir():
        behavior_packs = []
        resource_packs = []
        bp_list_path = level_dir / "world_behavior_packs.json"
        rp_list_path = level_dir / "world_resource_packs.json"
        if bp_list_path.is_file():
            with bp_list_path.open() as bp_file:
                behavior_packs = json.load(bp_file)
        if rp_list_path.is_file():
            with rp_list_path.open() as rp_file:
                resource_packs = json.load(rp_file)

        level: Level = Level(name=level_name, behavior_packs=behavior_packs, resource_packs=resource_packs)

        return level

    raise HTTPException(status_code=404, detail="That level was not fu*king found!")


class Actions(str, Enum):
    start = "start"
    stop = "stop"
    restart = "restart"


class Control(BaseModel):
    action: Actions
    message: str | None = None


@app.post("/control/", response_model=Control)
def create_control(response: Response, control: Control = Body(..., embed=True)):
    """Issue control commands to the Minecraft server."""
    container = docker.containers.get(MC_SERVER_NAME)

    # Get the desired method for the MC server docker container action and execute.
    action = getattr(container, control.action)
    if callable(action):
        action()
        response.status_code = status.HTTP_202_ACCEPTED
        return control
    else:
        control.message = action
        return control


class Statuses(str, Enum):
    running = "running"
    exited = "exited"


class Status(BaseModel):
    status: Statuses


@app.get("/status/", response_model=Status)
def read_status():
    """Return whether the server is running or not."""
    return Status(status=docker.containers.get(MC_SERVER_NAME).status)
