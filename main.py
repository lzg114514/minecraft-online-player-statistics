import logging
import time
from datetime import datetime
import mcstat
import traceback
from typing import Any, Dict, List
from rich.logging import RichHandler
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from threading import Thread

# Consts
PROJECT_NAME: str = "minecraft-online-player-statistics"
VERSION: str = "0.0.1"
HOST: str = "0.0.0.0"
PORT: int = 1410

# Globals
target_server_host: str = "sc3.i9idc.com"
target_server_port: int = 683
latest_status: Dict[str, Any] = {}
last_update_timestamp: float = 0.0
task_paused: bool = False
task_terminated: bool = False
task_interval: int = 10  # In seconds

# Initialize logger
FORMAT: str = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="%X", handlers=[RichHandler()]
)

log: logging.Logger = logging.getLogger("rich")

# Initialize FastAPI app
app: FastAPI = FastAPI()

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)


class TargetServer(BaseModel):
    host: str
    port: int

class ToggleTask(BaseModel):
    task_paused: bool = Field(..., alias="task-paused")
    task_terminated: bool = Field(..., alias="task-terminated")

class GetStatusDays(BaseModel):
    days: int


def task() -> None:
    global latest_status, last_update_timestamp
    while not task_terminated:
        while not task_paused:
            try:
                latest_status = mcstat.get_info(host=target_server_host, port=target_server_port)
                last_update_timestamp = time.time()
                player_count: int = latest_status.get("players", {"online": -1})["online"]
                formatted_time: str = time.strftime("%Y-%m-%d %H:%M:%S")
                log.info(f"Updated Minecraft status, {player_count} players online")
            except Exception as e:
                log.exception("Error occurred while updating Minecraft status.")
                player_count: int = -1
                formatted_time: str = time.strftime("%Y-%m-%d %H:%M:%S")
            with open("player_stats.txt", "a") as file:
                file.write(f"{formatted_time},{player_count}\n")
            time.sleep(task_interval)

def toTimestamp(str_time: str) -> int:
    date_obj = datetime.strptime(str_time, "%Y-%m-%d %H:%M:%S")
    timestamp = int(date_obj.timestamp())
    return timestamp


@app.get("/api/v1/data/latest-status")
def latest_status_api() -> Response:
    return JSONResponse(content={"success": True, "code": 200, "msg": "200 OK",
                    "data": {"time": last_update_timestamp, "status": latest_status}}, status_code=200)

@app.post("/api/v1/data/status")
def status_api(days: GetStatusDays) -> Response:
    length: int = (60 * 60 * 24 * days.days) // task_interval
    status_data: List[Dict[int, int]] = []

    with open("player_stats.txt", "r") as file:
        content = file.read()
    full_status_data = content.split("\n")
    full_status_data.pop(-1)
    
    count: int = 0
    step: int = length // 720
    for i in full_status_data[::-1][::step]:
        if count <= length:
            status_data.append({toTimestamp(i[0:19]): int(i[20:])})
        else:
            break
    

    return JSONResponse(content={"success": True, "code": 200, "msg": "200 OK",
                    "data": {"length": length//step, "status": status_data[::-1]}}, status_code=200)



@app.get("/api/v1/data/full-status-file")
def full_status_file_api() -> Response:
    headers = {
        "Content-Disposition": 'attachment; filename="player_stats.txt"'
    }
    with open("player_stats.txt", "r") as file:
        content = file.read()
    return Response(content=content, headers=headers, media_type="application/octet-stream")


@app.post("/api/v1/control/set-target-server")
def set_target_server_api(target_server: TargetServer) -> Response:
    global target_server_host, target_server_port
    target_server_host = target_server.host
    target_server_port = target_server.port
    return JSONResponse(content={"success": True, "code": 200, "msg": "200 OK",
                    "data": {"current": {"host": target_server_host, "port": target_server_port}}}, status_code=200)


@app.post("/api/v1/control/toggle-task")
def toggle_task_api(toggle_task: ToggleTask) -> Response:
    global task_paused, task_terminated
    task_paused = toggle_task.task_paused
    task_terminated = toggle_task.task_terminated
    return JSONResponse(content={"success": True, "code": 200, "msg": "200 OK",
                    "data": {"current": {"task-paused": task_paused, "task-terminated": task_terminated}}}, status_code=200)


@app.exception_handler(Exception)
async def handle_exception(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        code: int = exc.status_code
        message: str = exc.detail
        return JSONResponse(content={"success": False, "code": code, "msg": message, "data": None}, status_code=exc.status_code)
    else:
        message: str = "An unexpected error occurred."
        return JSONResponse(
            content={"success": False, "code": 500, "msg": message, "data": {"exception": traceback.format_exc()}}, status_code=500)


if __name__ == '__main__':
    log.info(f"Starting Server: {PROJECT_NAME} Version {VERSION}")
    # Start the task thread
    task_thread = Thread(target=task)
    task_thread.start()

    # Configure Uvicorn logging with RichHandler
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s]     %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "class": "rich.logging.RichHandler",
                "formatter": "default",
                "level": "INFO",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
    
    uvicorn.run(app, host=HOST, port=PORT, log_config=log_config)
