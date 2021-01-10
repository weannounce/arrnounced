from asyncio import all_tasks, run_coroutine_threadsafe
import logging
import pydle
import re
import time

import irc_modes
import message_handler

logger = logging.getLogger("IRC")


def get_connected():
    connected = {}
    for client in clients:
        connected[client.tracker.config.type] = client.tracker.status.as_dict()
    return connected


class IRC(irc_modes.ModesFixer):
    RECONNECT_MAX_ATTEMPTS = None

    def __init__(self, tracker, event_loop):
        super().__init__(tracker.config.irc_nickname, eventloop=event_loop)
        self.tracker = tracker

    async def connect(self, *args, **kwargs):
        try:
            await super().connect(*args, **kwargs)
        except OSError as e:
            logger.error("%s: %s", type(e).__name__, e)
            await self.on_disconnect(expected=False)

    # Request channel invite or join channel
    async def attempt_join_channel(self):
        if self.tracker.config.irc_invite_cmd is None:
            for channel in self.tracker.config.user_channels:
                logger.info("Joining %s", channel)
                await self.join(channel)
        else:
            logger.info("%s: Requesting invite", self.tracker.config.short_name)
            await self.message(
                self.tracker.config.irc_inviter, self.tracker.config.irc_invite_cmd
            )

    async def on_disconnect(self, expected):
        self.tracker.status.connected = False
        await super().on_disconnect(expected)

    async def on_kill(self, target, by, reason):
        self.tracker.status.connected = False
        logger.info("KILL: target: %s, by: %s, reason: %s", target, by, reason)
        await super().on_kill(target, by, reason)

    async def on_connect(self):
        logger.info("Connected to: %s", self.tracker.config.irc_server)
        self.tracker.status.connected = True
        await super().on_connect()

        if self.tracker.config.irc_ident_password is None:
            await self.attempt_join_channel()
        else:
            logger.info("Identifying with NICKSERV")
            await self.rawmsg(
                "PRIVMSG",
                "NICKSERV",
                "IDENTIFY",
                self.tracker.config.irc_ident_password,
            )

    async def on_raw(self, message):
        await super().on_raw(message)

        # TODO
        # async def on_raw_221(self, message):
        if message.command == 221 and "+r" in message._raw:
            logger.info("Identified with NICKSERV (221)")
            await self.attempt_join_channel()

    async def on_raw_900(self, message):
        logger.info("Identified with NICKSERV (900)")
        await self.attempt_join_channel()

    async def on_message(self, target, source, message):
        await message_handler.on_message(self.tracker, source, target.lower(), message)

    async def on_invite(self, channel, by):
        logger.info("%s invited us to join %s", by, channel)
        if channel in self.tracker.config.irc_channels:
            await self.join(channel)
        else:
            logger.warning(
                "Skipping join. %s is not in irc_channels list or specified in XML tracker configuration.",
                channel,
            )

    async def on_join(self, channel, user):
        await super().on_join(channel, user)
        if user == self.tracker.config.irc_nickname:
            self.tracker.status.joined(channel)

    async def on_part(self, channel, user, message=None):
        await super().on_part(channel, user, message)
        if user == self.tracker.config.irc_nickname:
            self.tracker.status.parted(channel, message)

    async def on_kick(self, channel, user, by, reason=None):
        await super().on_kick(channel, user, by, reason)
        if user == self.tracker.config.irc_nickname:
            self.tracker.status.kicked(channel, by, reason)

    # Channel full
    async def on_raw_471(self, message):
        channel_rejection = _create_channel_rejection(message._raw)
        if (
            channel_rejection
            and channel_rejection.user == self.tracker.config.irc_nickname
        ):
            self.tracker.status.channel_full(channel_rejection)

    # Invite only
    async def on_raw_473(self, message):
        channel_rejection = _create_channel_rejection(message._raw)
        if (
            channel_rejection
            and channel_rejection.user == self.tracker.config.irc_nickname
        ):
            self.tracker.status.invite_only(channel_rejection)

    # Banned from channel
    async def on_raw_474(self, message):
        channel_rejection = _create_channel_rejection(message._raw)
        if (
            channel_rejection
            and channel_rejection.user == self.tracker.config.irc_nickname
        ):
            self.tracker.status.banned(channel_rejection)

    # Bad channel key
    async def on_raw_475(self, message):
        channel_rejection = _create_channel_rejection(message._raw)
        if (
            channel_rejection
            and channel_rejection.user == self.tracker.config.irc_nickname
        ):
            self.tracker.status.bad_channel_key(channel_rejection)


class ChannelRejection:
    def __init__(self, user, channel, reason):
        self.user = user
        self.channel = channel
        self.reason = reason


# :d7574991db48.example.com 474 bipbopdelayed #delay :Cannot join channel (you're banned)
regex_channel_reject = re.compile(
    r":[^\s]+ \d+ +(?P<user>[^\s]+) (?P<channel>[^\s]+) :(?P<reason>.*)"
)


def _create_channel_rejection(message):
    match = regex_channel_reject.match(message)
    if match:
        return ChannelRejection(
            match.group("user"), match.group("channel"), match.group("reason")
        )
    return None


pool = pydle.ClientPool()
clients = []


def stop():
    logger.info("Stopping IRC client(s)")
    global pool, clients
    for client in clients:
        # pool.disconnect(client)
        run_coroutine_threadsafe(client.disconnect(expected=True), pool.eventloop)

    while len(all_tasks(pool.eventloop)) != 0:
        time.sleep(1)
    pool.eventloop.call_soon_threadsafe(pool.eventloop.stop)

    while pool.eventloop.is_running():
        time.sleep(1)
    pool.eventloop.close()


def run(trackers):
    global pool, clients

    for tracker in trackers.values():
        logger.info(
            "Connecting to server: %s:%d %s",
            tracker.config.irc_server,
            tracker.config.irc_port,
            ", ".join(tracker.config.user_channels),
        )

        client = IRC(tracker, pool.eventloop)

        clients.append(client)
        try:
            pool.connect(
                client,
                hostname=tracker.config.irc_server,
                port=tracker.config.irc_port,
                tls=tracker.config.irc_tls,
                tls_verify=tracker.config.irc_tls_verify,
            )
        except Exception:
            logger.exception("Error while connecting to: %s", tracker.config.irc_server)

    try:
        pool.handle_forever()
    except Exception:
        logger.exception("Exception pool.handle_forever:")
