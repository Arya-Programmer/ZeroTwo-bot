import asyncio

import wavelink

from src.cogs.embed import getSongInQueueEmbed, getSearchOptionEmbed
from src.cogs.errors import AlreadyConnectedToChannel, NoVoiceChannel, NoTracksFound, QueueIsEmpty
from src.cogs.queue import Queue

OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    @property
    def tracks(self):
        return self.queue.queue

    @property
    def isLooped(self):
        return self.queue.isLooped

    @property
    def isQueueLooped(self):
        return self.queue.isQueueLooped

    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        # check if user is in a voice channel | if True: get channel ID
        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        # this is named teardown because disconnect is taken
        try:
            await self.destroy()
        except KeyError:
            pass

    async def addTracks(self, ctx, tracks, ask, show_song=True):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
        else:
            if (track := await self.chooseTrack(ctx, tracks, ask)) is not None:
                self.queue.add(track)
                if len(self.queue.queue) <= 1:
                    await ctx.send(f"**Playing** :notes: `{track.title}` - Now!")
                elif show_song:
                    await ctx.send(embed=getSongInQueueEmbed(ctx, self.queue, track))

        if not self.is_playing:
            await self.startPlayback()

    async def chooseTrack(self, ctx, tracks, ask):
        def _isReactionInOptions(r, u):
            return r.emoji in OPTIONS.keys() and u == ctx.author and r.message.id == msg.id

        if ask:
            msg = await ctx.send(embed=getSearchOptionEmbed(ctx, tracks))
            for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
                await msg.add_reaction(emoji)

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=60, check=_isReactionInOptions)
            except asyncio.TimeoutError:
                await msg.delete()
                await ctx.message.delete()
            else:
                await msg.delete()
                return tracks[OPTIONS[reaction.emoji]]
        else:
            return tracks[0]

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

    async def clear(self):
        self.queue._queue.clear()
