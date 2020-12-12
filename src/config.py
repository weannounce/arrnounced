import logging
import io
import sys
from tomlkit import parse


mandatory_tracker_fields = ["irc_nickname", "irc_server", "irc_port", "irc_channels"]
logger = logging.getLogger("CONFIG")


class UserConfig:
    def __init__(self, toml):
        self.toml = toml

    def validate_config(self):  # noqa: C901
        valid = True

        if not (
            self.toml["sonarr"].get("apikey") is not None
            or self.toml["radarr"].get("apikey") is not None
            or self.toml["lidarr"].get("apikey") is not None
        ):
            logger.error("Must specify at least one backend (Sonarr/Radarr/Lidarr)")
            valid = False

        if bool(self.toml["webui"].get("username")) != bool(
            self.toml["webui"].get("password")
        ):
            logger.error("webui: Must set none or both 'username' and 'password'")
            valid = False

        for section_name, section in self.toml["trackers"].items():
            for mandatory in mandatory_tracker_fields:
                if not section.get(mandatory):
                    logger.error("%s: Must set '%s'", section_name, mandatory)
                    valid = False

            if bool(section.get("irc_inviter")) != bool(section.get("irc_invite_cmd")):
                logger.error(
                    "%s: Must set both 'irc_inviter' and 'irc_invite_cmd'", section_name
                )
                valid = False

            if (
                section.get("notify_sonarr")
                or section.get("category_sonarr") is not None
            ) and self.toml["sonarr"].get("apikey") is None:
                logger.error(
                    "%s: Must configure sonarr to use 'notify_sonarr' or 'category_sonarr'",
                    section_name,
                )
                valid = False
            if (
                section.get("notify_radarr")
                or section.get("category_radarr") is not None
            ) and self.toml["radarr"].get("apikey") is None:
                logger.error(
                    "%s: Must configure radarr to use 'notify_radarr' or 'category_radarr'",
                    section_name,
                )
                valid = False
            if (
                section.get("notify_lidarr")
                or section.get("category_lidarr") is not None
            ) and self.toml["lidarr"].get("apikey") is None:
                logger.error(
                    "%s: Must configure lidarr to use 'notify_lidarr' or 'category_lidarr'",
                    section_name,
                )
                valid = False

            if (
                section.get("notify_sonarr")
                and section.get("category_sonarr") is not None
            ):
                logger.error(
                    "%s: Cannot use both notify_sonarr and cateogry_sonarr",
                    section_name,
                )
                valid = False
            if (
                section.get("notify_radarr")
                and section.get("category_radarr") is not None
            ):
                logger.error(
                    "%s: Cannot use both notify_radarr and cateogry_radarr",
                    section_name,
                )
                valid = False
            if (
                section.get("notify_lidarr")
                and section.get("category_lidarr") is not None
            ):
                logger.error(
                    "%s: Cannot use both notify_lidarr and cateogry_lidarr",
                    section_name,
                )
                valid = False

        valid = _check_empty_values(self.toml, []) and valid
        return valid

    class UserTracker:
        def __init__(self, tracker_type, user_tracker):
            self.type = tracker_type
            self.tracker = user_tracker

        @property
        def settings(self):
            return self.tracker["settings"]

    @property
    def trackers(self):
        return [
            UserConfig.UserTracker(ttype, t)
            for ttype, t in self.toml["trackers"].items()
        ]

    @property
    def log_to_console(self):
        return self.toml["log"]["to_console"]

    @property
    def log_to_file(self):
        return self.toml["log"]["to_file"]

    @property
    def sonarr_apikey(self):
        return self.toml["sonarr"].get("apikey")

    @property
    def sonarr_url(self):
        return self.toml["sonarr"]["url"]

    @property
    def radarr_apikey(self):
        return self.toml["radarr"].get("apikey")

    @property
    def radarr_url(self):
        return self.toml["radarr"]["url"]

    @property
    def lidarr_apikey(self):
        return self.toml["lidarr"].get("apikey")

    @property
    def lidarr_url(self):
        return self.toml["lidarr"]["url"]

    @property
    def webui_host(self):
        return self.toml["webui"]["host"]

    @property
    def webui_port(self):
        return self.toml["webui"]["port"]

    @property
    def webui_shutdown(self):
        return self.toml["webui"]["shutdown"]

    @property
    def login_required(self):
        return self.toml["webui"].get("username") is not None

    def login(self, username, password):
        if self.toml["webui"].get("username") is None:
            return True
        elif (
            self.toml["webui"].get("username") == username
            and self.toml["webui"].get("password") == password
        ):
            return True
        return False


def _init_value(table, key, value):
    if table.get(key) is None:
        table[key] = value


def toml_notice():
    print(
        "Please note that the configuration format has changed to TOML", file=sys.stderr
    )
    print("Because of this", file=sys.stderr)
    print("* The default config file path has chagned", file=sys.stderr)
    print("* Config file must be updated to conform with TOML", file=sys.stderr)
    print("See the release notes for more info", file=sys.stderr)


def init(config_path):
    toml_cfg = None
    with io.open(config_path) as f:
        try:
            toml_cfg = parse(f.read())
        except Exception as e:
            print("Error {}: {}".format(config_path, e), file=sys.stderr)
            toml_notice()
            return None

    # Settings
    _init_value(toml_cfg, "webui", {})
    _init_value(toml_cfg["webui"], "host", "0.0.0.0")
    _init_value(toml_cfg["webui"], "port", 3467)
    _init_value(toml_cfg["webui"], "shutdown", False)

    _init_value(toml_cfg, "log", {})
    _init_value(toml_cfg["log"], "to_file", True)
    _init_value(toml_cfg["log"], "to_console", True)

    _init_value(toml_cfg, "sonarr", {})
    _init_value(toml_cfg["sonarr"], "url", "http://localhost:8989")

    _init_value(toml_cfg, "radarr", {})
    _init_value(toml_cfg["radarr"], "url", "http://localhost:7878")

    _init_value(toml_cfg, "lidarr", {})
    _init_value(toml_cfg["lidarr"], "url", "http://localhost:8686")

    _init_value(toml_cfg, "trackers", {})
    for tracker_type in toml_cfg["trackers"]:
        # Init optional tracker values
        _init_value(toml_cfg["trackers"][tracker_type], "irc_tls", False)
        _init_value(toml_cfg["trackers"][tracker_type], "irc_tls_verify", False)
        _init_value(toml_cfg["trackers"][tracker_type], "torrent_https", False)
        _init_value(toml_cfg["trackers"][tracker_type], "announce_delay", 0)
        _init_value(toml_cfg["trackers"][tracker_type], "notify_sonarr", False)
        _init_value(toml_cfg["trackers"][tracker_type], "notify_radarr", False)
        _init_value(toml_cfg["trackers"][tracker_type], "notify_lidarr", False)
        _init_value(toml_cfg["trackers"][tracker_type], "settings", {})

    # for k, v in toml_cfg.items():
    #    print(k + ": " + str(v))
    return UserConfig(toml_cfg)


def _check_empty_values(section, prior_sections):
    valid = True
    for key, value in section.items():
        if type(value) is dict:
            valid = _check_empty_values(value, prior_sections + [key]) and valid
        elif len(str(value)) == 0:
            logger.error(
                "%s.%s: Empty value in configuration not allowed. Remove instead.",
                ".".join(prior_sections),
                key,
            )
            valid = False
    return valid
