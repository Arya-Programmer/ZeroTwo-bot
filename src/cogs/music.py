import asyncio
import datetime
import math
import sqlite3
import typing
import re
import os.path
from io import BytesIO

import aiohttp
import discord
import wavelink
from discord.ext import commands

from src.cogs.embed import getQueueEmbed
from src.cogs.errors import AlreadyConnectedToChannel, NoNextPage, NoPrevPage, NoVoiceChannel
from src.cogs.player import Player

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "../info.db")

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s(" \
            r")<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])) "

NODES = {
    "MAIN": {
        "host": "192.168.1.60",
        "port": 2334,
        "rest_uri": "http://192.168.1.60:2334",
        "password": "PASSPASS",
        "identifier": "MAIN",
        "region": "europe",
    }
}


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node {node.identifier}")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def onPlayerStop(self, _, payload):
        await payload.player.advance()

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("**Darling~** I can't play song in `here`")
            return False
        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        for node in NODES.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            if not [m for m in before.channel.members if not m.bot]:
                await self.get_player(member.guild).teardown()

    @commands.command(name="summoningnojutsu", aliases=['summon', 'join', 'connect'])
    async def connect(self, ctx, *, channel: typing.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        await ctx.send("**Hey Darling~**, `p@$$w0rd?`")

        def check(m):
            return "aland" in str(m.content).lower()

        try:
            msg = await self.bot.wait_for("message", timeout=10, check=check)
        except asyncio.TimeoutError:
            await ctx.send("**Darling** do you not remember the `password`?:slight_smile:")
        else:
            channel = await player.connect(ctx, channel)
            await ctx.send(f":thumbsup: Joined `{channel.name if channel else 'none'}` from <#{ctx.channel.id}>.")

    @commands.command(name='createemoji', aliases=['createem', 'ce'])
    async def createemoji(self, ctx):
        url = "https://i.imgur.com/CK94WFn.jpg"
        name = "Zerotwo_Cute"
        async with aiohttp.ClientSession() as ses:
            async with ses.get(url) as r:
                try:
                    img_or_gif = BytesIO(await r.read())
                    b_value = img_or_gif.getvalue()
                    if r.status in range(200, 299):
                        emoji = await ctx.guild.create_custom_emoji(image=b_value, name=name)
                        print(f'Successfully created emoji: <:{name}:{emoji.id}>')
                        await ses.close()
                    else:
                        print(f'Error when making request | {r.status} response.')
                        await ses.close()
                except discord.HTTPException:
                    print('File size is too big!')

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

        embed = getQueueEmbed(tracks, totalLength, ctx, currentPage, player)

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
