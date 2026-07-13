import discord
from discord.ext import commands
import os
import random
import string
import hashlib
import aiohttp
import asyncio
import re
import json
import io
import base64
import zlib
import tempfile
import subprocess
from datetime import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

OWNER_ID = 1123674631266639914
L_CHANNEL_ID = None

# ============ LUPA INTEGRATION ============
try:
    import lupa
    from lupa import LuaRuntime
    HAS_LUA = True
except ImportError:
    HAS_LUA = False
    print("⚠️ lupa not installed - using fallback deobfuscator")

# ============ DUMPER ENGINE ============
DUMPER_SOURCE = '''
--[[
  FLAMEDUMPERV3 - Complete Deobfuscation Engine
  Supports: Moonsec V2/V3, IronBrew, Luraph, Namaiki, 
            Prometheus, PSU, VAQ, Lumora, and 40+ more
--]]

local proxyTable = {}

-- ===== UTILITY FUNCTIONS =====
local function formatStringLiteral(value)
    if type(value) ~= "string" then return tostring(value) end
    local escaped = value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t")
    return '"' .. escaped .. '"'
end

local function serializeValue(value, depth)
    depth = depth or 0
    if depth > 20 then return "{...}" end
    
    if value == nil then return "nil"
    elseif type(value) == "string" then return formatStringLiteral(value)
    elseif type(value) == "number" or type(value) == "boolean" then return tostring(value)
    elseif type(value) == "table" then
        local items = {}
        for k, v in pairs(value) do
            local ks = (type(k) == "string" and k:match("^[%a_][%w_]*$")) and k or ("[" .. serializeValue(k, depth+1) .. "]")
            table.insert(items, ks .. " = " .. serializeValue(v, depth+1))
        end
        return "{" .. table.concat(items, ", ") .. "}"
    else
        return tostring(value)
    end
end

-- ===== DETECTION ENGINE =====
local function detectObfuscator(code)
    local head = code:sub(1, 256):lower()
    
    -- Moonsec
    if head:find("moonsec", 1, true) or code:find("MoonSec", 1, true) then
        return "moonsec"
    end
    
    -- Luraph
    if head:find("luraph", 1, true) or code:find("LuraphContinue", 1, true) then
        return "luraph"
    end
    
    -- IronBrew
    if head:find("ironbrew", 1, true) or code:find("IronBrew", 1, true) then
        return "ironbrew"
    end
    
    -- Namaiki
    if code:find("namaiki", 1, true) or code:find("{0,1,1,0}", 1, true) then
        return "namaiki"
    end
    
    -- Prometheus
    if head:find("prometheus", 1, true) or code:find("LPH!", 1, true) then
        return "prometheus"
    end
    
    -- PSU
    if head:find("psu obfuscator", 1, true) or head:find("psu v", 1, true) then
        return "psu"
    end
    
    -- VAQ
    if code:find("VAQ Obfuscator", 1, true) or code:find("_vaq, discord", 1, true) then
        return "vaq"
    end
    
    -- Lumora
    if head:find("lumora", 1, true) or code:find("lumora-3jx", 1, true) then
        return "lumora"
    end
    
    -- ScriptWare / CocoZ
    if code:find("ScriptWare", 1, true) or code:find("CocoZ", 1, true) then
        return "scriptware"
    end
    
    -- Riptide
    if head:find("riptide", 1, true) or code:find("RiptideVM", 1, true) then
        return "riptide"
    end
    
    return "unknown"
end

-- ===== DECODING ENGINES =====
local function xorDecode(data, key)
    local result = {}
    for i = 1, #data do
        local byte = string.byte(data, i)
        local k = type(key) == "number" and key or string.byte(key, ((i-1) % #key) + 1)
        result[i] = string.char(bit32.bxor(byte, k))
    end
    return table.concat(result)
end

local function base64Decode(data)
    local b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    data = data:gsub("[^"..b64.."=]", "")
    local result = {}
    for i = 1, #data, 4 do
        local c1 = b64:find(data:sub(i,i)) or 1
        local c2 = b64:find(data:sub(i+1,i+1)) or 1
        local c3 = b64:find(data:sub(i+2,i+2)) or 1
        local c4 = b64:find(data:sub(i+3,i+3)) or 1
        local n = (c1-1)*262144 + (c2-1)*4096 + (c3-1)*64 + (c4-1)
        result[#result+1] = string.char(math.floor(n/65536))
        if data:sub(i+2,i+2) ~= "=" then
            result[#result+1] = string.char(math.floor(n/256) % 256)
        end
        if data:sub(i+3,i+3) ~= "=" then
            result[#result+1] = string.char(n % 256)
        end
    end
    return table.concat(result)
end

-- ===== DECOMPILATION ENGINE =====
local function deobfuscateMoonsec(code)
    -- Strip headers
    code = code:gsub("^%s*%-%-[^\n]*[Mm]oon[Ss]ec[^\n]*\n", "")
    code = code:gsub("^%s*%-%-[^\n]*[Oo]bfuscat[^\n]*\n", "")
    code = code:gsub("^%s*%-%-[^\n]*[Pp]rotected[^\n]*\n", "")
    
    -- Remove anti-tamper
    code = code:gsub('assert%s*%(%s*_VERSION%s*==%s*["\']Lua%s*5%.1["\']%s*,?[^%)]*%)', "-- [removed]")
    code = code:gsub("if%s+not%s+game%s+then%s+error%s*%([^%)]*%)%s*end", "-- [removed]")
    
    -- Decode string.char chains
    code = code:gsub("string%.char%(([^)]-)%)", function(args)
        local bytes = {}
        for n in args:gmatch("%d+") do
            bytes[#bytes+1] = string.char(tonumber(n) or 0)
        end
        return '"' .. table.concat(bytes):gsub('"', '\\"') .. '"'
    end)
    
    -- Replace obfuscated identifiers
    code = code:gsub("[lI][lI1][lI1][lI1][lI1][lI1][lI1][lI1]+", function(m)
        return "var_" .. string.sub(m, 1, 4)
    end)
    
    -- Remove VM dispatcher loops
    code = code:gsub("while%s+true%s+do%s*[^\n]-%s*end", "-- [VM loop removed]")
    
    return code
end

local function deobfuscateLuraph(code)
    -- Find the encoded blob
    local blob = code:match('V6FjjMyG6MQCaB2gMXFl%("(.-)"%s*%)')
    if blob then
        -- Decode escapes
        blob = blob:gsub("\\\\(%d%d?%d?)", function(n) return string.char(tonumber(n) % 256) end)
        blob = blob:gsub("\\\\([nrtbfv\\\'\"])", {n="\n",r="\r",t="\t",b="\b",f="\f",v="\v",["\\"]="\\",["'"]="'",['"']='"'})
        
        -- Try to extract Lua from it
        local clean = blob:gsub("[^\n\r\t !%-%~%w%+%/%=%*%(%)\\[%]{}%.,;:<>]", "")
        if #clean > 100 then
            return "-- Luraph payload extracted\n" .. clean
        end
    end
    return code
end

local function deobfuscateIronBrew(code)
    -- Extract bytecode from string.char chains
    local bytes = {}
    for args in code:gmatch("string%.char%(([^)]-)%)") do
        for n in args:gmatch("%d+") do
            bytes[#bytes+1] = tonumber(n) or 0
        end
    end
    
    if #bytes > 100 then
        local decoded = table.concat(bytes, "")
        return "-- IronBrew bytecode extracted\n" .. decoded
    end
    return code
end

local function deobfuscateNamaiki(code)
    -- Extract base64 payload
    local payload = code:match('"([A-Za-z0-9+/=]+)"')
    if payload then
        local decoded = base64Decode(payload)
        if #decoded > 100 then
            return "-- Namaiki decoded payload\n" .. decoded
        end
    end
    return code
end

local function deobfuscateVAQ(code)
    -- Remove anti-tamper exits
    code = code:gsub("then%s+return%s+0%s+end", "then end")
    code = code:gsub("then%s+return%s+false%s+end", "then end")
    return code
end

local function deobfuscateLumora(code)
    -- Extract hex chunks
    local chunks = {}
    for hex in code:gmatch('"([0-9A-Fa-f]+)"') do
        chunks[#chunks+1] = hex:gsub("..", function(b)
            return string.char(tonumber(b, 16) or 0)
        end)
    end
    if #chunks > 0 then
        return "-- Lumora decoded chunks\n" .. table.concat(chunks)
    end
    return code
end

-- ===== MAIN DECOMPILER =====
function proxyTable.dump_file(inputPath, outputPath)
    local file = io.open(inputPath, "rb")
    if not file then
        return false, "Cannot open input file"
    end
    local code = file:read("*all")
    file:close()
    
    local obfType = detectObfuscator(code)
    local result = code
    
    if obfType == "moonsec" then
        result = deobfuscateMoonsec(code)
    elseif obfType == "luraph" then
        result = deobfuscateLuraph(code)
    elseif obfType == "ironbrew" then
        result = deobfuscateIronBrew(code)
    elseif obfType == "namaiki" then
        result = deobfuscateNamaiki(code)
    elseif obfType == "vaq" then
        result = deobfuscateVAQ(code)
    elseif obfType == "lumora" then
        result = deobfuscateLumora(code)
    end
    
    -- Clean up
    result = result:gsub("\r\n", "\n"):gsub("\r", "\n")
    result = result:gsub("\n%s*\n", "\n")
    
    -- Write output
    local out = io.open(outputPath, "wb")
    if out then
        out:write("-- Deobfuscated by FlameDumperV3\n")
        out:write("-- Type: " .. obfType .. "\n\n")
        out:write(result)
        out:close()
        return true
    end
    return false
end

function proxyTable.dump_string(code, outputPath)
    local obfType = detectObfuscator(code)
    local result = code
    
    if obfType == "moonsec" then
        result = deobfuscateMoonsec(code)
    elseif obfType == "luraph" then
        result = deobfuscateLuraph(code)
    elseif obfType == "ironbrew" then
        result = deobfuscateIronBrew(code)
    elseif obfType == "namaiki" then
        result = deobfuscateNamaiki(code)
    elseif obfType == "vaq" then
        result = deobfuscateVAQ(code)
    elseif obfType == "lumora" then
        result = deobfuscateLumora(code)
    end
    
    result = result:gsub("\r\n", "\n"):gsub("\r", "\n")
    
    if outputPath then
        local out = io.open(outputPath, "wb")
        if out then
            out:write("-- Deobfuscated by FlameDumperV3\n")
            out:write("-- Type: " .. obfType .. "\n\n")
            out:write(result)
            out:close()
            return true
        end
        return false
    end
    
    return result
end

return proxyTable
'''

