import inspect
import logging
import os
import requests
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import url_for
from flask_login import LoginManager
from flask_login import login_user, logout_user, current_user
from flask_login import login_required
from flask_login import UserMixin
from flask_socketio import SocketIO
from flask_socketio import join_room, leave_room
from pathlib import Path

import log
import web_handler

logger = logging.getLogger("WEB-UI")
table_row_count = 20


class User(UserMixin):
    def get_id(self):
        return 1


# Template directory is the current ([0]) stack object's ([1]) directory + templates
templates_dir = Path(os.path.dirname(os.path.abspath(inspect.stack()[0][1]))).joinpath(
    "templates"
)
app = Flask("Arrnounced", template_folder=templates_dir)
# This will invalidate logins on each restart of Arrnounced
# But I'm too lazy to think of something else at the moment
app.secret_key = os.urandom(16)
socketio = SocketIO(app)

login_manager = LoginManager(app=app)
login_manager.login_view = "login"
user = User()
user_config = None


def run(config):
    global user_config
    user_config = config
    try:
        socketio.run(
            app,
            host=user_config.webui_host,
            port=user_config.webui_port,
            debug=False,
            use_reloader=False,
        )
    except OSError as e:
        logger.error("Error starting webserver: %s", e)


def ack():
    print("msg received")


def update(tracker_status):
    socketio.emit("reply", tracker_status.as_dict(), room="status")


@socketio.on("connect")
def handle_connected():
    if current_user.is_authenticated or not user_config.login_required():
        print("is authed")
    else:
        print("is NOT authed")

    print("connected")


@socketio.on("disconnect")
def handle_disconnected():
    leave_room("status")
    print("disconnected")


@socketio.on("status_event")
def handle_status_event(json):
    print("received json: " + str(json))
    join_room("status")


@app.route("/shutdown", methods=["GET", "POST"])
def shutdown():
    if not user_config.webui_shutdown:
        return redirect(url_for("index"))

    logger.info("Shutting down Arrnounced")
    logger.info("Disable shutdown by removing webui.shutdown from config")
    web_handler.shutdown()
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        raise RuntimeError("Not running with the Werkzeug Server")
    func()
    return "Shutting down..."


@login_manager.user_loader
def load_user(id):
    return user


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST" or not user_config.login_required:
        if user_config.login(
            request.form.get("username"), request.form.get("password")
        ):
            login_user(user)
            return redirect(url_for("index"))
        else:
            error = "Invalid credentials"
    return render_template("login.html", error=error)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/assets/<path:path>")
def send_asset(path):
    return send_from_directory(
        str(templates_dir) + "/assets/{}".format(os.path.dirname(path)),
        os.path.basename(path),
    )


@app.route("/")
@login_required
def index():
    announce_pages, snatch_pages = web_handler.get_page_counts(table_row_count)
    return render_template(
        "index.html",
        announcement_pages=announce_pages,
        snatch_pages=snatch_pages,
        login_required=user_config.login_required,
    )


@app.route("/status")
@login_required
def status():
    return render_template(
        "status.html",
        connected=web_handler.get_status(),
        login_required=user_config.login_required,
    )


@app.route("/logs")
@login_required
def logs():
    logs = []
    for log_line in log.get_logs():
        logs.append({"time": log_line[0], "tag": log_line[1], "msg": log_line[2]})

    return render_template(
        "logs.html", logs=logs, login_required=user_config.login_required
    )


# TODO: Reintroduce check ability
@app.route("/<pvr_name>/check", methods=["POST"])
@login_required
def check(pvr_name):
    try:
        data = request.json
        if "apikey" in data and "url" in data:
            # Check if api key is valid
            logger.debug(
                "Checking whether apikey: %s is valid for: %s",
                data.get("apikey"),
                data.get("url"),
            )

            headers = {"X-Api-Key": data.get("apikey")}
            resp = requests.get(
                url="{}/api/diskspace".format(data.get("url")), headers=headers
            ).json()
            logger.debug("check response: %s", resp)

            if "error" not in resp:
                return "OK"

    # TODO: Catch more specific types
    except Exception:
        logger.exception("Exception while checking " + pvr_name + " apikey:")

    return "ERR"


@app.route("/notify", methods=["POST"])
@login_required
def notify():
    data = request.json
    if "id" in data and "backend_name" in data:
        if web_handler.notify_backend(data["id"], data["backend_name"]):
            return "OK"
    else:
        logger.warning("Missing data in notify request")

    return "ERR"


@app.route("/announced", methods=["POST"])
@login_required
def announced():
    page_nr = 1
    if "page_nr" in request.json:
        page_nr = request.json["page_nr"]

    announced_page, configured_backends = web_handler.get_announced_page(
        page_nr, table_row_count
    )
    announced = jsonify(
        announces=announced_page,
        backends=configured_backends,
    )
    return announced


@app.route("/snatched", methods=["POST"])
@login_required
def snatched():
    page_nr = 1
    if "page_nr" in request.json:
        page_nr = request.json["page_nr"]

    snatched = jsonify(snatches=web_handler.get_snatched_page(page_nr, table_row_count))
    return snatched
