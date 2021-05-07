from datetime import timedelta, datetime

import discord


def getSongInQueueEmbed(ctx, track):
    embed = discord.Embed(
        title=f"**{track.title}**",
        url=f"{track.uri}",
        description=discord.Embed.Empty,
        color=discord.Colour(0xFFB6C1),
    )
    embed.add_field(name="Channel", value=track.author, inline=True)
    embed.add_field(name="Song Duration",
                    value=str(timedelta(milliseconds=track.duration)),
                    inline=True)
    embed.add_field(name="Estimated time until playing", value="N/A Yet", inline=True)
    embed.add_field(name="Position in queue", value=str(len(self.queue.queue) - 1), inline=True)
    embed.set_thumbnail(url=track.thumb)
    embed.set_author(name='Added to queue', icon_url=ctx.author.avatar_url)

    return embed


def getSearchOptionEmbed(ctx, tracks):
    embed = discord.Embed(
        title="Choose a song",
        description=(
            "\n".join(
                f"**{i + 1}.** {t.title} ({t.length // 60000}:{str(t.length % 60).zfill(2)})"
                for i, t in enumerate(tracks[:5])
            )
        ),
        color=ctx.author.color,
        timestamp=datetime.utcnow()
    )
    embed.set_author(name="Query Results")
    embed.set_footer(text=f"Invoked by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)


def getQueueEmbed(tracks, totalLength, ctx, currentPage, player):
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
