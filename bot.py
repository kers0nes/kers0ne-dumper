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

import discord
from discord.ext import commands
from discord import CustomActivity
from discord.ui import Button, View, Select
from dotenv import load_dotenv
import aiohttp
import requests
from PIL import Image, ImageDraw, ImageColor
from hashlib import sha256

load_dotenv()

# ============ CONFIG ============
TOKEN = os.getenv("DISCORD_TOKEN")
REQUIRED_STATUS = ".gg/KFdHVt3Mm6"
OWNER_ID = 1123674631266639914
DEOBF_CHANNEL_ID = None

LUNE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catlog.luau")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUFF_DIR = os.path.join(SCRIPT_DIR, "stuff")
API_DUMP = os.path.join(STUFF_DIR, "API-Dump.json")
CLASSES_JSON = os.path.join(STUFF_DIR, "classes.json")
ENUMS_JSON = os.path.join(STUFF_DIR, "enums.json")
ASSETIDS_JSON = os.path.join(STUFF_DIR, "assetids.json")
LUNE_BIN = os.getenv("LUNE_BIN", "lune")
TIMEOUT_SECONDS = 30

NO_MENTIONS = discord.AllowedMentions.none()
URL_PATTERN = re.compile(r'https?://\S+')

# ============ BOT SETUP ============
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=".", 
    intents=intents, 
    help_command=None, 
    allowed_mentions=discord.AllowedMentions.none()
)

# ============ STATUS CHECK ============
def has_required_status(user) -> bool:
    """Check if user has .gg/KFdHVt3Mm6 in their custom status"""
    for activity in user.activities:
        if isinstance(activity, CustomActivity):
            if activity.name and REQUIRED_STATUS in activity.name:
                return True
    return False

def status_required():
    """Decorator to check if user has required status"""
    async def predicate(ctx):
        if ctx.author.id == OWNER_ID:
            return True
        if has_required_status(ctx.author):
            return True
        await ctx.reply(
            f"❌ You need to put `{REQUIRED_STATUS}` in your custom status to use this command!\n"
            f"Set it in your Discord profile -> Custom Status",
            allowed_mentions=NO_MENTIONS
        )
        return False
    return commands.check(predicate)

# ============ DETECTION ENGINE ============

