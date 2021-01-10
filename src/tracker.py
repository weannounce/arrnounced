observers = []


def register_observer(observer):
    global observers
    observers.append(observer)


def notify_observers(tracker_status):
    global observers
    for observer in observers:
        observer(tracker_status)
    print("Connected: {}".format(tracker_status.connected))
    for channel, msg in tracker_status.channels.items():
        print("Channel {}: {}".format(channel, msg))


class Tracker:
    def __init__(
        self,
        tracker_config,
    ):
        self.config = tracker_config
        self.status = TrackerStatus(tracker_config)

    @property
    def name(self):
        return self.config.long_name

    @property
    def type(self):
        return self.config.type


def _date2str(date):
    return "Never" if date is None else date.strftime("%Y-%m-%d %H:%M:%S")


class TrackerStatus:
    def __init__(self, config):
        self._type = config.type
        self._name = config.long_name
        self._connected = False
        self._channels = {}
        self._latest_announcement = None
        self._latest_snatch = None

    def as_dict(self):
        return {
            "type": self._type,
            "name": self._name,
            "connected": self._connected,
            "channels": self._channels,
            "latest_announcement": _date2str(self._latest_announcement),
            "latest_snatch": _date2str(self._latest_snatch),
        }

    @property
    def name(self):
        return self._name

    @property
    def connected(self):
        return self._connected

    @property
    def latest_announcement(self):
        return self._latest_announcement

    @latest_announcement.setter
    def latest_announcement(self, announcement):
        self._latest_announcement = announcement.date
        if announcement.snatch_date is not None:
            self._latest_snatch = announcement.snatch_date
        notify_observers(self)

    @property
    def latest_snatch(self):
        return self._latest_snatch

    @latest_snatch.setter
    def latest_snatch(self, announcement):
        self._latest_snatch = announcement.snatch_date
        notify_observers(self)

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

    # TODO
    # 471     ERR_CHANNELISFULL
    #                "<channel> :Cannot join channel (+l)"
    # 472     ERR_UNKNOWNMODE
    #                "<char> :is unknown mode char to me"
    # 473     ERR_INVITEONLYCHAN
    #                "<channel> :Cannot join channel (+i)"
    # 474     ERR_BANNEDFROMCHAN
    #                "<channel> :Cannot join channel (+b)"
    # 475     ERR_BADCHANNELKEY
    #                "<channel> :Cannot join channel (+k)"

    def joined_channel(self, channel):
        print("--- JOINED")
        self._channels[channel] = "Joined"
        notify_observers(self)

    # TODO: Handle None message
    def parted_channel(self, channel, message):
        print("--- PARTED")
        self._channels[channel] = "Parted: {}".format(message)
        notify_observers(self)

    # TODO: Handle None message
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
