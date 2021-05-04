import discord
from discord.ext import commands

from pathlib import Path


class MusicBot(commands.Bot):
    def __init__(self):
        self._cogs = [p.stem for p in Path("").glob("./cogs/*.py")]
        print(self._cogs)

        super().__init__(command_prefix=self.prefix, case_insensitive=True, intents=discord.Intents.all())

    def setup(self):
        print("Running Setup")

        for cog in self._cogs:
            self.load_extension(f'cogs.{cog}')
            print(f"Loaded '{cog}' cog.")

        print("Setup Complete")

    def run(self):
        self.setup()

        with open("./token.0", "r", encoding="utf-8") as f:
            TOKEN = f.read()

        print("Running bot...")
        super().run(TOKEN, reconnect=True)

    async def on_connect(self):
        print(f"Connected to Discord (latency: {self.latency * 1000}ms )")

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
        for cog in [p.stem for p in Path("").glob("./cogs/*.py")]:
            try:
                client.unload_extension(f'cogs.{cog}')
                client.load_extension(f'cogs.{cog}')
            except Exception as e:
                client.load_extension(f'cogs.{cog}')
        await ctx.send("Reloaded")

    client.run()