class DetectionEngine:
    SIGNATURES = {
        'Moonsec': {
            'patterns': [r'[Mm]oon[Ss]ec', r'MoonSecV\d', r'moonsec v\d'],
            'weight': 10,
            'description': 'Moonsec V2/V3 - String-based VM obfuscator'
        },
        'Luraph': {
            'patterns': [r'Luraph', r'LuraphContinue', r'LPH_NO_VIRTUALIZE', r'LPH_OBFUSCATED'],
            'weight': 10,
            'description': 'Luraph - Lua bytecode VM obfuscator'
        },
        'IronBrew': {
            'patterns': [r'[Ii]ron[Bb]rew', r'IRON_VM', r'IronBrew Obfuscator'],
            'weight': 10,
            'description': 'IronBrew - Bytecode-level obfuscator'
        },
        'Namaiki': {
            'patterns': [r'namaiki', r'{0,1,1,0}', r'Protected by Namaiki'],
            'weight': 9,
            'description': 'Namaiki - Layer-based obfuscator'
        },
        'VAQ': {
            'patterns': [r'VAQ Obfuscator', r'_vaq, discord', r'_bp5nxQostOWX6XP'],
            'weight': 9,
            'description': 'VAQ - Anti-tamper obfuscator'
        },
        'Lumora': {
            'patterns': [r'lumora', r'lumora-3jx', r'Lumora Obfuscator'],
            'weight': 8,
            'description': 'Lumora - Hex-based obfuscator'
        },
        'Prometheus': {
            'patterns': [r'Prometheus', r'LPH!', r'PrometheusBytecodeMagic'],
            'weight': 8,
            'description': 'Prometheus - Bytecode compression obfuscator'
        },
        'PSU': {
            'patterns': [r'PSU Obfuscator', r'PSU v\d', r'PSU_KEY', r'PSUEncode'],
            'weight': 8,
            'description': 'PSU - Base64 encoded obfuscator'
        },
        'Riptide': {
            'patterns': [r'Riptide', r'riptide_vm', r'__riptide', r'RiptideVM'],
            'weight': 7,
            'description': 'Riptide - VM-based obfuscator'
        },
        'Cloudia': {
            'patterns': [r'Cloudia', r'cloudia_vm', r'__cloudia', r'CloudiaVM'],
            'weight': 7,
            'description': 'Cloudia - Cloud-based VM obfuscator'
        },
        'Carbon': {
            'patterns': [r'Carbon', r'carbon_vm', r'__carbon', r'CarbonVM'],
            'weight': 7,
            'description': 'Carbon - VM obfuscator'
        },
        'Nihon': {
            'patterns': [r'Nihon', r'nihon_vm', r'__nihon', r'NihonVM'],
            'weight': 7,
            'description': 'Nihon - VM obfuscator'
        },
        'Trigon': {
            'patterns': [r'Trigon', r'trigon_vm', r'__trigon', r'TrigonVM'],
            'weight': 7,
            'description': 'Trigon - VM obfuscator'
        },
        'Valyse': {
            'patterns': [r'Valyse', r'valyse_vm', r'__valyse', r'ValyseVM'],
            'weight': 7,
            'description': 'Valyse - VM obfuscator'
        },
        'Evon': {
            'patterns': [r'Evon', r'evon_vm', r'__evon', r'EvonVM'],
            'weight': 7,
            'description': 'Evon - VM obfuscator'
        },
        'Seliware': {
            'patterns': [r'Seliware', r'seliware_vm', r'__seliware', r'SeliwareVM'],
            'weight': 7,
            'description': 'Seliware - VM obfuscator'
        },
        'Electron': {
            'patterns': [r'Electron', r'electron_vm', r'__electron', r'ElectronVM'],
            'weight': 7,
            'description': 'Electron - VM obfuscator'
        },
        'Oxide': {
            'patterns': [r'Oxide', r'oxide_vm', r'__oxide', r'OxideVM'],
            'weight': 7,
            'description': 'Oxide - VM obfuscator'
        },
        'Oblivion': {
            'patterns': [r'Oblivion', r'oblivion_vm', r'__oblivion', r'OblivionVM'],
            'weight': 7,
            'description': 'Oblivion - VM obfuscator'
        },
        'Sheathe': {
            'patterns': [r'Sheathe', r'sheathe_vm', r'__sheathe', r'SheatheVM'],
            'weight': 7,
            'description': 'Sheathe - VM obfuscator'
        },
        'ByteMe': {
            'patterns': [r'ByteMe', r'byteme_vm', r'__byteme', r'ByteMeVM'],
            'weight': 7,
            'description': 'ByteMe - Bytecode obfuscator'
        },
        'LuaShield': {
            'patterns': [r'LuaShield', r'luashield', r'__luashield', r'LuaShieldVM'],
            'weight': 7,
            'description': 'LuaShield - Protection obfuscator'
        },
        'CodexVM': {
            'patterns': [r'CodexVM', r'codex_vm', r'__codex'],
            'weight': 7,
            'description': 'CodexVM - VM obfuscator'
        },
        'Hyperion': {
            'patterns': [r'Hyperion', r'Byfron', r'__hyperion', r'HyperionProtect'],
            'weight': 9,
            'description': 'Hyperion/Byfron - Anti-cheat obfuscator'
        },
        'Azur': {
            'patterns': [r'Azur', r'azur_vm', r'__azur', r'AzurObfuscator'],
            'weight': 7,
            'description': 'Azur - VM obfuscator'
        },
        'Hercules': {
            'patterns': [r'Hercules', r'hercules_vm', r'__hercules', r'HerculesVM'],
            'weight': 7,
            'description': 'Hercules - VM obfuscator'
        },
        'Nova': {
            'patterns': [r'Nova', r'nova_vm', r'__nova', r'NovaObfuscator'],
            'weight': 7,
            'description': 'Nova - VM obfuscator'
        },
        'Acedia': {
            'patterns': [r'Acedia', r'acedia_vm', r'__acedia', r'AcediaVM'],
            'weight': 7,
            'description': 'Acedia - VM obfuscator'
        },
        'ScriptWare': {
            'patterns': [r'ScriptWare', r'__scriptware', r'ScriptWareVM'],
            'weight': 6,
            'description': 'ScriptWare - Executor obfuscator'
        },
        'CocoZ': {
            'patterns': [r'CocoZ', r'coco_z_', r'__cocoz'],
            'weight': 6,
            'description': 'CocoZ - Executor obfuscator'
        },
        'Synapse': {
            'patterns': [r'Synapse', r'__synapse', r'syn\.protect_gui', r'Synapse X'],
            'weight': 8,
            'description': 'Synapse X - Executor obfuscator'
        },
        'Krnl': {
            'patterns': [r'Krnl', r'__krnl', r'krnl\.request', r'KRNL_LOADED'],
            'weight': 8,
            'description': 'Krnl - Executor obfuscator'
        },
        'Fluxus': {
            'patterns': [r'Fluxus', r'__fluxus', r'fluxus\.request'],
            'weight': 8,
            'description': 'Fluxus - Executor obfuscator'
        },
        'Sentinel': {
            'patterns': [r'Sentinel', r'__sentinel', r'sentinel\.request'],
            'weight': 7,
            'description': 'Sentinel - Executor obfuscator'
        },
        'Wave': {
            'patterns': [r'Wave', r'__wave', r'wave\.request'],
            'weight': 7,
            'description': 'Wave - Executor obfuscator'
        },
        'Celery': {
            'patterns': [r'Celery', r'__celery'],
            'weight': 6,
            'description': 'Celery - Executor obfuscator'
        },
        'Oxygen': {
            'patterns': [r'Oxygen', r'__oxygen'],
            'weight': 6,
            'description': 'Oxygen - Executor obfuscator'
        },
        'Hydrogen': {
            'patterns': [r'Hydrogen', r'__hydrogen'],
            'weight': 6,
            'description': 'Hydrogen - Executor obfuscator'
        },
        'Delta': {
            'patterns': [r'Delta', r'__delta'],
            'weight': 6,
            'description': 'Delta - Executor obfuscator'
        },
        'Comet': {
            'patterns': [r'Comet', r'__comet'],
            'weight': 6,
            'description': 'Comet - Executor obfuscator'
        },
        'Swift': {
            'patterns': [r'Swift', r'__swift'],
            'weight': 6,
            'description': 'Swift - Executor obfuscator'
        },
        'Xeno': {
            'patterns': [r'Xeno', r'__xeno'],
            'weight': 6,
            'description': 'Xeno - Executor obfuscator'
        },
        'Arceus': {
            'patterns': [r'Arceus', r'__arceus'],
            'weight': 6,
            'description': 'Arceus - Executor obfuscator'
        },
        'Velocity': {
            'patterns': [r'Velocity', r'__velocity'],
            'weight': 6,
            'description': 'Velocity - Executor obfuscator'
        },
        'Zorara': {
            'patterns': [r'Zorara', r'__zorara'],
            'weight': 6,
            'description': 'Zorara - Executor obfuscator'
        },
        'Potassium': {
            'patterns': [r'Potassium', r'__potassium'],
            'weight': 6,
            'description': 'Potassium - Executor obfuscator'
        },
        'MacSploit': {
            'patterns': [r'MacSploit', r'__macsploit'],
            'weight': 6,
            'description': 'MacSploit - Executor obfuscator'
        },
        'ScriptHub': {
            'patterns': [r'ScriptHub', r'__script_hub'],
            'weight': 5,
            'description': 'ScriptHub - Script obfuscator'
        },
        'Dex': {
            'patterns': [r'Dex', r'__dex', r'DarkDex'],
            'weight': 5,
            'description': 'Dex/DarkDex - Explorer obfuscator'
        },
        'Hydroxide': {
            'patterns': [r'Hydroxide', r'__hydroxide'],
            'weight': 5,
            'description': 'Hydroxide - Script obfuscator'
        },
        'InfiniteYield': {
            'patterns': [r'InfiniteYield', r'__infinite_yield'],
            'weight': 5,
            'description': 'Infinite Yield - Admin script obfuscator'
        },
    }
    
    GENERIC = {
        'String-Char Obfuscator': {
            'patterns': [r'string\.char\(', r'table\.concat\('],
            'weight': 3,
            'description': 'String.char chain obfuscator'
        },
        'VM Dispatcher': {
            'patterns': [r'while\s+true\s+do', r'elseif\s+\w+\s*==\s*\d+\s+then'],
            'weight': 3,
            'description': 'VM dispatcher loop obfuscator'
        },
        'Base64 Loader': {
            'patterns': [r'loadstring\(', r'[A-Za-z0-9+/]{32,}={0,2}'],
            'weight': 3,
            'description': 'Base64 encoded loader'
        },
        'XOR Encoded': {
            'patterns': [r'bit32\.bxor\(', r'bxor\(', r'bit\.bxor\('],
            'weight': 3,
            'description': 'XOR encoded strings'
        },
        'Zlib Compressed': {
            'patterns': [r'zlib\.decompress', r'zlib\.inflate'],
            'weight': 3,
            'description': 'Zlib compressed payload'
        },
        'Luau Bytecode': {
            'patterns': [r'\x1bLua', r'\x1bLJ'],
            'weight': 4,
            'description': 'Luau bytecode loader'
        },
    }
    
    @classmethod
    def detect(cls, code):
        results = {}
        for name, sig in cls.SIGNATURES.items():
            score = 0
            for pattern in sig['patterns']:
                if re.search(pattern, code, re.IGNORECASE):
                    score += sig['weight']
            if score > 0:
                results[name] = {
                    'score': score,
                    'description': sig['description'],
                    'confidence': min(100, int((score / (len(sig['patterns']) * sig['weight'])) * 100))
                }
        
        for name, sig in cls.GENERIC.items():
            score = 0
            for pattern in sig['patterns']:
                if re.search(pattern, code, re.IGNORECASE):
                    score += sig['weight']
            if score > 0:
                results[name] = {
                    'score': score,
                    'description': sig['description'],
                    'confidence': min(100, int((score / (len(sig['patterns']) * sig['weight'])) * 100))
                }
        
        return sorted(results.items(), key=lambda x: x[1]['confidence'], reverse=True)
    
    @classmethod
    def get_summary(cls, code):
        results = cls.detect(code)
        if not results:
            return "No obfuscation detected. The code appears to be plain Lua."
        
        lines = ["**Obfuscation Detection Results:**", ""]
        for name, data in results[:10]:
            confidence = data['confidence']
            bar = '█' * (confidence // 10) + '░' * (10 - (confidence // 10))
            lines.append(f"**{name}**")
            lines.append(f"  Confidence: {confidence}% {bar}")
            lines.append(f"  Description: {data['description']}")
            lines.append("")
        
        if len(results) > 10:
            lines.append(f"*... and {len(results) - 10} more detected*")
        return '\n'.join(lines)

# ============ OBFUSCATION ENGINE ============

class ObfuscationEngine:
    @staticmethod
    def randomstr(length):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def random_ident():
        prefixes = ['_', '_0x', 'O0', 'l1', 'I1', 'll', 'II', 'OO', '00']
        return random.choice(prefixes) + ObfuscationEngine.randomstr(6)
    
    @staticmethod
    def moonsec_obfuscate(code, level=1):
        result = ['-- MoonSec Obfuscator v3.0', '-- Protected by MoonSec', '']
        var_map = {}
        lines = code.split('\n')
        
        for line in lines:
            if '=' in line and not line.strip().startswith('--'):
                parts = line.split('=')
                if len(parts) == 2:
                    var = parts[0].strip()
                    if var and var.isidentifier() and var not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return']:
                        if var not in var_map:
                            var_map[var] = ObfuscationEngine.random_ident()
        
        for line in lines:
            obf_line = line
            for orig, obf in var_map.items():
                obf_line = obf_line.replace(orig, obf)
            result.append(obf_line)
        
        if level >= 2:
            code = '\n'.join(result)
            def encode_string(match):
                s = match.group(1) or match.group(2)
                chars = [str(ord(c)) for c in s]
                return f'string.char({",".join(chars)})'
            code = re.sub(r'(["\'])([^"\']*)\1', encode_string, code)
            result = code.split('\n')
        
        if level >= 3:
            code = '\n'.join(result)
            vm_code = f'''
local _0x{ObfuscationEngine.randomstr(4)} = {{}}
local function {ObfuscationEngine.random_ident()}(...)
    local _args = {{...}}
    {code}
end
{'_' + ObfuscationEngine.randomstr(8)} = {ObfuscationEngine.random_ident()}
{'_' + ObfuscationEngine.randomstr(8)}()
'''
            return vm_code
        
        return '\n'.join(result)
    
    @staticmethod
    def luraph_obfuscate(code, level=1):
        result = ['-- Luraph Obfuscator v1.0', '-- Protected by Luraph', '']
        
        if level >= 2:
            hex_code = code.encode().hex()
            result.append(f'local _ = "{hex_code}"')
            result.append('local function decode(s)')
            result.append('  local t = {}')
            result.append('  for i = 1, #s, 2 do')
            result.append('    t[#t+1] = string.char(tonumber(s:sub(i, i+1), 16))')
            result.append('  end')
            result.append('  return table.concat(t)')
            result.append('end')
            result.append('loadstring(decode(_))()')
            return '\n'.join(result)
        
        obf_vars = {}
        lines = code.split('\n')
        for line in lines:
            if 'function' in line or 'local' in line:
                matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', line)
                for m in matches:
                    if m not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return']:
                        if m not in obf_vars:
                            obf_vars[m] = ObfuscationEngine.random_ident()
                        line = line.replace(m, obf_vars[m])
            result.append(line)
        
        return '\n'.join(result)
    
    @staticmethod
    def ironbrew_obfuscate(code, level=1):
        result = ['-- IronBrew Obfuscator v1.0', '-- Protected by IronBrew', '']
        
        if level >= 2:
            bytes_data = [str(ord(c)) for c in code]
            result.append(f'local _ = {{ {",".join(bytes_data)} }}')
            result.append('local function decode(t)')
            result.append('  local s = {}')
            result.append('  for i = 1, #t do')
            result.append('    s[#s+1] = string.char(t[i])')
            result.append('  end')
            result.append('  return table.concat(s)')
            result.append('end')
            result.append('loadstring(decode(_))()')
            return '\n'.join(result)
        
        lines = code.split('\n')
        for line in lines:
            if '=' in line and not line.strip().startswith('--'):
                parts = line.split('=')
                if len(parts) == 2:
                    var = parts[0].strip()
                    val = parts[1].strip()
                    if var and var.isidentifier():
                        line = f'local {ObfuscationEngine.random_ident()} = {val}; {var} = {ObfuscationEngine.random_ident()}'
            result.append(line)
        
        return '\n'.join(result)
    
    @staticmethod
    def generic_obfuscate(code, level=1):
        if level == 1:
            var_map = {}
            lines = code.split('\n')
            for line in lines:
                matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', line)
                for m in matches:
                    if m not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return', 'nil', 'true', 'false']:
                        if m not in var_map:
                            var_map[m] = ObfuscationEngine.random_ident()
            for orig, obf in var_map.items():
                code = code.replace(orig, obf)
            return code
        
        elif level == 2:
            lines = code.split('\n')
            for i in range(len(lines)):
                if i % 3 == 0:
                    lines.insert(i, f'local _{ObfuscationEngine.randomstr(4)} = {random.randint(1, 9999)}')
            return '\n'.join(lines)
        
        elif level == 3:
            lines = ['local function main()']
            for line in code.split('\n'):
                lines.append(f'  {line}')
            lines.append('end')
            lines.append(f'local _{ObfuscationEngine.randomstr(8)} = main')
            lines.append(f'_{ObfuscationEngine.randomstr(8)}()')
            return '\n'.join(lines)
        
        return code

# ============ LUNE ENGINE ============

def sanitize_output(text: str) -> str:
    ZWSP = '\u200b'
    text = text.replace("@everyone", "@" + ZWSP + "everyone")
    text = text.replace("@here", "@" + ZWSP + "here")
    text = re.sub(r'<@&(\d+)>', lambda m: '<@&' + ZWSP + m.group(1) + '>', text)
    text = re.sub(r'<@!?(\d+)>', lambda m: '<@' + ZWSP + m.group(1) + '>', text)
    text = re.sub(r'<#(\d+)>', lambda m: '<#' + ZWSP + m.group(1) + '>', text)
    return text

async def download_from_url(url: str) -> str | None:
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    elif "pastebin.com" in url and "/raw/" not in url:
        paste_id = url.split("/")[-1]
        url = f"https://pastebin.com/raw/{paste_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.text(errors="ignore")
    except Exception:
        return None
    return None

def run_lune(code: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, "input.lua")
        output_path = os.path.join(tmp, "out.lua")

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = [
            LUNE_BIN,
            "run",
            LUNE_SCRIPT,
            "--",
            input_path,
            f"out={output_path}",
            f"api_dump={API_DUMP}",
        ]

        if os.path.isfile(CLASSES_JSON):
            cmd.append(f"classes={CLASSES_JSON}")
        if os.path.isfile(ENUMS_JSON):
            cmd.append(f"enums={ENUMS_JSON}")
        if os.path.isfile(ASSETIDS_JSON):
            cmd.append(f"assetids={ASSETIDS_JSON}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=tmp,
            )
        except FileNotFoundError:
            return False, "Could not find the lune executable. Set LUNE_BIN in your .env."
        except subprocess.TimeoutExpired:
            return False, "exceeded the time limit."

        if proc.returncode != 0 and not os.path.exists(output_path):
            err = (proc.stderr or proc.stdout or "Unknown error").strip()
            return False, err[:1900]

        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                return True, f.read()

        return False, (proc.stdout or "No output.").strip()[:1900]

# ============ HELPER FUNCTIONS ============

async def extract_code(ctx: commands.Context, content: str) -> str | None:
    if ctx.message.attachments:
        att = ctx.message.attachments[0]
        data = await att.read()
        return data.decode("utf-8", errors="ignore")

    if ctx.message.reference:
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            ref_msg = None
        if ref_msg:
            if ref_msg.attachments:
                data = await ref_msg.attachments[0].read()
                return data.decode("utf-8", errors="ignore")
            if ref_msg.content:
                content = ref_msg.content + "\n" + content

    match = URL_PATTERN.search(content)
    if match:
        url = match.group(0)
        code = await download_from_url(url)
        if code:
            return code

    if "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            block = parts[1]
            first_line, _, rest = block.partition("\n")
            if first_line.strip().isalpha():
                return rest
            return block

    return None

async def get_text_file(ctx):
    content = await extract_code(ctx, "")
    if content:
        return content
    return None

def randomstr(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def softerror(msg, reply, waitdelete=6):
    botmsg = await msg.reply(reply)
    try:
        await msg.delete()
    except:
        pass
    await asyncio.sleep(waitdelete)
    await botmsg.delete()

def string_to_discordfile(string, filename=None, justbuffer=False):
    buffer = io.BytesIO()
    buffer.write(string.encode())
    buffer.seek(0)
    if justbuffer:
        return buffer
    return discord.File(buffer, filename=filename)

# ============ COMMAND MANAGER ============

command_manager = {}
command_cooldowns = defaultdict(int)

def is_on_cooldown(user_id, command_name, cooldown=5):
    key = f"{user_id}:{command_name}"
    if command_cooldowns[key] > time.time():
        return True
    command_cooldowns[key] = time.time() + cooldown
    return False

# ============ BOT COMMANDS ============

@bot.command(name="help")
@status_required()
async def help_cmd(ctx):
    help_text = f"""Available Commands:

📁 FILE PROCESSING:
.l - Deobfuscate Lua scripts (lune/catlog.luau engine)
.deobfuscate - Alias for .l
.detect - Detect obfuscator type
.beautify - Beautify Lua code
.minify - Minify Lua code
.compress - Compress Lua code
.rename - Rename Lua variables
.upload - Upload code to paste services

🔒 OBFUSCATION:
.moonsecobf [level] - Moonsec-style obfuscation
.luraphobf [level] - Luraph-style obfuscation
.ironbrewobf [level] - IronBrew-style obfuscation
.obf [level] - Generic obfuscation
.moonveil - Free daily Moonveil obfuscation
.goofy - Goofyscator obfuscation

🔓 DEOBFUSCATION:
.msdeobf - Moonsec V3 deobfuscation
.promdeobf - Prometheus deobfuscation (RELUA)
.ibdeobf - IronBrew 2 deobfuscation
.deobf - LuaObfuscator string decryption

🌐 WEB TOOLS:
.byp <url> - Bypass link shorteners
.gen <prompt> - Generate AI images
.get <url> - Fetch content from URL

⚙️ OTHER:
.ping - Bot latency
.say <text> - Echo text
.color <hex> - Generate color gradient
.meow - Cute meow
.solara - Check Solara executor status
.darklua - Darklua configuration panel

**Requirement:** Put `{REQUIRED_STATUS}` in your custom status!
Levels: 1=Basic, 2=Medium, 3=Heavy"""
    await ctx.send(help_text)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

@bot.command(name="say")
@status_required()
async def say_cmd(ctx, *, text):
    await ctx.send(discord.utils.escape_mentions(text))

@bot.command(name="meow")
async def meow_cmd(ctx):
    await ctx.send("meow " * random.randint(1, 5))

@bot.command(name="color")
@status_required()
async def color_cmd(ctx, hex_code):
    try:
        hex_code = hex_code.lstrip('#')
        if not (len(hex_code) == 6 or len(hex_code) == 8):
            await ctx.send("Invalid hex code. Use .color #RRGGBB")
            return
        
        rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        if len(hex_code) == 8:
            rgb = rgb + (int(hex_code[6:8], 16),)
        else:
            rgb = rgb + (255,)
        
        img = Image.new("RGBA", (80, 80), rgb)
        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, "color.png"))
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command(name="byp")
@status_required()
async def bypass_cmd(ctx, url):
    if not url.startswith("http"):
        await ctx.send("Provide valid URL starting with http:// or https://")
        return
    
    if is_on_cooldown(ctx.author.id, "byp", 10):
        await ctx.send("⏳ Slow down! Wait a bit.")
        return
    
    await ctx.send(f"Bypassing {url}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as resp:
                if str(resp.url) != url:
                    await ctx.send(f"Bypassed URL: {str(resp.url)}")
                    return
        
        async with aiohttp.ClientSession() as session:
            async with session.post("https://bypass.vip/api/bypass", json={"url": url}) as resp:
                data = await resp.json()
                if data.get("success"):
                    dest = data.get("result", {}).get("destination")
                    if dest:
                        await ctx.send(f"Bypassed URL: {dest}")
                        return
        
        await ctx.send("Could not bypass URL. Try https://bypass.vip")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command(name="gen")
@status_required()
async def gen_cmd(ctx, *, prompt):
    if not prompt:
        await ctx.send("Provide a prompt")
        return
    
    if is_on_cooldown(ctx.author.id, "gen", 10):
        await ctx.send("⏳ Slow down! Wait a bit.")
        return
    
    msg = await ctx.send("🎨 Generating image...")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://image.pollinations.ai/prompt/{prompt}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    await msg.delete()
                    await ctx.send(file=discord.File(io.BytesIO(data), "generated.png"))
                else:
                    await msg.edit(content="Generation failed")
    except Exception as e:
        await msg.edit(content=f"Error: {str(e)}")

@bot.command(name="get")
@status_required()
async def get_cmd(ctx, url=None):
    if not url:
        # Try to get from attachments
        if ctx.message.attachments:
            data = await ctx.message.attachments[0].read()
            await ctx.send(file=string_to_discordfile(data.decode('utf-8', errors='ignore'), "fetched.lua"))
            return
        await ctx.send("Provide a URL or attach a file")
        return
    
    content = await download_from_url(url)
    if content:
        await ctx.send(file=string_to_discordfile(content, "fetched.lua"))
    else:
        await ctx.send("Failed to fetch content from URL")

@bot.command(name="upload")
@status_required()
async def upload_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a file to upload")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://pastefy.app/api/v2/paste", json={
                "content": content,
                "title": "uploaded by 25ms",
                "visibility": "UNLISTED"
            }) as resp:
                data = await resp.json()
                if data.get("success"):
                    url = data['paste']['raw_url']
                    await ctx.send(f"{url}\n\n`loadstring(game:HttpGet'{url}')()`")
                else:
                    await ctx.send("Upload failed")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# ============ L COMMAND (DEOBFUSCATE) ============

