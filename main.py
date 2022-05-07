import os
from pathlib import Path

import tomli

from fastapi import FastAPI
from docker import DockerClient

MC_SERVER_NAME = os.environ.get("MC_SERVER_NAME", "mc-server")

app = FastAPI()
docker = DockerClient(base_url="unix://var/run/docker.sock")

with open(Path("pyproject.toml"), "rb") as pyproject:
    __version__ = tomli.load(pyproject).get("tool.poetry", {}).get("version", "0.0.0")


@app.get("/")
async def root():
    return {"version": __version__}


@app.get("/status/")
async def say_hello(server_name: str):
    return {"status": docker.containers.get(MC_SERVER_NAME).status}
