def notify_observers(tracker_status):
    print("Connected: {}".format(tracker_status.connected))
    for channel, msg in tracker_status.channels.items():
        print("Channel {}: {}".format(channel, msg))


class Tracker:
    def __init__(self, tracker_config):
        self.config = tracker_config
        self.status = TrackerStatus()

    @property
    def name(self):
        return self.config.long_name

    @property
    def type(self):
        return self.config.type


class TrackerStatus:
    def __init__(self):
        self._connected = False
        self._channels = {}
        self._latest_announcement = None

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, connected):
        if connected:
            print("--- CONNECTED")
        else:
            self._channels = {}
            print("--- DISCONNECTED")
        self._connected = connected
        notify_observers(self)

    @property
    def channels(self):
        return self._channels

    def joined_channel(self, channel):
        print("--- JOINED")
        self._channels[channel] = "Joined"
        notify_observers(self)

    def parted_channel(self, channel, message):
        print("--- PARTED")
        self._channels[channel] = "Parted: {}".format(message)
        notify_observers(self)

    def kicked_channel(self, channel, by, reason):
        print("--- KICKED")
        self._channels[channel] = "Kicked by {}, reason: {}".format(by, reason)
        notify_observers(self)


class TrackerConfig:
    def __init__(self, user_tracker, xml_config):
        self._xml_config = xml_config
        self._user_tracker = user_tracker.tracker

        self._always_backends = (
            [b.strip() for b in self._user_tracker.get("notify_backends").split(",")]
            if self._user_tracker.get("notify_backends")
            else []
        )

    def setting(self, key):
        return self._user_tracker["settings"].get(key)

    @property
    def irc_port(self):
        return int(self._user_tracker["irc_port"])

    @property
    def irc_nickname(self):
        return self._user_tracker["irc_nickname"]

    @property
    def irc_server(self):
        return str(self._user_tracker["irc_server"])

    @property
    def irc_tls(self):
        return self._user_tracker["irc_tls"]

    @property
    def irc_tls_verify(self):
        return self._user_tracker["irc_tls_verify"]

    @property
    def irc_ident_password(self):
        return self._user_tracker.get("irc_ident_password")

    @property
    def irc_inviter(self):
        return self._user_tracker.get("irc_inviter")

    @property
    def irc_invite_cmd(self):
        return self._user_tracker.get("irc_invite_cmd")

    @property
    def torrent_https(self):
        return self._user_tracker["torrent_https"]

    @property
    def announce_delay(self):
        return self._user_tracker["announce_delay"]

    @property
    def always_notify_backends(self):
        return self._always_backends

    @property
    def category_notify_backends(self):
        return self._user_tracker["category"]

    @property
    def short_name(self):
        return self._xml_config.tracker_info["shortName"]

    @property
    def long_name(self):
        return self._xml_config.tracker_info["longName"]

    @property
    def type(self):
        return self._xml_config.tracker_info["type"]

    @property
    def user_channels(self):
        return [x.strip() for x in self._user_tracker["irc_channels"].split(",")]

    # Return both channels from XML and user config
    @property
    def irc_channels(self):
        for server in self._xml_config.servers:
            for channel in server.channels:
                yield channel

        for channel in self.user_channels:
            yield channel

    @property
    def announcer_names(self):
        for server in self._xml_config.servers:
            for announcer in server.announcers:
                yield announcer

    @property
    def line_patterns(self):
        return self._xml_config.line_patterns

    @property
    def multiline_patterns(self):
        return self._xml_config.multiline_patterns

    @property
    def ignores(self):
        return self._xml_config.ignores

    @property
    def line_matched(self):
        return self._xml_config.line_matched
