observers = []


def register_observer(observer):
    global observers
    observers.append(observer)


def notify_observers(tracker_status):
    global observers
    for observer in observers:
        observer(tracker_status)


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

    def init_latest(self, latest_announcement, latest_snatch):
        self._latest_announcement = latest_announcement
        self._latest_snatch = latest_snatch

    def as_dict(self):
        return {
            "type": self._type,
            "name": self._name,
            "connected": self._connected,
            "channels": [cs.as_dict() for cs in self.channels.values()],
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
        if not connected:
            self._channels = {}
        self._connected = connected
        notify_observers(self)

    class ChannelStatus:
        def __init__(self, channel):
            self.channel = channel
            self.joined = False
            self.reason = ""

        def as_dict(self):
            return {
                "channel": self.channel,
                "joined": self.joined,
                "reason": self.reason,
            }

        def set_reason(self, static, reason):
            if reason:
                self.reason = "{}: {}".format(static, reason)
            else:
                self.reason = static

    @property
    def channels(self):
        return self._channels

    def channel_full(self, rejection):
        self._channels[rejection.channel] = TrackerStatus.ChannelStatus(
            rejection.channel
        )
        self._channels[rejection.channel].set_reason("Channel full", rejection.reason)
        notify_observers(self)

    def invite_only(self, rejection):
        self._channels[rejection.channel] = TrackerStatus.ChannelStatus(
            rejection.channel
        )
        self._channels[rejection.channel].set_reason("Invite only", rejection.reason)
        notify_observers(self)

    def banned(self, rejection):
        self._channels[rejection.channel] = TrackerStatus.ChannelStatus(
            rejection.channel
        )
        self._channels[rejection.channel].set_reason("Banned", rejection.reason)
        notify_observers(self)

    def bad_channel_key(self, rejection):
        self._channels[rejection.channel] = TrackerStatus.ChannelStatus(
            rejection.channel
        )
        self._channels[rejection.channel].set_reason(
            "Bad channel key", rejection.reason
        )
        notify_observers(self)

    def joined(self, channel):
        self._channels[channel] = TrackerStatus.ChannelStatus(channel)
        self._channels[channel].joined = True
        notify_observers(self)

    def parted(self, channel, message):
        self._channels[channel].joined = False
        self._channels[channel].set_reason("Parted", message)
        notify_observers(self)

    def kicked(self, channel, by, reason):
        self._channels[channel].joined = False
        self._channels[channel].set_reason("Kicked by {}".format(by), reason)
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
