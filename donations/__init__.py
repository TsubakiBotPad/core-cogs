from .donations import Donations

__red_end_user_data_statement__ = "This cog stores your custom commands."


async def setup(bot):
    n = Donations(bot)
    bot.add_cog(n) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(n)
    bot.loop.create_task(n.set_server_attributes())
