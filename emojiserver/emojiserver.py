import logging
import os.path
import zipfile
from collections import defaultdict
from io import BytesIO
from typing import Awaitable, Callable

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.utils.chat_formatting import box, pagify
from tsutils.user_interaction import get_user_confirmation

logger = logging.getLogger('red.misc-cogs.emoji')

EP_STATUS = {
    2: 'admin',
    1: 'user',
    0: 'non-user',
}


def has_status(status) -> Callable[[Context], Awaitable[bool]]:
    """Check if a user is of a status"""

    async def decorator(ctx):
        is_owner = ctx.author.id in ctx.bot.owner_ids
        eps = await ctx.bot.get_cog("EmojiServer").config.emojipeople()
        return is_owner or eps.get(ctx.author.id, 0) >= status

    return decorator


class EmojiServer(commands.Cog):
    """Steal some emoji with this cog."""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=37061532732)
        self.config.register_global(emojiservers=[], emojipeople={})

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.group(aliases=['emojiservers'])
    async def emojiserver(self, ctx):
        """Add or remove emoji servers"""

    @emojiserver.command(name='add')
    @checks.is_owner()
    async def es_add(self, ctx, *server_ids: int):
        """Add an emoji server"""
        async with self.config.emojiservers() as ess:
            for sid in server_ids:
                if self.bot.get_guild(sid) is None:
                    await ctx.send(f"Server '{sid}' not found.")
                elif sid in ess:
                    await ctx.send(f"{s.name} is already an emoji server.")
                else:
                    ess.append(sid)
        await ctx.tick()

    @emojiserver.command(name='remove', aliases=['rm'])
    @checks.is_owner()
    async def es_rm(self, ctx, *server: discord.Guild):
        """Remove an emoji server"""
        async with self.config.emojiservers() as ess:
            for s in server:
                if s.id not in ess:
                    await ctx.send(f"{s.name} is not an emoji server.")
                else:
                    ess.remove(s.id)
        await ctx.tick()

    @emojiserver.command(name='list')
    async def es_list(self, ctx):
        """List all emoji servers"""
        ess = await self.config.emojiservers()
        formatted = '\n'.join(f'{g.id}' for gid in ess
                              if (g := self.bot.get_guild(gid)))
        if not formatted:
            await ctx.send("There are no emoji servers set")
        for page in pagify(formatted):
            await ctx.send(box(page))

    async def emojiperson_set(self, ctx, user: discord.User, status: int) -> None:
        async with self.config.emojipeople() as eps:
            if eps.get(user.id, 0) == status:
                await ctx.send(f"{user.name} is already an emoji {EP_STATUS[status]}.")
                return
            if eps.get(user.id, 0) != 0 and status != 0:
                await ctx.send(f"Changing {user.name} from an emoji {EP_STATUS[eps[user.id]]}"
                               f" to an emoji {EP_STATUS[status]}")
            eps[user.id] = status
        await ctx.tick()

    async def emojiperson_list(self, ctx):
        eps = await self.config.emojipeople()
        admins = [u for u, s in eps.items() if s == 2]
        users = [u for u, s in eps.items() if s == 1]
        formatted = ""
        formatted += "Admins:\n"
        formatted += '\n'.join(f"{u.name} ({u.id})" for uid in admins if (u := self.bot.get_user(uid)))
        formatted += "\n\nUsers:\n"
        formatted += '\n'.join(f"{u.name} ({u.id})" for uid in users if (u := self.bot.get_user(uid)))
        if not formatted:
            await ctx.send("There are no emoji people set")
        for page in pagify(formatted):
            await ctx.send(box(page))

    @emojiserver.group(name='user')
    @checks.is_owner()
    async def emojiuser(self, ctx):
        """Add or remove emoji users"""

    @emojiuser.command(name='add')
    async def es_eu_add(self, ctx, user: discord.User):
        """Add an emoji user"""
        await self.emojiperson_set(ctx, user, 1)

    @emojiuser.command(name='remove', aliases=['rm'])
    async def es_eu_remove(self, ctx, user: discord.User):
        """Remove an emoji user"""
        await self.emojiperson_set(ctx, user, 0)

    @emojiuser.command(name='list')
    async def es_eu_list(self, ctx, user: discord.User):
        """List all emoji users"""
        await self.emojiperson_list(ctx)

    @emojiserver.group(name='admin')
    @checks.is_owner()
    async def emojiadmin(self, ctx):
        """Add or remove emoji users"""

    @emojiadmin.command(name='add')
    async def es_ea_add(self, ctx, user: discord.User):
        """Add an emoji admins"""
        await self.emojiperson_set(ctx, user, 2)

    @emojiadmin.command(name='remove', aliases=['rm'])
    async def es_ea_remove(self, ctx, user: discord.User):
        """Remove an emoji admins"""
        await self.emojiperson_set(ctx, user, 0)

    @emojiadmin.command(name='list')
    async def es_ea_list(self, ctx):
        """List all emoji admins"""
        await self.emojiperson_list(ctx)

    @emojiserver.command()
    @commands.check(has_status(1))
    async def inviteme(self, ctx):
        """Get an invitation to all emoji servers"""
        ess = await self.config.emojiservers()
        invites = []
        for gid in ess:
            guild = self.bot.get_guild(gid)
            invite = discord.utils.find(lambda i: i.max_age == 0,
                                        await guild.invites())
            if invite is None:
                invite = await guild.text_channels[0].create_invite(max_age=0)
            invites.append(invite)
        for page in pagify('\n'.join(i.url for i in invites)):
            await ctx.author.send(page)

    @emojiserver.command()
    @commands.check(has_status(2))
    async def promoteme(self, ctx):
        """Get admin status on this server"""
        ess = await self.config.emojiservers()
        if ctx.guild.id not in ess:
            return await ctx.send("This is not an emoji server.")
        adminrole = discord.utils.find(lambda r: r.name == 'Admin' and r.is_assignable(),
                                       ctx.guild.roles)
        if adminrole is None:
            adminrole = await ctx.guild.create_role(name='Admin', permissions=discord.Permissions(manage_emojis=True))
        await ctx.author.add_roles(adminrole, reason="emojiserver promoteme")
        await ctx.tick()

    @emojiserver.command()
    @commands.check(has_status(2))
    async def zipupload(self, ctx):
        att = ctx.message.attachments
        ess = await self.config.emojiservers()
        if len(att) != 1:
            return await ctx.send("You need to supply exactly one attachment.")
        zf = BytesIO(await att[0].read())
        if not zipfile.is_zipfile(zf):
            return await ctx.send("Attached file must be a zip file")
        async with ctx.typing():
            with zipfile.ZipFile(zf) as z:
                fns = defaultdict(set)
                sid = {}
                for full_name in z.namelist():
                    if full_name.startswith('__MACOSX') or full_name.count('/') != 2:
                        continue
                    _, f, name = full_name.split('/')
                    if name.endswith('.txt'):
                        sid[f] = int(name[:-len('.txt')])
                        continue
                    elif name.endswith('.png'):
                        fns[f].add(full_name)

                problems = []
                for folder in fns:
                    if folder not in sid:
                        problems.append(f"Server ID not found in subfolder `{folder}`")
                    elif (guild := self.bot.get_guild(sid[folder])) is None:
                        problems.append(f"Server with ID {sid} (folder {folder}) not found.")
                    elif guild.id not in ess:
                        problems.append(f"{guild.name} ({guild.id}) is not an emoji server")
                    elif len(guild.emojis) + len(fns[folder]) > guild.emoji_limit:
                        problems.append(f"Not enough emoji spots in server {guild.name} ({guild.id})")
                if problems:
                    for page in pagify("Problems:\n"+'\n'.join(problems)):
                        await ctx.send(box(page))
                    return await ctx.react_quietly("\N{CROSS MARK}")
                for foldername in fns:
                    guild = self.bot.get_guild(sid[foldername])
                    for fp in fns[foldername]:
                        _, _, name = fp.split('/')
                        name = name[:-len('.png')]
                        with z.open(fp) as f:
                            image = f.read()
                        await guild.create_custom_emoji(name=name, image=image, reason="emojiserver zipupload")
        await ctx.tick()

    @emojiserver.command(aliases=['purge'])
    @checks.is_owner()
    async def massdelete(self, ctx: Context, *servers: discord.Guild):
        num_emojis = sum(len(g.emojis) for g in servers)
        message = f"Are you sure you want to delete {num_emojis} emoji from the following servers:\n"
        message += '\n'.join(g.name for g in servers)
        if not await get_user_confirmation(ctx, message):
            return await ctx.react_quietly("\N{CROSS MARK}")
        async with ctx.typing():
            for guild in servers:
                for emoji in guild.emojis:
                    await guild.delete_emoji(emoji)
        await ctx.tick()
