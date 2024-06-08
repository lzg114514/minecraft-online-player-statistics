import logging
import time
import mcstat
import threading
import traceback
import waitress
from typing import Any
from rich.logging import RichHandler
from werkzeug.exceptions import HTTPException
from flask import Response
from flask import Flask, request, jsonify, render_template, send_file

# Consts
PROJECT_NAME: str = "minecraft-online-player-statistics"
VERSION: str = "0.0.1"
HOST: str = "0.0.0.0"
PORT: int = 1410

# Globals
target_server_host: str = "sc3.i9idc.com"
target_server_port: int = 683
latest_status: dict[str, Any] = {}
last_update_timestamp: float = 0.0
task_paused: bool = False
task_terminated: bool = False
task_interval: int = 10  # In seconds

# Initialize logger
FORMAT: str = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

log: logging.Logger = logging.getLogger("rich")

# Initialize flask server app
app: Flask = Flask(__name__)


def task() -> None:
    global latest_status, last_update_timestamp
    while not task_terminated:
        cnt = 1
        while not task_paused:
            try:
                latest_status = mcstat.get_info(host=target_server_host, port=target_server_port)
                last_update_timestamp = time.time()
                player_count: int = latest_status.get("players", {"online": -1}).get("online", -1)
                formatted_time: str = time.strftime("%Y-%m-%d %H:%M:%S")
                log.info(f"[blue]Updated Minecraft status, {player_count} players online",
                         extra={"markup": True})

            except Exception as e:
                logging.exception("Error occurred while updating minecraft status.")
                player_count: int = -1
                formatted_time: str = time.strftime("%Y-%m-%d %H:%M:%S")

            with open("player_stats.txt", "a") as file:
                file.write(f"{formatted_time},{player_count}\n")
            cnt += 1
            time.sleep(task_interval)


@app.route("/api/v1/ping", methods=["GET", "POST"])
def ping_api() -> tuple[Response, int]:
    return jsonify({"success": True, "code": 200, "msg": "200 OK", "data": None}), 200


@app.route("/api/v1/data/latest-status", methods=["GET", "POST"])
def latest_status_api() -> tuple[Response, int]:
    return jsonify({"success": True, "code": 200, "msg": "200 OK",
                    "data": {"time": last_update_timestamp, "status": latest_status}}), 200


@app.route("/api/v1/data/full-status-file", methods=["GET", "POST"])
def full_status_file_api() -> tuple[Response, int]:
    return send_file("player_stats.txt", as_attachment=True), 200


@app.route("/api/v1/control/set-target-server", methods=["POST"])
def set_target_server_api() -> tuple[Response, int]:
    global target_server_host, target_server_port
    data: dict = request.get_json()
    target_server_host = data.get("host", target_server_host)
    target_server_port = data.get("port", target_server_port)
    return jsonify({"success": True, "code": 200, "msg": "200 OK",
                    "data": {"current": {"host": target_server_host, "port": target_server_port}}}), 200


@app.route("/api/v1/control/toggle-task", methods=["POST"])
def toggle_task_api() -> tuple[Response, int]:
    global task_paused, task_terminated, task_interval
    data: dict = request.get_json()
    task_paused = data.get("task-paused", task_paused)
    task_terminated = data.get("task-terminated", task_terminated)
    task_interval = data.get("task-interval", task_interval)
    return jsonify({"success": True, "code": 200, "msg": "200 OK",
                    "data": {"current": {"task-paused": task_paused, "task-terminated": task_terminated,
                                         "task-interval": task_interval}}}), 200


@app.errorhandler(Exception)
def handle_exception(e: Exception) -> tuple[Response, int]:
    if isinstance(e, HTTPException):
        code: int = e.code
        message: str = e.get_description()
        return jsonify({"success": False, "code": code, "msg": message, "data": None}), e.code
    else:
        log.exception("An unexpected error occurred.")
        message: str = "An unexpected error occurred."
        return jsonify(
            {"success": False, "code": 500, "msg": message, "data": {"exception": traceback.format_exc()}}), 500


@app.after_request
def log_each_request(response: Response) -> Response:
    log.info(f"{request.remote_addr} -- {request.method} {request.path} {response.status_code}")
    return response


if __name__ == '__main__':
    log.info(f"Starting Server: {PROJECT_NAME} Version {VERSION}")
    threading.Thread(target=task).start()
    waitress.serve(app, host=HOST, port=PORT)