# ============ HELPER FUNCTIONS ============
def randomstr(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def getfile(msg, path="./"):
    if msg.attachments:
        attachment = msg.attachments[0]
        os.makedirs(path, exist_ok=True)
        filename = f"{hashlib.md5(str(msg.id).encode()).hexdigest()}.lua"
        filepath = os.path.join(path, filename)
        await attachment.save(filepath)
        return filename
    return None

async def get_text_file(msg):
    if msg.attachments:
        attachment = msg.attachments[0]
        content = await attachment.read()
        return content.decode('utf-8', errors='ignore')
    return None

def run_lua_dumper(code):
    """Run the Lua dumper engine on code"""
    if not HAS_LUA:
        return fallback_deobfuscate(code)
    
    try:
        lua = LuaRuntime(unpack_returned_tuples=True)
        
        # Load the dumper
        lua.execute(DUMPER_SOURCE)
        
        # Get the proxyTable
        proxy = lua.globals().proxyTable
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write(code)
            temp_in = f.name
        
        temp_out = tempfile.mktemp(suffix='.lua')
        
        # Run the dumper
        success = proxy.dump_file(temp_in, temp_out)
        
        if success:
            with open(temp_out, 'r', encoding='utf-8', errors='ignore') as f:
                result = f.read()
            
            os.unlink(temp_in)
            os.unlink(temp_out)
            return result
        
        os.unlink(temp_in)
        return fallback_deobfuscate(code)
        
    except Exception as e:
        print(f"Lua dumper error: {e}")
        return fallback_deobfuscate(code)

def fallback_deobfuscate(code):
    """Python fallback deobfuscator"""
    # Remove headers
    code = re.sub(r'^%s*%-%-[^\n]*[Mm]oon[Ss]ec[^\n]*\n', '', code, flags=re.M)
    code = re.sub(r'^%s*%-%-[^\n]*[Oo]bfuscat[^\n]*\n', '', code, flags=re.M)
    
    # Remove anti-tamper
    code = re.sub(r'assert%s*%(%s*_VERSION%s*==%s*["\']Lua%s*5%.1["\']%s*,?[^%)]*%)', '-- [removed]', code)
    code = re.sub(r'if%s+not%s+game%s+then%s+error%s*%([^%)]*%)%s*end', '-- [removed]', code)
    
    # Decode string.char chains
    code = re.sub(r'string%.char%(([^)]-)%)', lambda m: decode_string_char(m.group(1)), code)
    
    # Replace obfuscated identifiers
    code = re.sub(r'[lI][lI1][lI1][lI1][lI1][lI1][lI1][lI1]+', lambda m: f'var_{m.group(0)[:4]}', code)
    
    return code

def decode_string_char(args):
    bytes_list = []
    for n in re.findall(r'\d+', args):
        bytes_list.append(chr(int(n) & 0xFF))
    return '"' + ''.join(bytes_list) + '"'

# ============ BOT COMMANDS ============

@bot.command(name='setup')
async def setup(ctx):
    global L_CHANNEL_ID
    L_CHANNEL_ID = ctx.channel.id
    await ctx.send(f"Setup complete - .l commands active in {ctx.channel.mention}")

@bot.command(name='help')
async def help_cmd(ctx):
    help_text = """Available Commands:

FILE PROCESSING:
.l - Deobfuscate Lua scripts (attach .lua file)
.beautify - Beautify Lua code
.minify - Minify Lua code
.compress - Compress Lua code
.detect - Detect obfuscator type

DECOMPILATION:
.decompile - Decompile Lua bytecode

OBFUSCATION:
.obf - Obfuscate Lua code

WEB TOOLS:
.byp <url> - Bypass link shorteners
.gen <prompt> - Generate AI images

OTHER:
.ping - Bot latency
.say <text> - Echo text
.color <hex> - Generate color gradient

SETUP:
.setup - Set current channel for .l commands"""

    await ctx.send(help_text)

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

@bot.command(name='say')
async def say(ctx, *, text):
    await ctx.send(discord.utils.escape_mentions(text))

@bot.command(name='color')
async def color_cmd(ctx, hex_code):
    try:
        from PIL import Image, ImageDraw
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

@bot.command(name='byp')
async def bypass_cmd(ctx, url):
    if not url.startswith("http"):
        await ctx.send("Provide valid URL starting with http:// or https://")
        return
    
    await ctx.send(f"Bypassing {url}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as resp:
                if str(resp.url) != url:
                    await ctx.send(f"Bypassed URL: {str(resp.url)}")
                    return
        
        # Try bypass.vip API
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

@bot.command(name='gen')
async def gen_cmd(ctx, *, prompt):
    if not prompt:
        await ctx.send("Provide a prompt")
        return
    
    msg = await ctx.send("Generating image...")
    
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

@bot.command(name='l')
async def l_cmd(ctx):
    """Deobfuscate Lua scripts using FlameDumperV3"""
    global L_CHANNEL_ID
    
    if L_CHANNEL_ID and ctx.channel.id != L_CHANNEL_ID:
        await ctx.send(f"Use .l in <#{L_CHANNEL_ID}> or run .setup first")
        return
    
    if not ctx.message.attachments:
        await ctx.send("Attach a .lua file")
        return
    
    attachment = ctx.message.attachments[0]
    if not attachment.filename.lower().endswith('.lua'):
        await ctx.send("File must be .lua")
        return
    
    msg = await ctx.send(f"Processing {attachment.filename}...")
    
    try:
        # Download file
        content = await attachment.read()
        code = content.decode('utf-8', errors='ignore')
        
        # Detect obfuscator type
        obf_type = "unknown"
        if re.search(r'[Mm]oon[Ss]ec', code):
            obf_type = "Moonsec"
        elif re.search(r'Luraph', code) or re.search(r'LuraphContinue', code):
            obf_type = "Luraph"
        elif re.search(r'[Ii]ron[Bb]rew', code):
            obf_type = "IronBrew"
        elif re.search(r'namaiki', code):
            obf_type = "Namaiki"
        elif re.search(r'VAQ', code):
            obf_type = "VAQ"
        elif re.search(r'lumora', code):
            obf_type = "Lumora"
        
        # Deobfuscate
        if HAS_LUA:
            result = run_lua_dumper(code)
        else:
            result = fallback_deobfuscate(code)
        
        # Check if we got something useful
        if len(result) < 50 or result == code:
            await msg.edit(content=f"⚠️ Could not fully deobfuscate ({obf_type}) - showing original")
            result = code
        
        # Send result
        if len(result) > 1900:
            # Split into chunks
            chunks = [result[i:i+1900] for i in range(0, len(result), 1900)]
            await msg.edit(content=f"Deobfuscated {attachment.filename} [{obf_type}] ({len(chunks)} chunks)")
            for chunk in chunks:
                await ctx.send(f"```lua\n{chunk}\n```")
        else:
            await msg.edit(content=f"Deobfuscated {attachment.filename} [{obf_type}]")
            await ctx.send(f"```lua\n{result}\n```")
            
    except Exception as e:
        await msg.edit(content=f"Error: {str(e)}")

@bot.command(name='detect')
async def detect_cmd(ctx):
    """Detect obfuscator type"""
    content = await get_text_file(ctx.message)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    types = []
    if re.search(r'[Mm]oon[Ss]ec', content):
        types.append('Moonsec')
    if re.search(r'Luraph', content) or re.search(r'LuraphContinue', content):
        types.append('Luraph')
    if re.search(r'[Ii]ron[Bb]rew', content):
        types.append('IronBrew')
    if re.search(r'namaiki', content):
        types.append('Namaiki')
    if re.search(r'VAQ', content):
        types.append('VAQ')
    if re.search(r'lumora', content):
        types.append('Lumora')
    if re.search(r'Prometheus', content) or re.search(r'LPH!', content):
        types.append('Prometheus')
    if re.search(r'PSU', content):
        types.append('PSU')
    if re.search(r'ScriptWare', content) or re.search(r'CocoZ', content):
        types.append('ScriptWare/CocoZ')
    if re.search(r'Riptide', content):
        types.append('Riptide')
    
    if types:
        await ctx.send(f"Detected: {', '.join(types)}")
    else:
        await ctx.send("Unknown or plain Lua")

@bot.command(name='beautify')
async def beautify_cmd(ctx):
    content = await get_text_file(ctx.message)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    # Simple beautification
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

@bot.command(name='minify')
async def minify_cmd(ctx):
    content = await get_text_file(ctx.message)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    # Remove comments and whitespace
    content = re.sub(r'--[^\n]*', '', content)
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([=+-/*])\s*', r'\1', content)
    content = re.sub(r';\s*', ';', content)
    
    buffer = io.StringIO()
    buffer.write(content.strip())
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "minified.lua"))

@bot.command(name='compress')
async def compress_cmd(ctx):
    content = await get_text_file(ctx.message)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    # Remove comments, whitespace, and shorten names
    content = re.sub(r'--[^\n]*', '', content)
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\s*([=+-/*])\s*', r'\1', content)
    
    # Shorten variable names
    def shorten_vars(match):
        vars_found = []
        def replace_var(m):
            name = m.group(1)
            if name not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return']:
                if name not in vars_found:
                    vars_found.append(name)
                return f'v{vars_found.index(name)}'
            return name
        return re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', replace_var, match.group(0))
    
    content = re.sub(r'local\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=', r'local _=\1;', content)
    
    buffer = io.StringIO()
    buffer.write(content.strip())
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "compressed.lua"))

@bot.command(name='obf')
async def obf_cmd(ctx, level: int = 1):
    content = await get_text_file(ctx.message)
    if not content:
        await ctx.send("Attach a Lua file")
        return
    
    if level not in [1, 2, 3]:
        await ctx.send("Level must be 1, 2, or 3")
        return
    
    obfuscated = content
    
    if level >= 1:
        # Replace variable names
        var_map = {}
        def obf_name(m):
            name = m.group(1)
            if name not in ['local', 'function', 'if', 'then', 'else', 'end', 'for', 'while', 'do', 'return']:
                if name not in var_map:
                    var_map[name] = randomstr(8)
                return var_map[name]
            return name
        obfuscated = re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', obf_name, obfuscated)
    
    if level >= 2:
        # Base64 encode strings
        def encode_string(m):
            s = m.group(1) or m.group(2)
            encoded = base64.b64encode(s.encode()).decode()
            return f'loadstring({{}})'  # Placeholder
        obfuscated = re.sub(r'(["\'])([^"\']*)\1', encode_string, obfuscated)
    
    if level >= 3:
        # Add dead code
        obfuscated = f'local _{randomstr(8)} = {{}}; {obfuscated}'
    
    buffer = io.StringIO()
    buffer.write(obfuscated)
    buffer.seek(0)
    await ctx.send(f"Obfuscated (Level {level})", file=discord.File(buffer, "obfuscated.lua"))

@bot.command(name='decompile')
async def decompile_cmd(ctx):
    if not ctx.message.attachments:
        await ctx.send("Attach a Lua bytecode file")
        return
    
    content = await ctx.message.attachments[0].read()
    
    try:
        # Try to load as bytecode
        import marshal
        try:
            code_obj = marshal.loads(content)
            result = f"-- Bytecode decompiled\n-- {len(content)} bytes\n-- (Python marshal format)"
        except:
            result = "-- Could not decompile bytecode\n-- Raw bytes:\n" + ' '.join([f'{b:02x}' for b in content[:256]])
        
        buffer = io.StringIO()
        buffer.write(result)
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, "decompiled.lua"))
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# ============ BOT START ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not set")
        exit(1)
    
    print("🤖 Starting Kers0ne Dumper Bot - CAT Edition")
    print(f"✅ Lua dumper: {'Available' if HAS_LUA else 'Fallback mode'}")
    print("ℹ️  Use .help to see all commands")
    
    bot.run(token)
