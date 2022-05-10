"""Endpoints to control a Minecraft Bedrock server running in a docker container."""
import json
import os
from pathlib import Path

import docker as docker_package
import tomli
import fastapi as fa

MC_SERVER_NAME = os.environ.get("MC_DOCKER_NAME", "mc-server")
DOCKER_BASE_URL = os.environ.get("DOCKER_BASE_URL", "unix://var/run/docker.sock")

app = fa.FastAPI()
docker = docker_package.DockerClient(base_url=DOCKER_BASE_URL)
MC_ROOT = Path("/data")
LEVELS_DIR = MC_ROOT / "worlds"

with open(Path("pyproject.toml"), "rb") as pyproject:
    __version__ = tomli.load(pyproject).get("tool.poetry", {}).get("version", "0.0.0")


@app.get("/")
async def root():
    """Return the version of the API."""
    return {"version": __version__}


@app.get("/status/")
async def status():
    """Return whether the server is running or not."""
    return {"status": docker.containers.get(MC_SERVER_NAME).status}


@app.get("/levels/{level_name}")
async def levels(level_name: str = None):
    """Return a list of levels or details of a level"""
    if level_name is None:
        level_list = list(level.name for level in LEVELS_DIR.iterdir())
        return {"levels": level_list}

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

        return {
            "level": {
                "name": level_name,
                "behavior_packs": behavior_packs,
                "resource_packs": resource_packs,
            }
        }

    raise fa.HTTPException(status_code=404, detail="That level was not fu*king found!")


@app.post("/controller/")
async def controller():
    pass
