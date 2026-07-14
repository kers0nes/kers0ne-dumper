import os
import io
import asyncio
import tempfile
import subprocess
import re
import random
import string
import hashlib
import json
import base64
import zlib
import time
import pathlib
import threading
import ssl
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
from shutil import move as file_move
from json import loads, dumps

import discord
from discord.ext import commands
from discord import CustomActivity
from discord.ui import Button, View, Select
from discord.utils import escape_mentions
import aiohttp
import requests
from PIL import Image, ImageDraw, ImageColor, ImageFont
from hashlib import sha256

# AI Imports
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

# ============ CONFIG & GLOBALS ============
TOKEN = os.environ.get("DISCORD_TOKEN")
REQUIRED_STATUS = ".gg/25ms"
OWNER_ID = 1123674631266639914
GUILD_ID = 1306714913539887237
DUMP_ROLE_ID = 1373857675497963601
CMDS_CHANNEL_ID = 1348000639753519205

LUNE_BIN = os.environ.get("LUNE_BIN", "lune")
TIMEOUT_SECONDS = 30
NO_MENTIONS = discord.AllowedMentions.none()
URL_PATTERN = re.compile(r'https?://\S+')

# AI Keys
GOOGLE_API_KEY = "AIzaSyBx3Eaf8YN99Cm9Ri8xdI-gOMx3q4SHF54"
GROQ_API_KEY = "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"
ZAI_API_KEY = "4813ab26a5de4441900032a7768a9928.JjIozz6t4L93EJJc"
HF_KEY = "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"