@bot.command(name="l")
@status_required()
async def analyze_cmd(ctx: commands.Context, *, text: str = ""):
    code = await extract_code(ctx, text)

    if not code or not code.strip():
        await ctx.reply(
            "Attach a .lua/.luau file, reply to a message that has one, "
            "put the code in a ```lua ... ``` code block, or provide a valid code link.",
            allowed_mentions=NO_MENTIONS
        )
        return

    if is_on_cooldown(ctx.author.id, "l", 5):
        await ctx.reply("⏳ Slow down! Wait a bit.")
        return

    async with ctx.typing():
        loop = asyncio.get_running_loop()
        ok, result = await loop.run_in_executor(None, run_lune, code)

    result = sanitize_output(result)

    if not ok:
        await ctx.reply(f"Error:\n```\n{result}\n```", allowed_mentions=NO_MENTIONS)
        return

    if len(result) > 1900:
        file = discord.File(io.BytesIO(result.encode("utf-8")), filename="result.lua")
        await ctx.reply("done, attached file:", file=file, allowed_mentions=NO_MENTIONS)
    else:
        await ctx.reply(f"Result:\n```lua\n{result}\n```", allowed_mentions=NO_MENTIONS)

@bot.command(name="deobfuscate", aliases=["deob"])
@status_required()
async def deobfuscate_cmd(ctx: commands.Context, *, text: str = ""):
    await analyze_cmd(ctx, text=text)

