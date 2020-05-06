import inspect
import logging
import os
import requests
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import url_for
from flask_login import LoginManager
from flask_login import login_user, logout_user
from flask_login import login_required
from flask_login import UserMixin
from pathlib import Path
from urllib.parse import urlparse

import config
import db
import log
import utils
from backend import renotify, get_configured_backends
from utils import Announcement

logger = logging.getLogger("WEB-UI")


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

login_manager = LoginManager(app=app)
login_manager.login_view = "login"
user = User()


def run():
    try:
        app.run(
            debug=False,
            host=config.webui_host(),
            port=config.webui_port(),
            use_reloader=False,
        )
    except OSError as e:
        logger.error("Error starting webserver: %s", e)


def shutdown_server():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        raise RuntimeError("Not running with the Werkzeug Server")
    func()


@login_manager.user_loader
def load_user(id):
    return user


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST" or not config.login_required():
        if config.login(request.form.get("username"), request.form.get("password")):
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
@db.db_session
def index():
    return render_template(
        "index.html",
        snatched=db.get_snatched(limit=20, page=0),
        announced=db.get_announced(limit=20, page=0),
        backends=get_configured_backends(),
    )


@app.route("/logs")
@login_required
def logs():
    logs = []
    for log_line in log.get_logs():
        logs.append({"time": log_line[0], "tag": log_line[1], "msg": log_line[2]})

    return render_template("logs.html", logs=logs)


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
@db.db_session
def notify():
    try:
        data = request.json
        if "id" in data and "backend_name" in data:
            # Request to check this torrent again
            db_announcement = db.get_announcement(data.get("id"))
            if db_announcement is not None and len(db_announcement.title) > 0:
                logger.debug("Checking announcement again: %s", db_announcement.title)

                backend_name = data.get("backend_name")
                announcement = Announcement(
                    db_announcement.title,
                    db_announcement.torrent,
                    indexer=db_announcement.indexer,
                    date=db_announcement.date,
                )
                approved = renotify(announcement, backend_name,)

                if approved:
                    logger.debug(backend_name + " accepted the torrent this time!")
                    db.insert_snatched(db_announcement, backend_name)
                    return "OK"

                logger.debug(backend_name + " still refused this torrent...")
                return "ERR"

    # TODO: Catch more specific types
    except Exception:
        logger.exception("Exception while notifying announcement:")

    return "ERR"


@app.context_processor
def utility_processor():
    def format_timestamp(timestamp):
        formatted = utils.human_datetime(timestamp)
        return formatted

    def correct_download(link):
        formatted = link
        if "localhost" in link:
            parts = urlparse(request.url)
            if parts.hostname is not None:
                formatted = formatted.replace("localhost", parts.hostname)

        return formatted

    return dict(format_timestamp=format_timestamp, correct_download=correct_download)
