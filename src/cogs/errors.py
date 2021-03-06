from discord.ext import commands


class NoPrevPage(commands.CommandError):
    pass


class NoNextPage(commands.CommandError):
    pass


class AlreadyConnectedToChannel(commands.CommandError):
    pass


class NoVoiceChannel(commands.CommandError):
    pass


class QueueIsEmpty(commands.CommandError):
    pass


class NoTracksFound(commands.CommandError):
    pass


class LackPermissions(commands.CommandError):
    pass


class NoQueryProvided(commands.CommandError):
    pass


class PlayerAlreadyPaused(commands.CommandError):
    pass


class PlaylistNotSupported(commands.CommandError):
    pass
