import asyncio
import logging

import config
import sonarr
import utils

cfg = config.init()

############################################################
# Tracker Configuration
############################################################
name = "IPTorrents"
irc_host = "irc.iptorrents.com"
irc_port = 6667
irc_channel = "#ipt.announce"
irc_tls = False
irc_tls_verify = False

# these are loaded by init
auth_key = None
torrent_pass = None

logger = logging.getLogger(name.upper())
logger.setLevel(logging.DEBUG)


############################################################
# Tracker Framework (all trackers must follow)
############################################################
# Parse announcement message
@asyncio.coroutine
def parse(announcement):
    if 'TV/' not in announcement:
        return
    decolored = utils.strip_irc_color_codes(announcement)
    logger.debug("Parsing: %s", decolored)

    # extract required information from announcement
    torrent_title = utils.substr(decolored, '] ', ' -', True)
    torrent_id = utils.get_id(decolored, 0)

    # pass announcement to sonarr
    if torrent_id is not None and torrent_title is not None:
        download_link = "http://{}:{}/{}/{}/{}".format(cfg['server.host'], cfg['server.port'],
                                                       name.lower(), torrent_id,
                                                       utils.replace_spaces(torrent_title, '.'))

        approved = yield from sonarr.wanted(torrent_title, download_link, name)
        if approved:
            logger.debug("Sonarr approved release: %s", torrent_title)
        else:
            logger.debug("Sonarr rejected release: %s", torrent_title)


@asyncio.coroutine
def get_torrent_link(torrent_id, torrent_name):
    torrent_link = "https://iptorrents.com/download.php/{}/{}.torrent?torrent_pass={}".format(torrent_id,
                                                                                              torrent_name,
                                                                                              torrent_pass)
    return torrent_link


# Initialize tracker
@asyncio.coroutine
def init():
    global auth_key, torrent_pass

    auth_key = cfg["{}.auth_key".format(name.lower())]
    torrent_pass = cfg["{}.torrent_pass".format(name.lower())]

    # check torrent_pass was supplied
    if not torrent_pass:
        return False

    return True
