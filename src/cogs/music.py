import asyncio
import datetime
from datetime import timedelta
import math
import typing
import re
from io import BytesIO

import aiohttp
import discord
import wavelink
from discord.ext import commands
from wavelink import Equalizer
import requests

from cogs.decorators import connectToDB
from src.cogs.embed import getQueueEmbed, getPlaylistsEmbed, getPlaylistItemsEmbed, getHistoryEmbed
from src.cogs.errors import AlreadyConnectedToChannel, NoVoiceChannel, \
    NoQueryProvided, PlaylistNotSupported, PlayerAlreadyPaused, QueueIsEmpty
from src.cogs.player import Player

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s(" \
            r")<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’])) "

NODES = {
    "MAIN": {
        "host": "lavalink-zerotwo.herokuapp.com",
        "port": 80,
        "rest_uri": "https://lavalink-zerotwo.herokuapp.com",
        "password": "youshallnotpass",
        "identifier": "MAIN",
        "region": "europe",
    }
}


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.startNodesLoop = self.bot.loop.create_task(self.start_nodes())

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
            await self.bot.wait_for("message", timeout=10, check=check)
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
    async def disconnect(self, ctx):
        player = self.get_player(ctx)
        await player.teardown()
        await ctx.send(":mailbox_with_no_mail: **Successfully disconnected**")

    @disconnect.error
    async def disconnect_error(self, ctx, exc):
        if isinstance(exc, ConnectionResetError):
            self.bot.loop.stop()
            self.bot.loop.reconnect()
            await ctx.send("Reconnected")

    @commands.command(name="stop")
    async def stop(self, ctx):
        player = self.get_player(ctx)
        player.queue.clear()
        await player.stop()

    @stop.error
    async def stop_error(self, ctx, exc):
        pass

    @commands.command(name="pause")
    async def pause(self, ctx):
        player = self.get_player(ctx)
        if player.is_paused:
            raise PlayerAlreadyPaused

        await player.set_pause(True)

    @pause.error
    async def pause_error(self, ctx, exc):
        if isinstance(exc, PlayerAlreadyPaused):
            ctx.send("I've already paused it for you, tho")

    @commands.command(name="play", aliases=['p', 'shoot', 'fuck'])
    async def play(self, ctx, *, query: typing.Optional[str]):
        player = self.get_player(ctx)
        orgQuery = query

        if not player.is_connected and query is not None:
            channel = await player.connect(ctx)
            await ctx.send(f":thumbsup: Joined `{channel.name if channel else 'none'}` from <#{ctx.channel.id}>.")

        if query is None:
            if player.is_paused:
                await player.set_pause(False)
            else:
                raise NoQueryProvided

        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f'ytsearch:{query}'

            await ctx.send(f":youtube: **Searching** :mag_right: `{orgQuery}`")
            await player.addTracks(ctx, await self.wavelink.get_tracks(query, retry_on_failure=True), False)

    @play.error
    async def play_error(self, ctx, exc):
        if isinstance(exc, NoQueryProvided):
            embed = discord.Embed(
                title=":negative_squared_cross_mark: **Invalid usage**",
                description=f"{ctx.prefix}play [Link or Query]",
                color=discord.Colour(0xFFB6C1),
            )
            await ctx.send(embed=embed)
        if isinstance(exc, QueueIsEmpty):
            self.startNodesLoop.close()
            self.startNodesLoop = self.bot.loop.create_task(self.start_nodes())

            print("RELOADED TASKS", locals())

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

        tracks = player.tracks
        currentPage = int(page)
        pagesCount = math.ceil((len(tracks) / 10))
        tempLen = 0
        totalLength = datetime.timedelta(milliseconds=[tempLen := tempLen + t.duration for t in tracks][-1])

        async def _callback(_page, _msg):
            await self.queue(ctx, _page, _msg)

        embed = getQueueEmbed(tracks, totalLength, ctx, currentPage, player)
        await self.pageNavigation(ctx, msg, embed, pagesCount, currentPage, _callback)

    async def pageNavigation(self, ctx, msg, embed, pagesCount, currentPage, func):
        def _check(emojiReac, u):
            return emojiReac.emoji in ["⬅", "➡"] and \
                   u == ctx.author and emojiReac.message.id == msg.id

        if msg:
            await msg.edit(embed=embed)
        else:
            msg = await ctx.send(embed=embed)
        if pagesCount > 1 and msg:
            await msg.add_reaction('⬅')
            await msg.add_reaction('➡')
            try:
                wait_for = self.bot.wait_for("reaction_add", timeout=120, check=_check)
                reaction, _ = await wait_for
            except asyncio.TimeoutError:
                print('TIMED OUT')
                await msg.clear_reactions()
            else:
                if reaction.emoji == "➡" and currentPage + 1 < pagesCount:
                    currentPage += 1
                elif reaction.emoji == "⬅" and currentPage - 1 >= 0:
                    currentPage -= 1
                await func(currentPage, msg)

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
    @connectToDB
    async def savePlaylist(self, ctx, playlistName, cursor=None):
        player = self.get_player(ctx)
        tracks = player.tracks
        tempLen = 0
        totalLength = timedelta(milliseconds=[tempLen := tempLen + t.duration for t in tracks][-1])

        cursor.execute(f"INSERT INTO PLAYLIST VALUES (?,?,?,?,?,?,?)",
                       (str(ctx.author),
                        str(ctx.guild.name),
                        ctx.message.channel.id,
                        datetime.datetime.now(),
                        str(playlistName),
                        str([t.title for t in tracks]),
                        str(totalLength)))

        await ctx.send(
            f":thumbsup: **Darling~** I memorized __{playlistName}__ for you"
            f":upside_down:, I will never **forget** it!:relaxed:")

    async def getPlaylistByName(self, ctx, name, cursor, page=0, msg=None):
        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length"
                                f" FROM PLAYLIST WHERE user = ? AND playlist_name = ?", (str(ctx.author), name))
        playlist_name, playlist_items, totalLength = result.fetchone()
        playlist_items = eval(playlist_items)
        currentPage = page
        pagesCount = math.ceil((len(playlist_items) / 10))

        embed = getPlaylistItemsEmbed(ctx, playlist_name, playlist_items, totalLength, currentPage)

        async def _callback(_page, _msg):
            await self.getPlaylistByName(ctx, name, cursor, _page, _msg)

        await self.pageNavigation(ctx, msg, embed, pagesCount, currentPage, _callback)

    @commands.command(name="myplaylist", aliases=['mypl'])
    @connectToDB
    async def myPlaylist(self, ctx, name=None, page=0, msg=None, cursor=None):
        page = int(page)
        if name:
            await self.getPlaylistByName(ctx, name, cursor)
            return

        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ?", (str(ctx.author),))
        playlists = result.fetchall()
        currentPage = page
        pagesCount = math.ceil((len(playlists) / 10))

        await ctx.send(f"**Darling~** Here is your `playlist`. Told you I'll remember it, did you not **believe me**?")

        embed = getPlaylistsEmbed(ctx, playlists, currentPage)

        async def _callback(_page, _msg):
            await self.myPlaylist(ctx, name, _page, _msg, cursor)

        await self.pageNavigation(ctx, msg, embed, pagesCount, currentPage, _callback)

    @commands.command(name="playplaylist", aliases=['playpl', 'ppl'])
    @connectToDB
    async def playPlaylist(self, ctx, name, cursor=None):
        player = self.get_player(ctx)

        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ? AND playlist_name = ?", (str(ctx.author), name))
        playlist_name, playlist_items, playlist_length, date = result.fetchone()

        await ctx.send("**Darling~**<:zerotwo_smile:841171516913614868> "
                       "I have loaded the playlist, so please be patient.")
        for track in eval(playlist_items):
            if track := f'ytsearch:{track.strip()}':
                search = await self.wavelink.get_tracks(track, retry_on_failure=False)
                if search:
                    if not player.is_connected:
                        await player.connect(ctx)

                    await player.addTracks(ctx, search, False, show_song=False)

    @commands.group(name='equalizer', aliases=['eq'])
    async def setEqualizer(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("You have to tell me, `what to do` **Darling**")

    @setEqualizer.command(name='custom', aliases=['cus', 'c'])
    async def custom(self, ctx, band: int, gain: int, name: str):
        player = self.get_player(ctx)
        await player.set_eq(Equalizer(levels=[(int(band), float(gain))]))
        await ctx.send(f"`Equalizer: {name}` is now set to {str((int(band), float(gain)))}"
                       f", **Darling** Did I do a good job?")

    @setEqualizer.command(name='metal', aliases=['m'])
    async def metal(self, ctx):
        player = self.get_player(ctx)
        await player.set_eq(Equalizer.metal())
        await ctx.send("`Equalizer` is now set to Metal, **Darling** Did I do a good job?")

    @setEqualizer.command(name='piano', aliases=['p'])
    async def piano(self, ctx):
        player = self.get_player(ctx)
        await player.set_eq(Equalizer.piano())
        await ctx.send("`Equalizer` is now set to Piano, **Darling** Did I do a good job?")

    @setEqualizer.command(name='flat', aliases=['f'])
    async def flat(self, ctx):
        player = self.get_player(ctx)
        await player.set_eq(Equalizer.flat())
        await ctx.send("`Equalizer` is now set to Flat, **Darling** Did I do a good job?")

    @setEqualizer.command(name='boost', aliases=['b'])
    async def boost(self, ctx):
        player = self.get_player(ctx)
        await player.set_eq(Equalizer.boost())
        await ctx.send("`Equalizer` is now set to **BOOST**, **Darling** Did I do a good job?")

    @commands.command(name='volume', aliases=['vol', 'v'])
    async def setVolume(self, ctx, amount):
        player = self.get_player(ctx)
        await player.set_volume(int(amount))
        await ctx.send(f"`Volume` is now set to {amount}, **Darling** Are you happy now?")

    @commands.group(name="editPlaylist", aliases=["editpl"])
    async def editPlaylist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("You should tell me what to do with the `playlist`, **Darling~**")

    @editPlaylist.command(name='replace', aliases=['rep'])
    @connectToDB
    async def replace(self, ctx, playlist_name, index, *, replaceWith, cursor=None):
        index = int(index)
        if not index or not playlist_name or not replaceWith:
            return
        if isinstance(replaceWith, wavelink.TrackPlaylist):
            raise PlaylistNotSupported

        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ? AND playlist_name = ?",
                                (str(ctx.author), playlist_name))
        playlist_name, playlist_items, playlist_length, date = result.fetchone()

        playlist_items = eval(playlist_items)
        track = await self.wavelink.get_tracks(replaceWith if re.match(URL_REGEX, str(replaceWith.strip("<>"))) else
                                               f'ytsearch:{replaceWith.strip()}', retry_on_failure=False)
        playlist_items[index - 1] = track[0].title
        await ctx.send(f"**Hey Darling~~**. Alright I replaced {playlist_items[index - 1]} with {track[0].title}")
        cursor.execute(f"UPDATE PLAYLIST SET playlist_items = ? "
                       f"WHERE user = ? AND playlist_name = ?",
                       (str(playlist_items), str(ctx.author), playlist_name))

    @replace.error
    async def replace_error(self, ctx, exc):
        if isinstance(exc, PlaylistNotSupported):
            await ctx.send("**Darlingggg~**, you can't do that. No playlist, alright?")

    @editPlaylist.command(name='add')
    @connectToDB
    async def add(self, ctx, playlist_name, *, addTrack, cursor=None):
        if not playlist_name or not addTrack:
            return

        if isinstance(addTrack, wavelink.TrackPlaylist):
            raise PlaylistNotSupported

        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ? AND playlist_name = ?",
                                (str(ctx.author), playlist_name))
        playlist_name, playlist_items, playlist_length, date = result.fetchone()

        playlist_items = eval(playlist_items)
        track = await self.wavelink.get_tracks(addTrack if re.match(URL_REGEX, str(addTrack.strip("<>"))) else
                                               f'ytsearch:{addTrack.strip()}', retry_on_failure=False)
        playlist_items.append(track[0].title)
        await ctx.send(f"**Hey Darling~~**. Alright I added {track[0].title} "
                       f"there is {len(playlist_items)} Songs, `for you` :heart:")
        cursor.execute(f"UPDATE PLAYLIST SET playlist_items = ? "
                       f"WHERE user = ? AND playlist_name = ?",
                       (str(playlist_items), str(ctx.author), playlist_name))

    @add.error
    async def add_error(self, ctx, exc):
        if isinstance(exc, PlaylistNotSupported):
            await ctx.send("**Darlingggg~**, you can't do that. No playlist, `alright Darling?`")

    @editPlaylist.command(name='delete', aliases=['del'])
    @connectToDB
    async def deleteItem(self, ctx, playlist_name, index, cursor=None):
        if not playlist_name or not index:
            return

        result = cursor.execute(f"SELECT playlist_name, playlist_items, playlist_length, date"
                                f" FROM PLAYLIST WHERE user = ? AND playlist_name = ?",
                                (str(ctx.author), playlist_name))
        playlist_name, playlist_items, playlist_length, date = result.fetchone()

        playlist_items = eval(playlist_items)
        toBeDeleted = playlist_items[index - 1]
        list(playlist_items).remove(toBeDeleted)
        await ctx.send(f"**Hey Darling~~**. Deleted {toBeDeleted} `for you` now:heart:")
        cursor.execute(f"UPDATE PLAYLIST SET playlist_items = ? "
                       f"WHERE user = ? AND playlist_name = ?",
                       (str(playlist_items), str(ctx.author), playlist_name))

    @commands.command(name="forward")
    async def forward(self, ctx, seconds: int):
        player = self.get_player(ctx)
        if not player.is_playing:
            raise PlayerAlreadyPaused

        await ctx.send(f"<:zerotwo_smile:841171516913614868>**Darling~~**, "
                       f"I have skipped :fast_forward: **{seconds}Sec**"
                       f" from `{timedelta(milliseconds=int(player.position))}`"
                       f" to `{timedelta(milliseconds=int(player.position + (seconds*1000)))}`")
        await player.seek(position=player.position + (seconds*1000))

    @forward.error
    async def forward_error(self, ctx, exc):
        if isinstance(exc, PlayerAlreadyPaused):
            await ctx.send(f"**Darling**, you can play a song with {ctx.prefix}play <Query or Link>")

    @commands.command(name="seek")
    async def seek(self, ctx, seconds: int):
        seconds = seconds if seconds > 0 else 0
        player = self.get_player(ctx)
        if not player.is_playing:
            raise PlayerAlreadyPaused

        await ctx.send(f"**Darling~~**<:zerotwo_smile:841171516913614868>, I'm now playing from"
                       f" `{timedelta(seconds=seconds)}`")
        await player.seek(position=seconds*1000)

    @seek.error
    async def seek_error(self, ctx, exc):
        if isinstance(exc, PlayerAlreadyPaused):
            await ctx.send(f"but you aren't playing any song, **Darling~~**")

    @commands.command(name="rewind")
    async def rewind(self, ctx, seconds: int):
        player = self.get_player(ctx)
        if not player.is_playing:
            raise PlayerAlreadyPaused

        if (rewindValue := player.position - (seconds*1000)) < player.current.duration:
            await ctx.send(f"**Darling~~**<:zerotwo_smile:841171516913614868>, rewind by"
                           f" `{timedelta(seconds=seconds)}`")
        else:
            await ctx.send(f"**Darling~~**<:zerotwo_smile:841171516913614868>, "
                           f"you rewinded to less than zero so... aah..."
                           f" `{timedelta(seconds=seconds)}`")

        await player.seek(position=rewindValue)

    @seek.error
    async def seek_error(self, ctx, exc):
        if isinstance(exc, PlayerAlreadyPaused):
            await ctx.send(f"but you aren't playing any song, **Darling~~**")

    @commands.command(name="lyric", aliases=['ly'])
    async def getLyric(self, ctx, song_author, *, song_title):

        url = "https://api.lyrics.ovh/v1/{}/{}"
        response = requests.request("GET", url.format(song_author, song_title))

        embed = discord.Embed(title=f"Lyrics for {song_title} by {song_author}", description=response.text)
        await ctx.send(embed=embed)

    @commands.command(name="history", aliases=['hist'])
    @connectToDB
    async def history(self, ctx, currentPage=0, msg=None, cursor=None):
        result = cursor.execute(f"SELECT user, command, date"
                                f" FROM HISTORY WHERE user = ? AND guild = ?",
                                (str(ctx.author), ctx.author.guild.id))
        history = result.fetchall()
        pagesCount = math.ceil((len(history) / 10))

        embed = getHistoryEmbed(ctx, history, currentPage)
        await ctx.send(embed=embed)

        async def _callback(_page, _msg):
            await self.history(ctx, _page, _msg, cursor)

        await self.pageNavigation(ctx, msg, embed, pagesCount, currentPage, _callback)

    @commands.command(name="playNow", alises=['pn'])
    async def playNow(self, ctx, *, query):
        player = self.get_player(ctx)
        orgQuery = query
        if query is None:
            raise NoQueryProvided

        else:
            await player.stop()
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f'ytsearch:{query}'

            await ctx.send(f":youtube: **Searching** :mag_right: `{orgQuery}`")
            await player.playTrackNow(ctx, await self.wavelink.get_tracks(query, retry_on_failure=True))

    @commands.command(name="remove", alises=['r'])
    async def remove(self, ctx, *, query):
        player = self.get_player(ctx)
        tracks = player.tracks
        toRemove = None
        if query is str:
            for track in tracks:
                if query in track.title:
                    toRemove = tracks.index(track)
                    await ctx.send(f"Deleted {track.title} as you wanted, **Darling**")
                    break
            if not toRemove:
                raise NoQueryProvided
        else:
            toRemove = tracks[query+1]

        player.remove(toRemove)


def setup(bot):
    bot.add_cog(Music(bot))
