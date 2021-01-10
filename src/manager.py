import logging
import sys
import threading

import db
import irc
import webui
import tracker
from tracker_xml_config import get_tracker_xml_configs

logger = logging.getLogger("MANAGER")


def _set_latest(tracker):
    latest_announcement, latest_snatch = db.get_latest(tracker.config.short_name)
    tracker.status.init_latest(latest_announcement, latest_snatch)


def _get_trackers(user_config, tracker_config_path):
    xml_configs = get_tracker_xml_configs(tracker_config_path)
    trackers = {}
    for user_tracker in user_config.trackers:
        if user_tracker.type not in xml_configs:
            logger.error(
                "Tracker '%s' from configuration is not supported", user_tracker.type
            )
        elif _are_settings_configured(
            user_tracker, xml_configs[user_tracker.type].settings
        ):
            trackers[user_tracker.type] = tracker.Tracker(
                tracker.TrackerConfig(user_tracker, xml_configs[user_tracker.type])
            )
            _set_latest(trackers[user_tracker.type])
    return trackers


# Check that all setting from the XML tracker config is configured in the user config.
def _are_settings_configured(user_tracker, required_settings):
    configured = True
    for setting in required_settings:
        if setting == "cookie":
            logger.warning(
                "%s: Tracker seems to require cookies to download torrent files. "
                + "Sonarr/Radarr/Lidarr API does not support cookies",
                user_tracker.type,
            )
        elif setting not in user_tracker.settings:
            logger.error("%s: Must specify '%s' in config", user_tracker.type, setting)
            configured = False
    return configured


def run(user_config, tracker_config_path):
    trackers = _get_trackers(user_config, tracker_config_path)
    if len(trackers) == 0:
        logger.error("No trackers configured, exiting...")
        sys.exit(1)

    tracker.register_observer(webui.update)

    irc_thread = threading.Thread(target=irc.run, args=(trackers,))
    webui_thread = threading.Thread(target=webui.run, args=(user_config,))

    webui_thread.start()
    irc_thread.start()

    webui_thread.join()
    irc_thread.join()

    logger.debug("Threads joined")