AI_PROVIDER = "google"
OPENAI_COMPATIBLE = {
    "groq": (GROQ_API_KEY, "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openrouter": ("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", "https://openrouter.ai/api/v1", "z-ai/glm-4.5-air:free"),
    "nvidia": ("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", "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct"),
    "mistral": ("B5aucrVRjIvQwFc6qORiacuJen9WnCUD", "https://api.mistral.ai/v1", "mistral-medium-latest"),
}

# State Management
openai_clients = {}
ai_history = []
max_ai_len = 30
whitelisted_users = defaultdict(int)
licenses_data = {}
dump_user_settings = defaultdict(dict)
message_counts = defaultdict(int)

# ============ INITIALIZATION ============

def load_json_data(filename, default_factory=dict):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return defaultdict(int, json.load(f))
    except:
        pass
    return default_factory()

def save_json_data(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(dict(data), f)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

licenses_data = load_json_data("licenses.json")
dump_user_settings = load_json_data("dump_user_settings.json")
message_counts = load_json_data("message_counts.json")

# ============ UTILITIES ============

def randomstr(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def file_sha256(data):
    h = sha256()
    h.update(data if isinstance(data, bytes) else data.encode())
    return h.hexdigest()

def sanitize_output(text: str) -> str:
    ZWSP = '\u200b'
    text = text.replace("@everyone", "@" + ZWSP + "everyone")
    text = text.replace("@here", "@" + ZWSP + "here")
    return text

def has_required_status(user) -> bool:
    if user.id == OWNER_ID: return True
    for activity in user.activities:
        if isinstance(activity, CustomActivity):
            if activity.name and REQUIRED_STATUS in activity.name:
                return True
    return False

def status_required():
    async def predicate(ctx):
        if has_required_status(ctx.author):
            return True
        await ctx.reply(f"❌ You need `{REQUIRED_STATUS}` in your status to use this command!")
        return False
    return commands.check(predicate)

# ============ LICENSING SYSTEM ============

async def refresh_whitelist():
    global whitelisted_users
    whitelisted_users = defaultdict(int)
    for lic, info in licenses_data.items():
        if info.get("claimed"):
            whitelisted_users[info["claimed"]] = True

def is_whitelisted(user_id):
    return whitelisted_users.get(user_id, False)

# ============ BYPASS LOGIC ============

async def byplat(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://iwoozie.baby/api/free/bypass", params={"url": urllib.parse.unquote(url)}, timeout=120) as resp:
                data = await resp.json()
                if data.get("result"):
                    return data["result"]
    except:
        return False
    return False

# ============ AI HANDLER ============

async def chat_ai(messages, provider="google"):
    if provider in OPENAI_COMPATIBLE:
        if provider not in openai_clients:
            key, base, _ = OPENAI_COMPATIBLE[provider]
            openai_clients[provider] = AsyncOpenAI(api_key=key, base_url=base)
        client = openai_clients[provider]
        _, _, model = OPENAI_COMPATIBLE[provider]
        response = await client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content, model
    return "Provider not supported", "none"

# ============ DEOBFUSCATION & DUMPING ============

async def run_unveilr(code: str, user_id: int) -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "input.lua")
            output_path = os.path.join(tmp, "out.lua")
            with open(input_path, "w", encoding="utf-8") as f: 
                f.write(code)
            
            settings = dump_user_settings.get(user_id, {
                "varnames": True, 
                "usesimplefunctions": False, 
                "watchoutforloop": True, 
                "spynilglobals": False, 
                "hook_op": False
            })
            
            params = [
                f"ipt={input_path}", 
                f"out={output_path}", 
                "version=3", 
                f"isPremium={str(is_whitelisted(user_id)).lower()}"
            ]
            for k, v in settings.items():
                params.append(f"{k}={str(v).lower()}")

            lune_script_paths = [
                os.path.join(os.getcwd(), "dropbox_extracted", "main.luau"),
                os.path.join(os.getcwd(), "main.luau"),
                os.path.join(os.path.dirname(__file__), "dropbox_extracted", "main.luau"),
                "main.luau"
            ]
            
            lune_script = None
            for path in lune_script_paths:
                if os.path.exists(path):
                    lune_script = path
                    break
            
            if lune_script and os.path.exists(LUNE_BIN):
                cmd = [LUNE_BIN, "run", lune_script] + params
                proc = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    cwd=tmp
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45)
                
                if os.path.exists(output_path):
                    with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                        return True, f.read()
                else:
                    if stderr:
                        return False, f"Lune error: {stderr.decode()[:200]}"
            else:
                return False, "Lune binary or script not found. Please ensure Lune is installed."
    except asyncio.TimeoutError:
        return False, "Dumping timed out after 45 seconds."
    except Exception as e:
        print(f"UnveilR Error: {e}")
        return False, f"Dumping failed: {str(e)[:100]}"
    
    return False, "Dumping failed."

# ============ BOT SETUP ============

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

# ============ VIEWS ============

class DumpConfigView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.settings = dump_user_settings.get(user_id, {
            "varnames": True, 
            "usesimplefunctions": False, 
            "watchoutforloop": True, 
            "spynilglobals": False, 
            "hook_op": False
        })

    @discord.ui.button(label="Toggle Varnames", style=discord.ButtonStyle.primary)
    async def toggle_varnames(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings["varnames"] = not self.settings["varnames"]
        dump_user_settings[self.user_id] = self.settings
        save_json_data("dump_user_settings.json", dump_user_settings)
        await interaction.response.send_message(f"✅ Varnames: {self.settings['varnames']}", ephemeral=True)

    @discord.ui.button(label="Toggle Simple Functions", style=discord.ButtonStyle.secondary)
    async def toggle_simplefuncs(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings["usesimplefunctions"] = not self.settings["usesimplefunctions"]
        dump_user_settings[self.user_id] = self.settings
        save_json_data("dump_user_settings.json", dump_user_settings)
        await interaction.response.send_message(f"✅ Simple Functions: {self.settings['usesimplefunctions']}", ephemeral=True)

    @discord.ui.button(label="Toggle Watchout For Loop", style=discord.ButtonStyle.success)
    async def toggle_watchout(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings["watchoutforloop"] = not self.settings["watchoutforloop"]
        dump_user_settings[self.user_id] = self.settings
        save_json_data("dump_user_settings.json", dump_user_settings)
        await interaction.response.send_message(f"✅ Watchout For Loop: {self.settings['watchoutforloop']}", ephemeral=True)

    @discord.ui.button(label="Toggle Spy Nil Globals", style=discord.ButtonStyle.danger)
    async def toggle_spy(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings["spynilglobals"] = not self.settings["spynilglobals"]
        dump_user_settings[self.user_id] = self.settings
        save_json_data("dump_user_settings.json", dump_user_settings)
        await interaction.response.send_message(f"✅ Spy Nil Globals: {self.settings['spynilglobals']}", ephemeral=True)

# ============ COMMANDS ============

@bot.command(name="l")
@status_required()
@commands.cooldown(1, 5, commands.BucketType.user)
async def dump_cmd(ctx, *, text=""):
    """Dump/deobfuscate Lua scripts"""
    code = None
    
    if ctx.message.attachments:
        try:
            code = (await ctx.message.attachments[0].read()).decode("utf-8", errors="ignore")
        except:
            await ctx.reply("❌ Failed to read attachment.")
            return
    
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            code = parts[1]
            if code.startswith("lua"):
                code = code[3:]
            elif code.startswith("luau"):
                code = code[4:]
            code = code.strip()
    
    elif text.strip():
        code = text.strip()
    
    if not code:
        await ctx.reply("❌ Provide a script file or paste it in codeblocks.\nExample: `.l \\`\\`\\`lua print('hello')\\`\\`\\``")
        return

    async with ctx.typing():
        ok, result = await run_unveilr(code, ctx.author.id)
    
    if ok:
        if len(result) > 1900:
            file = discord.File(io.BytesIO(result.encode("utf-8")), filename="dump.lua")
            await ctx.reply("✅ Dump complete:", file=file)
        else:
            await ctx.reply(f"```lua\n{result[:1900]}\n```")
    else:
        await ctx.reply(f"❌ {result}")

@bot.command(name="byp", aliases=["bypass"])
@status_required()
@commands.cooldown(1, 3, commands.BucketType.user)
async def bypass_cmd(ctx, url):
    """Bypass link shorteners"""
    if not url.startswith("http"):
        await ctx.reply("❌ Provide a valid URL.")
        return
    
    res = await byplat(url)
    if res:
        await ctx.reply(f"🔓 **Bypassed:** {res}")
    else:
        await ctx.reply("❌ Failed to bypass. Link may be unsupported.")

@bot.command(name="claim")
@commands.cooldown(1, 10, commands.BucketType.user)
async def claim_cmd(ctx, license_key):
    """Claim a license key"""
    if license_key not in licenses_data:
        await ctx.reply("❌ Invalid license key.")
        return
    
    info = licenses_data[license_key]
    if info.get("claimed"):
        await ctx.reply("❌ License already claimed.")
        return
    
    if info.get("available", 0) < time.time():
        await ctx.reply("❌ License expired.")
        return
    
    new_key = randomstr(36)
    licenses_data[new_key] = {"claimed": ctx.author.id, "available": time.time() + 1209600}
    del licenses_data[license_key]
    save_json_data("licenses.json", licenses_data)
    await refresh_whitelist()
    
    try:
        await ctx.author.send(f"✅ **Recovery Key:** ||{new_key}||\nKeep this safe!")
        await ctx.reply("✅ License claimed! Check your DMs.")
    except:
        await ctx.reply(f"✅ License claimed! Recovery key: ||{new_key}|| (SAVE THIS!)")

@bot.command(name="config")
@status_required()
async def config_cmd(ctx):
    """Configure dump settings"""
    view = DumpConfigView(ctx.author.id)
    await ctx.reply("⚙️ **Dump Configuration**", view=view, ephemeral=True)

@bot.command(name="settings", aliases=["mysettings"])
@status_required()
async def settings_cmd(ctx):
    """View your current settings"""
    settings = dump_user_settings.get(ctx.author.id, {})
    if not settings:
        await ctx.reply("📋 Using default settings.")
        return
    
    embed = discord.Embed(title="Your Dump Settings", color=0x00ff00)
    for k, v in settings.items():
        embed.add_field(name=k, value=str(v), inline=True)
    await ctx.reply(embed=embed)

@bot.command(name="resetconfig")
@status_required()
async def reset_config_cmd(ctx):
    """Reset dump settings to default"""
    if ctx.author.id in dump_user_settings:
        del dump_user_settings[ctx.author.id]
        save_json_data("dump_user_settings.json", dump_user_settings)
        await ctx.reply("🔄 Settings reset to default.")
    else:
        await ctx.reply("ℹ️ You're already using defaults.")

@bot.command(name="help", aliases=["commands"])
async def help_cmd(ctx):
    """Show all commands"""
    embed = discord.Embed(title="🔥 FlameDumper V3", color=0x5865F2)
    embed.add_field(name="**Dumping**", 
                    value="`.l` - Dump script\n`.config` - Dump settings\n`.settings` - View settings\n`.resetconfig` - Reset settings", 
                    inline=False)
    embed.add_field(name="**Tools**", 
                    value="`.byp <url>` - Bypass links\n`.gen <prompt>` - Generate image\n`.ai <prompt>` - Chat with AI", 
                    inline=False)
    embed.add_field(name="**Access**", 
                    value="`.claim <key>` - Claim license\n`.renew` - Renew license\n`.status` - Check license status", 
                    inline=False)
    embed.add_field(name="**Utility**", 
                    value="`.ping` - Bot latency\n`.invite` - Bot invite\n`.stats` - Server stats\n`.userinfo [@user]` - User info\n`.avatar [@user]` - User avatar", 
                    inline=False)
    embed.add_field(name="**Moderation**", 
                    value="`.purge <n>` - Clear messages\n`.kick <@user>` - Kick user\n`.ban <@user>` - Ban user\n`.unban <name#tag>` - Unban user\n`.mute <@user>` - Mute user\n`.unmute <@user>` - Unmute user", 
                    inline=False)
    embed.add_field(name="**Fun**", 
                    value="`.meme` - Random meme\n`.8ball <question>` - Magic 8ball\n`.roll <sides>` - Dice roll", 
                    inline=False)
    embed.add_field(name="**Admin**", 
                    value="`.say <msg>` - Make bot say\n`.embed <text>` - Send embed\n`.announce <#channel> <msg>` - Announce", 
                    inline=False)
    embed.add_field(name="**Owner**", 
                    value="`.shutdown` - Shutdown bot\n`.eval <code>` - Execute Python", 
                    inline=False)
    embed.set_footer(text=f"Status Required: {REQUIRED_STATUS} | Owner: <@{OWNER_ID}>")
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.reply(f"🏓 Pong! `{latency}ms`")

@bot.command(name="stats")
@commands.has_permissions(administrator=True)
async def stats_cmd(ctx):
    """Server statistics"""
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 Server Stats: {guild.name}", color=0x00ff00)
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.add_field(name="Emojis", value=len(guild.emojis))
    embed.add_field(name="Owner", value=str(guild.owner))
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"))
    await ctx.reply(embed=embed)

@bot.command(name="userinfo", aliases=["whois"])
async def userinfo_cmd(ctx, member: discord.Member = None):
    """Get user information"""
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 {member}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="Joined Discord", value=member.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="Roles", value=", ".join([r.name for r in member.roles if r.name != "@everyone"])[:1024] or "None")
    embed.add_field(name="Bot?", value="Yes" if member.bot else "No")
    await ctx.reply(embed=embed)

@bot.command(name="invite")
async def invite_cmd(ctx):
    """Get bot invite link"""
    invite = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot"
    await ctx.reply(f"🔗 **Invite me:** {invite}")

@bot.command(name="purge", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
@commands.cooldown(1, 3, commands.BucketType.user)
async def purge_cmd(ctx, amount: int):
    """Delete messages"""
    if amount < 1 or amount > 100:
        await ctx.reply("❌ Enter a number between 1-100.")
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.reply(f"🗑️ Deleted {len(deleted)-1} messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Kick a member"""
    if member == ctx.author:
        await ctx.reply("❌ You can't kick yourself.")
        return
    
    await member.kick(reason=reason)
    await ctx.reply(f"👢 Kicked {member.mention} | Reason: {reason}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx, member: discord.Member, *, reason="No reason"):
    """Ban a member"""
    if member == ctx.author:
        await ctx.reply("❌ You can't ban yourself.")
        return
    
    await member.ban(reason=reason)
    await ctx.reply(f"🔨 Banned {member.mention} | Reason: {reason}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_cmd(ctx, *, name):
    """Unban a member by name#tag"""
    banned_users = [entry async for entry in ctx.guild.bans()]
    for entry in banned_users:
        if str(entry.user) == name:
            await ctx.guild.unban(entry.user)
            await ctx.reply(f"✅ Unbanned {entry.user.mention}")
            return
    await ctx.reply("❌ User not found in ban list.")

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute_cmd(ctx, member: discord.Member):
    """Mute a member (adds mute role)"""
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)
    
    if mute_role in member.roles:
        await ctx.reply("❌ User already muted.")
        return
    
    await member.add_roles(mute_role)
    await ctx.reply(f"🔇 Muted {member.mention}")

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute_cmd(ctx, member: discord.Member):
    """Unmute a member"""
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role or mute_role not in member.roles:
        await ctx.reply("❌ User is not muted.")
        return
    
    await member.remove_roles(mute_role)
    await ctx.reply(f"🔊 Unmuted {member.mention}")

@bot.command(name="ai", aliases=["chat"])
@status_required()
@commands.cooldown(1, 3, commands.BucketType.user)
async def ai_cmd(ctx, *, prompt):
    """Chat with AI"""
    async with ctx.typing():
        system_prompt = f"You are an elite coding assistant. User: {ctx.author.name}. Be concise, helpful, and technical."
        msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        res, model = await chat_ai(msgs, provider="groq")
        
        if len(res) > 1900:
            file = discord.File(io.BytesIO(res.encode()), filename="response.txt")
            await ctx.reply(f"💬 Generated with {model}", file=file)
        else:
            await ctx.reply(f"💬 {res[:1900]}\n-# Generated with {model}")

@bot.command(name="gen", aliases=["imagine"])
@status_required()
@commands.cooldown(1, 10, commands.BucketType.user)
async def gen_cmd(ctx, *, prompt):
    """Generate image with AI"""
    await ctx.reply("🎨 Image generation coming soon. (HF API key required)")

@bot.command(name="meme")
@commands.cooldown(1, 5, commands.BucketType.user)
async def meme_cmd(ctx):
    """Get a random meme"""
    memes = [
        "https://i.imgflip.com/1bij.jpg",
        "https://i.imgflip.com/30b1gx.jpg",
        "https://i.imgflip.com/26am.jpg",
        "https://i.imgflip.com/1otk96.jpg",
        "https://i.imgflip.com/2k4z.jpg"
    ]
    embed = discord.Embed(title="😂 Random Meme", color=0xff9900)
    embed.set_image(url=random.choice(memes))
    await ctx.reply(embed=embed)

@bot.command(name="8ball", aliases=["eightball"])
@commands.cooldown(1, 3, commands.BucketType.user)
async def eightball_cmd(ctx, *, question):
    """Ask the magic 8ball"""
    responses = [
        "Yes", "No", "Maybe", "Ask again", "Definitely", 
        "Absolutely not", "Signs point to yes", "Outlook good",
        "Don't count on it", "Very doubtful", "Without a doubt",
        "Cannot predict now", "Concentrate and ask again"
    ]
    await ctx.reply(f"🎱 {question}\n**Answer:** {random.choice(responses)}")

@bot.command(name="roll")
@commands.cooldown(1, 2, commands.BucketType.user)
async def roll_cmd(ctx, sides: int = 6):
    """Roll a dice (default 6 sides)"""
    if sides < 1:
        await ctx.reply("❌ Sides must be positive.")
        return
    
    result = random.randint(1, sides)
    await ctx.reply(f"🎲 Rolled a d{sides}: **{result}**")

@bot.command(name="status", aliases=["license"])
async def status_cmd(ctx):
    """Check your license status"""
    if is_whitelisted(ctx.author.id):
        await ctx.reply("✅ **Premium status:** Active\n✨ All features unlocked.")
    else:
        await ctx.reply("❌ **Premium status:** Inactive\nUse `.claim <key>` to activate.")

@bot.command(name="renew")
@status_required()
async def renew_cmd(ctx):
    """Renew your license"""
    for key, info in licenses_data.items():
        if info.get("claimed") == ctx.author.id:
            info["available"] = time.time() + 1209600
            save_json_data("licenses.json", licenses_data)
            await ctx.reply("✅ License renewed for 14 days!")
            return
    await ctx.reply("❌ No license found for you.")

@bot.command(name="shutdown", aliases=["die"])
@commands.is_owner()
async def shutdown_cmd(ctx):
    """Shutdown the bot (Owner only)"""
    await ctx.reply("💀 Shutting down...")
    await bot.close()

@bot.command(name="eval")
@commands.is_owner()
async def eval_cmd(ctx, *, code):
    """Evaluate Python code (Owner only)"""
    try:
        result = eval(code)
        await ctx.reply(f"```py\n{result}\n```")
    except Exception as e:
        await ctx.reply(f"❌ Error: {e}")

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say_cmd(ctx, *, message):
    """Make the bot say something"""
    await ctx.message.delete()
    await ctx.send(message)

@bot.command(name="embed")
@commands.has_permissions(administrator=True)
async def embed_cmd(ctx, *, text):
    """Send an embed message"""
    embed = discord.Embed(description=text, color=0x5865F2)
    await ctx.message.delete()
    await ctx.send(embed=embed)

@bot.command(name="announce")
@commands.has_permissions(administrator=True)
async def announce_cmd(ctx, channel: discord.TextChannel, *, message):
    """Announce in a specific channel"""
    embed = discord.Embed(title="📢 Announcement", description=message, color=0xff0000)
    embed.set_footer(text=f"By {ctx.author.name}")
    await channel.send(embed=embed)
    await ctx.reply("✅ Announcement sent!")

@bot.command(name="avatar", aliases=["av"])
async def avatar_cmd(ctx, member: discord.Member = None):
    """Get user avatar"""
    member = member or ctx.author
    embed = discord.Embed(title=f"🖼️ {member.name}'s Avatar", color=member.color)
    embed.set_image(url=member.display_avatar.url)
    await ctx.reply(embed=embed)

# ============ ERROR HANDLING ============

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ You don't have permission to use this.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(f"❌ Invalid argument: {error}")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"⏳ Cooldown: {round(error.retry_after)}s")
    elif isinstance(error, commands.NotOwner):
        await ctx.reply("❌ Owner only command.")
    else:
        await ctx.reply(f"⚠️ Error: {str(error)[:100]}")
        print(error)

# ============ EVENTS ============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    await refresh_whitelist()
    await bot.change_presence(activity=discord.CustomActivity(name=f"{REQUIRED_STATUS} | .help"))
    print(f"📍 {len(bot.commands)} commands loaded")
    print(f"👑 Owner: {OWNER_ID}")
    print("🔓 Ready for action.")

@bot.event
async def on_message(message):
    if message.author.bot: 
        return
    
    if bot.user.mentioned_in(message):
        async with message.channel.typing():
            prompt = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
            if prompt:
                system_prompt = f"You are a rude and edgy chatbot named retard in a Discord server. User: {message.author.display_name}. Instructions: Be offensive, quirky, and use slang. Keep it short."
                msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
                res, model = await chat_ai(msgs, provider="groq")
                await message.reply(f"{res[:1900]}\n-# Generated with {model}")
            else:
                await message.reply("Say something, idiot.")
        return

    await bot.process_commands(message)

# ============ RUN ============
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN not found!")
