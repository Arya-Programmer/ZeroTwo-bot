import asyncio
import datetime
import typing
import re

import discord
import wavelink
from discord.ext import commands

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
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

        self._isQueueLooped = loop

    def getNextTrack(self):
        if not self._queue:
            raise QueueIsEmpty

        if not self._isLooped:
            self.position += 1

        if not self._isQueueLoopedn and not self._isLooped:
            history.extend(self._queue)
            self._queue.clear()

        if self.position > len(self._queue)-1 and not self._isLooped:
            if self._isQueueLooped:
                return self.firstTrack
            else:
                history.append(self._queue)
                self._queue.clear()

        return self._queue[self.position]

    @property
    def queue(self):
        return self._queue


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
                    embed.add_field(name="Estimated time until playing", value="N/A jare", inline=True)
                    embed.add_field(name="Position in queue", value=str(len(self.queue.queue)-1), inline=True)
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
                        f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
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

    async def getTracks(self):
        items = [item.title for item in self.queue.queue]
        return items

    async def startPlayback(self):
        await self.play(self.queue.firstTrack)

    async def advance(self):
        try:
            print("Current Queue: ", self.queue.queue, "next Track:", self.queue.getNextTrack())
            if (track := self.queue.getNextTrack()) is not None:
                await self.play(track)

        except QueueIsEmpty:
            pass

    async def queueloop(self, loop):
        try:
            self.queue.loop(loop)

        except QueueIsEmpty:
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
    async def onPlayerStop(self, node, payload):
        await payload.player.advance()

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are N/A in DMs")
            return False
        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        nodes = {
            "MAIN": {
                "host": "127.0.0.1",
                "port": 2333,
                "rest_uri": "http://127.0.0.1:2333",
                "password": "youshallnotpass",
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
            await ctx.send(f":thumbsup:`Already` connected to `{ctx.channel.id}`")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No suitable voice channel")

    @commands.command(name="reverseJutsu", aliases=['unsummon', 'leave', 'disconnect'])
    async def disconnect(self, ctx, *, channel: typing.Optional[discord.VoiceChannel]):
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
            await player.addTracks(ctx, await self.wavelink.get_tracks(query), False)

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

    @commands.command(name="queue", aliases=['q'])
    async def queue(self, ctx):
        player = self.get_player(ctx)
        tracks = await player.getTracks()
        embed = discord.Embed(
            title=":negative_squared_cross_mark: **Invalid usage**",
            description=f"{ctx.prefix}play [Link or Query]",
            color=discord.Colour(0xFFB6C1),
        )
        await ctx.send(embed=embed)

    @commands.command(name="skip", aliases=['s', 'next', 'fs'])
    async def skip(self, ctx):
        player = self.get_player(ctx)
        player.queue.position -= 1
        await player.stop()

    @commands.command(name="previous", aliases=['prev'])
    async def previous(self, ctx):
        player = self.get_player(ctx)
        player.queue.position -= 2
        await player.stop()

    @commands.command(name="queueloop", aliases=['ql'])
    async def queueloop(self, ctx):
        player = self.get_player(ctx)
        player.setLoopQueue(True)

    @commands.command(name="unqueueloop", aliases=['unql'])
    async def unqueueloop(self, ctx):
        player = self.get_player(ctx)
        player.setLoopQueue(False)


def setup(bot):
    bot.add_cog(Music(bot))
