import asyncio
import datetime
import math
import sqlite3
import typing
import re

import discord
import wavelink
from dateutil.parser import parser
from dateutil.rrule import rrule
from discord.ext import commands
import os.path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "../info.db")

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s(" \
            r")<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])) "
OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}


class AlreadyConnectedToChannel(commands.CommandError):
    pass


class NoVoiceChannel(commands.CommandError):
    pass


class QueueIsEmpty(commands.CommandError):
    pass


class NoTracksFound(commands.CommandError):
    pass


history = []


class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self._isQueueLooped = False
        self._isLooped = False

    def add(self, *args):
        self._queue.extend(args)

    @property
    def firstTrack(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    def loop(self, loop):
        if not self._queue:
            raise QueueIsEmpty

        self._isLooped = loop

    def queueLoop(self, loop):
        if not self._queue:
            raise QueueIsEmpty

        self._isQueueLooped = loop

    def getNextTrack(self):
        if not self._queue:
            raise QueueIsEmpty

        print(self.position)
        print(self._queue, len(self._queue))

        if not self._isLooped:  # if not looped. Otherwise return itself
            self.position += 1
            # if queue not looped then go to next song if there is one
            if not self._isQueueLooped:
                self._queue = self._queue[self.position:]  # remove the songs before this one
                self.position = 0
            # if queue looped but we got to last song then return the first one again
            elif self.position == len(self._queue):
                self.position = 0
                return self.firstTrack

        history.append(self._queue[self.position])
        return self._queue[self.position]

    @property
    def queue(self):
        if not self._queue:
            return QueueIsEmpty
        return self._queue

    @property
    def isLooped(self):
        if not self._queue:
            return QueueIsEmpty
        return self._isLooped

    @property
    def isQueueLooped(self):
        if not self._queue:
            return QueueIsEmpty
        return self._isQueueLooped


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.destroy()
        except KeyError:
            pass

    async def addTracks(self, ctx, tracks, ask):
        if not tracks:
            raise NoTracksFound

        # await ctx.send(tracks)
        # await ctx.send(self.queue._queue)
        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
        elif len(tracks) == 1:
            self.queue.add(tracks[0])
            await ctx.send(f'Added {tracks[0].title} to the queue')
        else:
            if (track := await self.chooseTrack(ctx, tracks, ask)) is not None:
                self.queue.add(track)
                if len(self.queue.queue) <= 1:
                    await ctx.send(f"**Playing** :notes: `{track.title}` - Now!")
                else:
                    embed = discord.Embed(
                        title=f"**{track.title}**",
                        url=f"{track.uri}",
                        description=discord.Embed.Empty,
                        color=discord.Colour(0xFFB6C1),
                    )
                    embed.add_field(name="Channel", value=track.author, inline=True)
                    embed.add_field(name="Song Duration",
                                    value=str(datetime.timedelta(milliseconds=track.duration)),
                                    inline=True)
                    embed.add_field(name="Estimated time until playing", value="N/A Yet", inline=True)
                    embed.add_field(name="Position in queue", value=str(len(self.queue.queue) - 1), inline=True)
                    embed.set_thumbnail(url=track.thumb)
                    embed.set_author(name='Added to queue', icon_url=ctx.author.avatar_url)
                    await ctx.send(embed=embed)

        if not self.is_playing:
            await self.startPlayback()

    async def chooseTrack(self, ctx, tracks, ask):
        def _check(r, u):
            return r.emoji in OPTIONS.keys() and u == ctx.author and r.message.id == msg.id

        if ask:
            embed = discord.Embed(
                title="Choose a song",
                description=(
                    "\n".join(
                        f"**{i + 1}.** {t.title} ({t.length // 60000}:{str(t.length % 60).zfill(2)})"
                        for i, t in enumerate(tracks[:5])
                    )
                ),
                color=ctx.author.color,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_author(name="Query Results")
            embed.set_footer(text=f"Invoked by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

            msg = await ctx.send(embed=embed)
            for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
                await msg.add_reaction(emoji)

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=_check)
            except asyncio.TimeoutError:
                await msg.delete()
                await ctx.message.delete()
            else:
                await msg.delete()
                return tracks[OPTIONS[reaction.emoji]]
        else:
            return tracks[0]

    @property
    def tracks(self):
        return self.queue.queue

    @property
    def isLooped(self):
        return self.queue.isLooped

    @property
    def isQueueLooped(self):
        return self.queue.isQueueLooped

    async def startPlayback(self):
        await self.play(self.queue.firstTrack)

    async def advance(self):
        try:
            print("Current Queue: ", self.queue.queue, "next Track:", track := self.queue.getNextTrack())
            if track is not None:
                await self.play(track)

        except QueueIsEmpty:
            pass

    async def setQueueLoop(self, loop):
        try:
            self.queue.queueLoop(loop)

        except QueueIsEmpty:
            pass

    async def setLoop(self, loop):
        try:
            self.queue.loop(loop)

        except QueueIsEmpty:
            pass


class NoPrevPage(commands.CommandError):
    pass


class NoNextPage(commands.CommandError):
    pass


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            if not [m for m in before.channel.members if not m.bot]:
                await self.get_player(member.guild).teardown()

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node {node.identifier}")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def onPlayerStop(self, _, payload):
        await payload.player.advance()
        try:
            print(payload.reason)
        except AttributeError:
            print(payload)

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are N/A in DMs")
            return False
        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        nodes = {
            "MAIN": {
                "host": "192.168.1.60",
                "port": 2334,
                "rest_uri": "http://192.168.1.60:2334",
                "password": "PASSPASS",
                "identifier": "MAIN",
                "region": "europe",
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    @commands.command(name="summoningnojutsu", aliases=['summon', 'join', 'connect'])
    async def connect(self, ctx, *, channel: typing.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        await ctx.send("wha is da the p@$$w0rd?")

        def check(m):
            return "aland" in str(m.content).lower()

        msg = await self.bot.wait_for("message", check=check)
        if msg:
            channel = await player.connect(ctx, channel)
            await ctx.send(f":thumbsup: Joined `{channel.name if channel else 'none'}` from <#{ctx.channel.id}>.")
        else:
            await ctx.send("Ey yo, fam you don't seem to know the p@$$w0rd")

    @connect.error
    async def connect_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send(
                f":thumbsup: **Darling~** didn't I already connect to a voice channel from `<#{ctx.channel.id}>`")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel")

    @commands.command(name="reverseJutsu", aliases=['unsummon', 'leave', 'disconnect'])
    async def disconnect(self, ctx, *_):
        player = self.get_player(ctx)
        await player.teardown()
        await ctx.send(":mailbox_with_no_mail: **Successfully disconnected**")

    @commands.command(name="play", aliases=['p', 'shoot', 'fuck'])
    async def play(self, ctx, *, query: typing.Optional[str]):
        player = self.get_player(ctx)
        orgQuery = query

        if not player.is_connected and query is not None:
            channel = await player.connect(ctx)
            await ctx.send(f":thumbsup: Joined `{channel.name if channel else 'none'}` from <#{ctx.channel.id}>.")

        if query is None:
            embed = discord.Embed(
                title=":negative_squared_cross_mark: **Invalid usage**",
                description=f"{ctx.prefix}play [Link or Query]",
                color=discord.Colour(0xFFB6C1),
            )
            await ctx.send(embed=embed)
            return
        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f'ytsearch:{query}'

            await ctx.send(f":youtube: **Searching** :mag_right: `{orgQuery}`")
            await player.addTracks(ctx, await self.wavelink.get_tracks(query, retry_on_failure=True), False)

    @commands.command(name="rythmplaylist", aliases=['rpl', 'rplaylist'])
    async def playlist(self, ctx, *, query: typing.Optional[str]):
        player = self.get_player(ctx)

        playlist = query.split("\n")
        for track in playlist:
            track = track.split('|')[0]
            if '.' in track:
                track = track.split('.')[1]
            if (track := f'ytsearch:{track.strip()}') and 'Up Next:' not in track and 'Now Playing:' not in track:
                search = await self.wavelink.get_tracks(track, retry_on_failure=False)
                if search:
                    if not player.is_connected:
                        await player.connect(ctx)

                    await player.addTracks(ctx, search, False)

    def getQueueEmbed(self, tracks, totalLength, ctx, currentPage, player):
        nowPlaying = ("__Now Playing:__\n[{}]({})"
                      " | `{}"
                      " Requested by: {}`\n\n__Up Next:__\n".format(player.current.title, player.current.uri,
                                                                    datetime.timedelta(
                                                                        milliseconds=player.current.duration
                                                                    ),
                                                                    str(ctx.author))
                      if currentPage < 1 else '')
        currentPageTracks = tracks[currentPage * 10:min([(currentPage+1)*10, len(tracks)])]

        embed = discord.Embed(
            title=f"**Queue for {ctx.message.guild.name}**",
            url=f"https://movieweb.pythonanywhere.com",
            description=nowPlaying +
                        "\n\n".join(
                            f"`{tracks.index(track) + 1}.` [{track.title}]({track.uri})"
                            f" | `{datetime.timedelta(milliseconds=track.duration)}"
                            f" Requested by: {str(ctx.author)}`"
                            for track in currentPageTracks
                        ) + f"\n\n**{len(tracks)} songs in queue | {totalLength} total length**",
            color=discord.Colour(0xFFB6C1),
        )
        embed.set_footer(text=f'Page {currentPage + 1}/{math.ceil((len(tracks) / 10))}'
                              ' | Loop: ' +
                              ("✅" if player.isLooped
                               else "❎") +
                              ' | Queue Loop: ' +
                              ("✅" if player.isQueueLooped
                               else "❎"),
                         icon_url=ctx.author.avatar_url)
        return embed

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx, page: int = 0, msg=None):
        player = self.get_player(ctx)

        def _check(emojiReac, u):
            return emojiReac.emoji in ["⬅", "➡"] and \
                   u == ctx.author and emojiReac.message.id == msg.id

        tracks = player.tracks
        currentPage = int(page)
        pagesCount = math.ceil((len(tracks) / 10))
        tempLen = 0
        totalLength = datetime.timedelta(milliseconds=[tempLen := tempLen + t.duration for t in tracks][-1])
        tracks = tracks[1:]

        embed = self.getQueueEmbed(tracks, totalLength, ctx, currentPage, player)

        found = False
        if msg:
            await msg.edit(embed=embed)
            found = True
        else:
            msg = await ctx.send(embed=embed)
            found = True
        if pagesCount > 1 and msg:
            await msg.add_reaction('⬅')
            await msg.add_reaction('➡')

        if found:
            try:
                waitfor = self.bot.wait_for("reaction_add", timeout=120, check=_check)
                reaction, _ = await waitfor
                print(reaction, _)
            except asyncio.TimeoutError:
                print(str(TimeoutError))
                await msg.clear_reactions()
                await msg.clear_reaction("➡")
                await msg.clear_reaction("⬅")
            else:
                try:
                    waitfor.close()
                    if reaction.emoji == "➡":
                        if currentPage + 1 < pagesCount:
                            currentPage += 1
                            await self.queue(ctx, currentPage, msg)
                        else:
                            raise NoNextPage
                    elif reaction.emoji == "⬅":
                        if currentPage - 1 >= 0:
                            currentPage -= 1
                            await self.queue(ctx, currentPage, msg)
                        else:
                            raise NoPrevPage
                except NameError:
                    pass

    async def pageChange(self, reaction, msg, currentPage, pagesCount, **kwargs):
        if reaction.emoji == "➡":
            if not currentPage + 1 > pagesCount:
                currentPage += 1
            else:
                raise NoPrevPage
        elif reaction.emoji == "⬅":
            if currentPage - 1 < 0:
                currentPage -= 1
            else:
                raise NoNextPage

        embed = self.getQueueEmbed(kwargs.tracks, kwargs.totalLength, kwargs.ctx, kwargs.currentPage, kwargs.player)
        await msg.edit(embed=embed)

    @commands.command(name="skip", aliases=['s', 'next', 'fs'])
    async def skip(self, ctx):
        player = self.get_player(ctx)
        await player.stop()
        await ctx.send(":fast_forward: ***Skipped*** :thumbsup:")

    @commands.command(name="previous", aliases=['prev'])
    async def previous(self, ctx):
        player = self.get_player(ctx)
        player.queue.position -= 2
        await player.stop()

    @commands.command(name="queueloop", aliases=['ql'])
    async def queueLoop(self, ctx):
        player = self.get_player(ctx)
        await player.setQueueLoop(True)
        await ctx.send(":repeat: **Queue loop enabled**")

    @commands.command(name="unqueueloop", aliases=['unql'])
    async def unQueueLoop(self, ctx):
        player = self.get_player(ctx)
        await player.setQueueLoop(False)
        await ctx.send(":repeat: **Queue loop disabled**")

    @commands.command(name="loop", aliases=['lp'])
    async def loop(self, ctx):
        player = self.get_player(ctx)
        await player.setLoop(True)

    @commands.command(name="unloop", aliases=['unlp'])
    async def unLoop(self, ctx):
        player = self.get_player(ctx)
        await player.setLoop(False)

    @commands.command(name="saveplaylist", aliases=['savepl'])
    async def savePlaylist(self, ctx, *, playlistName):
        player = self.get_player(ctx)
        tracks = player.tracks
        tempLen = 0
        totalLength = datetime.timedelta(milliseconds=[tempLen := tempLen + t.duration for t in tracks][-1])
        db = sqlite3.connect(DB_DIR)
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO PLAYLIST VALUES (?,?,?,?,?,?,?)",
                       (str(ctx.author),
                        str(ctx.guild.name),
                        ctx.message.channel.id,
                        datetime.datetime.now(),
                        str(playlistName),
                        str([t.title for t in tracks]),
                        str(totalLength)))
        db.commit()
        cursor.close()
        db.close()

        await ctx.send(
            f":thumbsup: **Darling~** I memorized __{playlistName}__ for you"
            f":upside_down:, I will never **forget** it!:relaxed:")

    @commands.command(name="myplaylist", aliases=['mypl'])
    async def myPlaylist(self, ctx, *_):

        def _check(emojiReac, u):
            return emojiReac.emoji in [":arrow_left:", ":arrow_right:"] and \
                   u == ctx.author and emojiReac.message.id == msg.id

        db = sqlite3.connect(DB_DIR)
        cursor = db.cursor()
        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ?", (str(ctx.author),))
        playlists = result.fetchall()
        print(playlists, ctx.author, cursor.execute(f"SELECT * FROM PLAYLIST").fetchall())
        currentPage = 0

        await ctx.send(f"**Darling~** Here is your `playlist`. Told you I'll remember it, did you not **believe me**?")

        embed = discord.Embed(
            title=f"**Playlists for {ctx.author.name}**",
            url=f"https://movieweb.pythonanywhere.com",
            description=f"Playlists:"
                        "\n\n".join(
                f"`{index + 1}.` {playlist_name} | **{len(eval(playlist_items))} Songs {playlist_length}** "
                f"Created at: {str(datetime.datetime.strptime(created_at.split('.')[0], '%Y-%m-%d %H:%M:%S'))}"
                for index, (playlist_name, playlist_items, playlist_length, created_at) in enumerate(playlists)
            ),
            color=discord.Colour(0xFFB6C1),
        )
        embed.set_footer(text=f'DARLING~~ this page {currentPage + 1}/{math.ceil(len(playlists) / 10)}',
                         icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        if math.ceil(len(playlists) / 10) > 1:
            await msg.add_reaction('⬅')
            await msg.add_reaction('➡')

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=_check)
            except asyncio.TimeoutError:
                await msg.remove_reaction('⬅', self.bot)
                await msg.remove_reaction('➡', self.bot)
                await ctx.message.delete()
            else:
                print("HI")
                await msg.delete()

        cursor.close()
        db.close()

    @commands.command(name="playplaylist", aliases=['playpl', 'ppl'])
    async def playPlaylist(self, ctx, *_):
        db = sqlite3.connect(DB_DIR)
        cursor = db.cursor()
        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ?", (str(ctx.author),))
        playlists = result.fetchall()
        print(playlists, ctx.author, cursor.execute(f"SELECT * FROM PLAYLIST").fetchall())
        currentPage = 0

        await ctx.send(f"**Darling~** Here is your `playlist`. Told you I'll remember it, did you not **believe me**?")

        cursor.close()
        db.close()


def setup(bot):
    bot.add_cog(Music(bot))