# ============ DETECT ============

@bot.command(name="detect")
@status_required()
async def detect_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    summary = DetectionEngine.get_summary(content)
    embed = discord.Embed(
        color=0x5865F2,
        title="🔍 Obfuscation Detection",
        description=summary,
        timestamp=datetime.now()
    )
    embed.set_footer(text="FlameDumperV3")
    await ctx.send(embed=embed)

# ============ BEAUTIFY ============

@bot.command(name="beautify")
@status_required()
async def beautify_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    lines = content.split('\n')
    result = []
    indent = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(end|elseif|else|until|})', line):
            indent = max(0, indent - 1)
        result.append('    ' * indent + line)
        if re.search(r'\b(then|do|function|if|elseif|else|for|while|repeat|{)s*$', line):
            indent += 1
    
    buffer = io.StringIO()
    buffer.write('\n'.join(result))
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "beautified.lua"))

# ============ MINIFY ============

@bot.command(name="minify")
@status_required()
async def minify_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    content = re.sub(r'--[^\n]*', '', content)
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([=+-/*])\s*', r'\1', content)
    content = re.sub(r';\s*', ';', content)
    
    buffer = io.StringIO()
    buffer.write(content.strip())
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "minified.lua"))

# ============ COMPRESS ============

@bot.command(name="compress")
@status_required()
async def compress_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    content = re.sub(r'--[^\n]*', '', content)
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([=+-/*])\s*', r'\1', content)
    
    var_map = {}
    def shorten(m):
        name = m.group(1)
        if name not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return']:
            if name not in var_map:
                var_map[name] = f'v{len(var_map)}'
            return var_map[name]
        return name
    content = re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', shorten, content)
    
    buffer = io.StringIO()
    buffer.write(content.strip())
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "compressed.lua"))

# ============ RENAME ============

@bot.command(name="rename")
@status_required()
async def rename_cmd(ctx):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://renamer-api.vercel.app/api/rename",
                json={"code": content},
                headers={"x-api-key": "33ms-DHJHS-24633"}
            ) as resp:
                data = await resp.json()
                renamed = data.get("renamedCode")
                if renamed:
                    buffer = io.StringIO()
                    buffer.write(renamed)
                    buffer.seek(0)
                    await ctx.send(file=discord.File(buffer, "renamed.lua"))
                else:
                    await ctx.send("Rename failed")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# ============ OBFUSCATION COMMANDS ============

@bot.command(name="moonsecobf")
@status_required()
async def moonsecobf_cmd(ctx, level: int = 1):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    if level not in [1, 2, 3]:
        await ctx.send("Level must be 1, 2, or 3")
        return
    
    msg = await ctx.send(f"🔒 Moonsec obfuscation (Level {level})...")
    result = ObfuscationEngine.moonsec_obfuscate(content, level)
    buffer = io.StringIO()
    buffer.write(result)
    buffer.seek(0)
    await msg.edit(content=f"✅ Moonsec Obfuscated (Level {level})")
    await ctx.send(file=discord.File(buffer, "moonsec_obfuscated.lua"))

@bot.command(name="luraphobf")
@status_required()
async def luraphobf_cmd(ctx, level: int = 1):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    if level not in [1, 2, 3]:
        await ctx.send("Level must be 1, 2, or 3")
        return
    
    msg = await ctx.send(f"🔒 Luraph obfuscation (Level {level})...")
    result = ObfuscationEngine.luraph_obfuscate(content, level)
    buffer = io.StringIO()
    buffer.write(result)
    buffer.seek(0)
    await msg.edit(content=f"✅ Luraph Obfuscated (Level {level})")
    await ctx.send(file=discord.File(buffer, "luraph_obfuscated.lua"))

@bot.command(name="ironbrewobf")
@status_required()
async def ironbrewobf_cmd(ctx, level: int = 1):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    if level not in [1, 2, 3]:
        await ctx.send("Level must be 1, 2, or 3")
        return
    
    msg = await ctx.send(f"🔒 IronBrew obfuscation (Level {level})...")
    result = ObfuscationEngine.ironbrew_obfuscate(content, level)
    buffer = io.StringIO()
    buffer.write(result)
    buffer.seek(0)
    await msg.edit(content=f"✅ IronBrew Obfuscated (Level {level})")
    await ctx.send(file=discord.File(buffer, "ironbrew_obfuscated.lua"))

@bot.command(name="obf")
@status_required()
async def obf_cmd(ctx, level: int = 1):
    content = await get_text_file(ctx)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    if level not in [1, 2, 3]:
        await ctx.send("Level must be 1, 2, or 3")
        return
    
    msg = await ctx.send(f"🔒 Generic obfuscation (Level {level})...")
    result = ObfuscationEngine.generic_obfuscate(content, level)
    buffer = io.StringIO()
    buffer.write(result)
    buffer.seek(0)
    await msg.edit(content=f"✅ Generic Obfuscated (Level {level})")
    await ctx.send(file=discord.File(buffer, "obfuscated.lua"))

# ============ SOLARA ============

@bot.command(name="solara")
async def solara_cmd(ctx):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://solara-api.example.com/status") as resp:
                data = await resp.json()
                status = "✅ Updated" if data.get("supported") else "❌ Outdated"
                download = data.get("url", "https://solara.example.com/download")
                changelog = data.get("changelog", "No recent changes")
                await ctx.send(f"**Solara Status**\nStatus: {status}\nDownload: {download}\nChangelog:\n```diff\n{changelog}\n```")
    except:
        await ctx.send("Solara API unavailable")

# ============ DARKLUA GUI ============

class DarkluaConfigView(View):
    def __init__(self, user_id: int, filename: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.filename = filename
        self.generator = "readable"
        self.column_span = 80
        self.selected_rules = ["compute_expression", "convert_index_to_field"]
        self.processing = False
        
        self.available_rules = [
            "compute_expression",
            "remove_unused_while",
            "remove_unused_if_branch",
            "remove_nil_declaration",
            "convert_index_to_field",
            "remove_comments",
            "remove_method_definition",
            "remove_spaces",
            "remove_types",
            "remove_unused_variable",
            "remove_function_call_parens",
        ]
        
        self.add_item(self.RuleSelect(self))
        self.add_item(self.GeneratorButton("readable", self))
        self.add_item(self.GeneratorButton("dense", self))
        self.add_item(self.ApplyButton(self))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your config.", ephemeral=True)
            return False
        return True

    class RuleSelect(Select):
        def __init__(self, view):
            self.view_ref = view
            options = [discord.SelectOption(label=rule, value=rule) for rule in view.available_rules[:25]]
            super().__init__(placeholder="Select rules...", min_values=0, max_values=len(options), options=options)

        async def callback(self, interaction):
            self.view_ref.selected_rules = list(self.values)
            await interaction.response.edit_message(content="Rules updated!", view=self.view_ref)

    class GeneratorButton(Button):
        def __init__(self, gen, view):
            self.generator_type = gen
            self.view_ref = view
            style = discord.ButtonStyle.primary if view.generator == gen else discord.ButtonStyle.secondary
            super().__init__(label=f"Gen: {gen}", style=style, row=1)

        async def callback(self, interaction):
            self.view_ref.generator = self.generator_type
            for item in self.view_ref.children:
                if isinstance(item, DarkluaConfigView.GeneratorButton):
                    item.style = discord.ButtonStyle.primary if item.generator_type == self.generator_type else discord.ButtonStyle.secondary
            await interaction.response.edit_message(content="Generator updated!", view=self.view_ref)

    class ApplyButton(Button):
        def __init__(self, view):
            self.view_ref = view
            super().__init__(label="Apply", style=discord.ButtonStyle.success, row=3)

        async def callback(self, interaction):
            if self.view_ref.processing:
                await interaction.response.send_message("Already processing...", ephemeral=True)
                return
            self.view_ref.processing = True
            await interaction.response.defer()
            await interaction.followup.send("Darklua processing complete! (Placeholder)", ephemeral=True)
            self.view_ref.processing = False

@bot.command(name="darklua")
@status_required()
async def darklua_cmd(ctx):
    filename = await get_text_file(ctx)
    if not filename:
        await ctx.send("Attach a Lua file")
        return
    
    view = DarkluaConfigView(ctx.author.id, "temp.lua")
    await ctx.send(content="Configure Darklua", view=view)

# ============ SETUP ============

@bot.command(name="setup")
async def setup(ctx):
    global DEOBF_CHANNEL_ID
    DEOBF_CHANNEL_ID = ctx.channel.id
    await ctx.send(f"Setup complete - .deobfuscate commands active in {ctx.channel.mention}")

# ============ STATUS CHECK ============

@bot.command(name="checkstatus")
async def checkstatus(ctx):
    if has_required_status(ctx.author):
        await ctx.send(f"✅ You have `{REQUIRED_STATUS}` in your status! All commands available.")
    else:
        await ctx.send(f"❌ You need to put `{REQUIRED_STATUS}` in your custom status to use commands!")

# ============ ON_READY ============

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📌 Required status: {REQUIRED_STATUS}")
    await bot.change_presence(
        activity=discord.CustomActivity(
            name=f"{REQUIRED_STATUS} | .help for commands"
        )
    )

# ============ ON_PRESENCE_UPDATE ============

@bot.event
async def on_presence_update(before, after):
    """Auto-role based on status"""
    try:
        guild = bot.get_guild(1306714913539887237)
        if not guild:
            return
        
        role = guild.get_role(1385300853526892584)
        if not role:
            return
        
        member = guild.get_member(after.id)
        if not member:
            return
        
        has_status = False
        for activity in after.activities:
            if isinstance(activity, CustomActivity):
                if activity.name and REQUIRED_STATUS in activity.name:
                    has_status = True
                    break
        
        if has_status:
            if role not in member.roles:
                await member.add_roles(role)
                print(f"✅ Added role to {member.name}")
        else:
            if role in member.roles:
                await member.remove_roles(role)
                print(f"❌ Removed role from {member.name}")
    except Exception as e:
        print(f"Presence update error: {e}")

# ============ RUN ============

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not set")
        exit(1)
    
    print("🤖 Starting Kers0ne Dumper Bot - CAT Edition")
    print(f"📌 Required status: {REQUIRED_STATUS}")
    print("ℹ️  Use .help to see all commands")
    
    bot.run(TOKEN)
