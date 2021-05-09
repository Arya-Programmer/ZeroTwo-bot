import os
import sqlite3

import discord
from discord.ext import commands

from pathlib import Path

from discord.ext.commands import NoEntryPointError, CommandInvokeError, ExtensionNotLoaded, ExtensionAlreadyLoaded


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "../info.db")
COGS_PATH = os.path.join(BASE_DIR, 'cogs')


class MusicBot(commands.Bot):
    def __init__(self):
        self.conn = sqlite3.connect(DB_DIR)
        self.cursor = self.conn.cursor()
        self._cogs = [p.stem for p in Path("").glob(COGS_PATH+"/*.py")]
        print(self._cogs)

        super().__init__(command_prefix=self.prefix, case_insensitive=True, intents=discord.Intents.all())

    def setup(self):
        print("Running Setup")

        for cog in self._cogs:
            try:
                print(cog)
                self.load_extension(f'cogs.{cog}')
                print(f"Loaded '{cog}' cog.")
            except NoEntryPointError:
                continue

        print("Setup Complete")

    def run(self):
        self.setup()

        print(os.environ.keys())
        TOKEN = os.environ['BOT_TOKEN']

        print("Running bot...")
        super().run(TOKEN, reconnect=True)

    async def on_connect(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS HISTORY(
                     guild           TEXT    NOT NULL,
                     channel_id      INT     NOT NULL,
                     user            TEXT    NOT NULL,
                     command         TEXT    NOT NULL,
                     date          timestamp NOT NULL
                 );''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS SETTINGS(
                     guild           TEXT    NOT NULL,
                     channels        INT     NOT NULL,
                     users           TEXT    NOT NULL,
                     prefix          TEXT    NOT NULL,
                     block_roles     TEXT    NOT NULL,
                     djs             TEXT    NOT NULL
                 );''')

        self.cursor.execute('''CREATE TABLE IF NOT EXISTS PLAYLIST(
                     user            TEXT    NOT NULL,
                     guild           TEXT    NOT NULL,
                     channel_id      INT     NOT NULL,
                     date          timestamp NOT NULL,
                     playlist_name   TEXT    NOT NULL,
                     playlist_items  TEXT    NOT NULL,
                     playlist_length TEXT    NOT NULL
                 );''')
        print(f"Connected to Discord (latency: {self.latency * 1000}ms )")

    async def shutdown(self):
        print("Closing connection to Discord/SQL...")
        self.cursor.close()
        await super().close()

    async def on_ready(self):
        self.client_id = (await self.application_info()).id
        print(self.client_id)

    async def prefix(self, bot, msg):
        return commands.when_mentioned_or("?")(bot, msg)

    async def process_commands(self, msg):
        ctx = await self.get_context(msg, cls=commands.Context)

        if ctx.command is not None:
            await self.invoke(ctx)

    async def on_message(self, msg):
        if not msg.author.bot:
            await self.process_commands(msg)


if __name__ == '__main__':
    client = MusicBot()


    @client.command()
    async def reload(ctx):
        for cog in [p.stem for p in Path("").glob(COGS_PATH+"/*.py")]:
            print(cog)
            print(COGS_PATH)
            print(DB_DIR)
            try:
                client.unload_extension(f'cogs.{cog}')
                client.load_extension(f'cogs.{cog}')
            except (ExtensionAlreadyLoaded, ExtensionNotLoaded):
                try:
                    client.load_extension(f'cogs.{cog}')
                except NoEntryPointError:
                    continue
        await ctx.send("Reloaded")


    client.run()
