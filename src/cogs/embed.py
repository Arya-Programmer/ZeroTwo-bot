import math
from datetime import timedelta, datetime

import discord


def getSongInQueueEmbed(ctx, queue, track):
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
    embed.add_field(name="Position in queue", value=str(len(queue.queue) - 1), inline=True)
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
    return embed


def getQueueEmbed(tracks, totalLength, ctx, currentPage, player):
    nowPlaying = ("__Now Playing:__\n[{}]({})"
                  " | `{}"
                  " Requested by: {}`\n\n__Up Next:__\n".format(player.current.title, player.current.uri,
                                                                timedelta(
                                                                    milliseconds=player.current.duration
                                                                ),
                                                                str(ctx.author))
                  if currentPage < 1 else '')
    tracksTrue = tracks[tracks.index(player.current):]
    tracksTrue.extend(tracks[:tracks.index(player.current)])
    tracks = tracksTrue[1:]
    currentPageTracks = tracks[currentPage * 10:min([(currentPage + 1) * 10, len(tracks)])]

    embed = discord.Embed(
        title=f"**Queue for {ctx.message.guild.name}**",
        url=f"https://movieweb.pythonanywhere.com",
        description=nowPlaying +
                    "\n\n".join(
                        f"`{tracks.index(track) + 1}.` [{track.title}]({track.uri})"
                        f" | `{timedelta(milliseconds=track.duration)}"
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


def getPlaylistsEmbed(ctx, playlists, currentPage):
    thisPagesPlaylists = playlists[currentPage * 10:min([(currentPage + 1) * 10, len(playlists)])]
    embed = discord.Embed(
        title=f"**Playlists for {ctx.author.name}**",
        url=f"https://movieweb.pythonanywhere.com",
        description=f"Playlists:"
                    "\n\n".join(
                        f"`{playlists.index((playlist_name, playlist_items, playlist_length, created_at)) + 1}.` "
                        f"{playlist_name} | **{len(eval(playlist_items))} Songs {playlist_length}** "
                        f"Created at: {str(datetime.strptime(created_at.split('.')[0], '%Y-%m-%d %H:%M:%S'))}"
                        for playlist_name, playlist_items, playlist_length, created_at in thisPagesPlaylists
                    ),
        color=discord.Colour(0xFFB6C1),
    )
    embed.set_footer(text=f'DARLING~~ this page {currentPage + 1}/{math.ceil(len(playlists) / 10)}',
                     icon_url=ctx.author.avatar_url)
    return embed


def getPlaylistItemsEmbed(ctx, playlist_name, playlist_items, totalLength, currentPage):
    thisPagesItems = playlist_items[currentPage * 10:min([(currentPage+1)*10, len(playlist_items)])]
    embed = discord.Embed(
        title=f"**Playlist __{playlist_name}__ {ctx.author.display_name}**",
        url=f"https://movieweb.pythonanywhere.com",
        description="\n\n".join(
            f"`{playlist_items.index(track) + 1}.` {track}"
            for track in thisPagesItems
        ) + f"\n\n**{len(playlist_items)} songs in __{playlist_name}__ {totalLength} **",
        color=discord.Colour(0xFFB6C1),
    )
    embed.set_footer(text=f'DARLING~~ this page {currentPage + 1}/{math.ceil(len(playlist_items) / 10)}',
                     icon_url=ctx.author.avatar_url)
    return embed


def getHistoryEmbed(ctx, history, currentPage):
    thisPagesItems = history[currentPage * 10:min([(currentPage+1)*10, len(history)])]
    embed = discord.Embed(
        title=f"**Commands run by {ctx.author.display_name} in {history[0][2]}**",
        url=f"https://movieweb.pythonanywhere.com",
        description="\n\n".join(
            f"`{history.index(command) + 1}.` {command} | {date}"
            for command, date, _ in thisPagesItems
        ) + f"\n\n**{len(history)} commands run by {str(ctx.author)}**",
        color=discord.Colour(0xFFB6C1),
    )
    embed.set_footer(text=f'DARLING~~ this page {currentPage + 1}/{math.ceil(len(playlist_items) / 10)}',
                     icon_url=ctx.author.avatar_url)
    return embed
