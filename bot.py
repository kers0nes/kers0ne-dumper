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
import certifi
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
# from google import genai # Optional based on environment
# from google.genai import types

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
    # Simplified AI logic for integration
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
    """The core dumping engine using UnveilR (Lune)"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "input.lua")
            output_path = os.path.join(tmp, "out.lua")
            with open(input_path, "w") as f: f.write(code)
            
            # User specific settings for dumping
            settings = dump_user_settings.get(user_id, {
                "varnames": True, "usesimplefunctions": False, 
                "watchoutforloop": True, "spynilglobals": False, 
                "hook_op": False
            })
            
            params = [
                f"ipt={input_path}", f"out={output_path}", 
                "version=3", f"isPremium={is_whitelisted(user_id)}"
            ]
            for k, v in settings.items():
                params.append(f"{k}={str(v).lower()}")

            lune_script = os.path.join(os.getcwd(), "dropbox_extracted", "main.luau")
            if os.path.exists(lune_script):
                cmd = [LUNE_BIN, "run", lune_script] + params
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmp)
                await asyncio.wait_for(proc.communicate(), timeout=45)
                if os.path.exists(output_path):
                    with open(output_path, "r", errors="ignore") as f: return True, f.read()
    except Exception as e:
        print(f"UnveilR Error: {e}")
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
            "varnames": True, "usesimplefunctions": False, 
            "watchoutforloop": True, "spynilglobals": False, 
            "hook_op": False
        })

    @discord.ui.button(label="Toggle Varnames", style=discord.ButtonStyle.primary)
    async def toggle_varnames(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.settings["varnames"] = not self.settings["varnames"]
        dump_user_settings[self.user_id] = self.settings
        save_json_data("dump_user_settings.json", dump_user_settings)
        await interaction.response.send_message(f"Varnames: {self.settings['varnames']}", ephemeral=True)

# ============ COMMANDS ============

@bot.command(name="l")
@status_required()
async def dump_cmd(ctx, *, text=""):
    code = None
    if ctx.message.attachments:
        code = (await ctx.message.attachments[0].read()).decode("utf-8", errors="ignore")
    elif "```" in text:
        code = text.split("```")[1]
        if code.startswith("lua"): code = code[3:]
    
    if not code:
        await ctx.reply("Please provide a script to dump.")
        return

    async with ctx.typing():
        ok, result = await run_unveilr(code, ctx.author.id)
    
    if ok:
        if len(result) > 1900:
            file = discord.File(io.BytesIO(result.encode()), filename="dump.lua")
            await ctx.reply("Dump complete:", file=file)
        else:
            await ctx.reply(f"```lua\n{result[:1900]}\n```")
    else:
        await ctx.reply("❌ Dumping failed. Make sure the script is valid.")

@bot.command(name="byp")
@status_required()
async def bypass_cmd(ctx, url):
    res = await byplat(url)
    await ctx.reply(f"Bypass Result: {res or 'Failed'}")

@bot.command(name="claim")
async def claim_cmd(ctx, license_key):
    if license_key not in licenses_data:
        await ctx.reply("Invalid license key.")
        return
    
    info = licenses_data[license_key]
    if info.get("claimed"):
        await ctx.reply("License already claimed.")
        return
    
    new_key = randomstr(36)
    licenses_data[new_key] = {"claimed": ctx.author.id, "available": time.time() + 1209600}
    del licenses_data[license_key]
    save_json_data("licenses.json", licenses_data)
    await refresh_whitelist()
    
    try:
        await ctx.author.send(f"Your Recovery Key: ||{new_key}||")
        await ctx.reply("✅ Success! Check your DMs.")
    except:
        await ctx.reply(f"✅ Success! Your recovery key is ||{new_key}|| (SAVE THIS!)")

@bot.command(name="config")
@status_required()
async def config_cmd(ctx):
    view = DumpConfigView(ctx.author.id)
    await ctx.reply("Configure your dump settings:", view=view)

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="FlameDumperV3 Commands", color=0x5865F2)
    embed.add_field(name="Dumping", value="`.l` - Dump/Deobfuscate a script\n`.config` - Configure dump settings", inline=False)
    embed.add_field(name="Tools", value="`.byp <url>` - Bypass links\n`.gen <prompt>` - Generate AI image", inline=False)
    embed.add_field(name="Access", value="`.claim <key>` - Claim a license", inline=False)
    embed.set_footer(text=f"Status Required: {REQUIRED_STATUS}")
    await ctx.send(embed=embed)

# ============ EVENTS ============

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await refresh_whitelist()
    await bot.change_presence(activity=discord.CustomActivity(name=f"{REQUIRED_STATUS} | .help"))

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # AI Interaction (Mention)
    if bot.user.mentioned_in(message):
        async with message.channel.typing():
            prompt = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
            # Persona: Edgy/Rude but helpful
            system_prompt = f"You are a rude and edgy chatbot named retard in a Discord server. User: {message.author.display_name}. Instructions: Be offensive, quirky, and use slang. Keep it short."
            msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            res, model = await chat_ai(msgs)
            await message.reply(f"{res}\n-# Generated with {model}")
            return

    await bot.process_commands(message)

# ============ RUN ============
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN not found!")
