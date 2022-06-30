from .friend import Friend

__red_end_user_data_statement__ = "Manually added friends are stored by user ID."


async def setup(bot):
    bot.add_cog(Friend(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(Friend(bot))
