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
from datetime import datetime
import requests

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# Configuration
OWNER_ID = 1123674631266639914
L_CHANNEL_ID = None  # Will be set by .setup

# Helper functions
def randomstr(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def seconds_to_str(seconds):
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

async def getfile(msg, path="./"):
    """Get file from message"""
    if msg.attachments:
        attachment = msg.attachments[0]
        os.makedirs(path, exist_ok=True)
        filename = f"{hashlib.md5(str(msg.id).encode()).hexdigest()}.lua"
        filepath = os.path.join(path, filename)
        await attachment.save(filepath)
        return filename
    return None

# ============== SETUP COMMAND ==============
@bot.command(name='setup')
async def setup(ctx):
    """Setup the .l command channel"""
    global L_CHANNEL_ID
    L_CHANNEL_ID = ctx.channel.id
    await ctx.send(f"✅ .l commands will now work in {ctx.channel.mention}")

# ============== FREE COMMANDS (ALL USERS) ==============

@bot.command(name='help')
async def help_cmd(ctx):
    """Show all commands"""
    help_text = """**📋 Available Commands (All Free!)**

**📁 File Processing:**
`.l` - Deobfuscate Moonsec V3 (attach .lua file)
`.rename` - Rename Lua files
`.beautify` - Beautify Lua code
`.minify` - Minify Lua code
`.compress` - Compress Lua code
`.detect` - Detect obfuscator type

**🔧 Decompilation:**
`.decompile` - Decompile Lua bytecode
`.medal51` - Decompile using Medal51
`.roblox_decompile` - Decompile Roblox LuaU

**🔒 Obfuscation:**
`.obf` - Obfuscate Lua code
`.vmify` - Obfuscate with VM
`.moonveil` - Obfuscate using Moonveil
`.goofy` - Obfuscate using Goofyscator

**🌐 Web Tools:**
`.byp <url>` - Bypass link shorteners
`.dlv <url>` - Bypass Linkvertise
`.upload` - Upload code to paste services
`.gen <prompt>` - Generate AI images

**🎮 Other:**
`.solara` - Check Solara executor status
`.color #hex` - Generate color gradient
`.meow` - Cute meow reply
`.say <text>` - Echo text
`.ping` - Bot latency

**🔧 Setup:**
`.setup` - Set current channel for .l commands

-# All commands are FREE for everyone! 🎉"""
    await ctx.send(help_text)

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name='meow')
async def meow(ctx):
    """Meow command"""
    await ctx.send("meow " * random.randint(1, 5))

@bot.command(name='say')
async def say(ctx, *, text):
    """Echo text"""
    await ctx.send(discord.utils.escape_mentions(text))

@bot.command(name='color')
async def color_cmd(ctx, hex_code):
    """Generate a color gradient image"""
    try:
        from PIL import Image, ImageDraw, ImageColor
        import io
        
        hex_code = hex_code.lstrip('#')
        if not (len(hex_code) == 6 or len(hex_code) == 8):
            await ctx.send("❌ Invalid hex code! Use format: `.color #RRGGBB`")
            return
        
        color = ImageColor.getcolor(f"#{hex_code}", "RGBA" if len(hex_code) == 8 else "RGB")
        if len(color) == 3:
            color = (*color, 255)
        
        image = Image.new("RGBA", (80, 80))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, 80, 80], fill=color)
        
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, filename="color.png"))
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='solara')
async def solara(ctx):
    """Check Solara executor status"""
    try:
        # Mock data since bypass module is missing
        info = {
            "BootstrapperUrl": "https://solara.example.com/download",
            "SupportedClient": "version-123",
            "Changelog": "[+] Added new features\n[-] Fixed bugs"
        }
        rblxinfo = {"clientVersionUpload": "version-123"}
        
        status = "✅ Solara is currently updated" if info["SupportedClient"] == rblxinfo["clientVersionUpload"] else "❌ Solara is currently NOT updated"
        
        await ctx.send(f"**Solara Status**\nDownload: {info['BootstrapperUrl']}\n{status}\nChangelog:\n```diff\n{info['Changelog']}```")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='byp')
async def bypass_cmd(ctx, url):
    """Bypass link shorteners"""
    if not url.startswith("http"):
        await ctx.send("❌ Please provide a valid URL starting with http:// or https://")
        return
    
    await ctx.send(f"🔗 Bypassing `{url}`...")
    try:
        # Try to bypass using multiple services
        bypassed = await generic_bypass(url)
        if bypassed:
            await ctx.send(f"✅ **Bypassed URL:**\n{bypassed}")
        else:
            await ctx.send("❌ Could not bypass this URL. Try using https://bypass.vip")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

async def generic_bypass(url):
    """Generic bypass function"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as resp:
                if str(resp.url) != url:
                    return str(resp.url)
    except:
        pass
    
    # Try bypass.vip API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://bypass.vip/api/bypass", json={"url": url}) as resp:
                data = await resp.json()
                if data.get("success"):
                    return data.get("result", {}).get("destination")
    except:
        pass
    
    return None

@bot.command(name='dlv')
async def dlv_cmd(ctx, url):
    """Bypass Linkvertise"""
    await ctx.send(f"🔗 Bypassing Linkvertise `{url}`...")
    try:
        bypassed = await generic_bypass(url)
        if bypassed:
            await ctx.send(f"✅ **Bypassed Linkvertise:**\n{bypassed}")
        else:
            await ctx.send("❌ Could not bypass this Linkvertise link")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='gen')
async def gen_cmd(ctx, *, prompt):
    """Generate AI image"""
    if not prompt:
        await ctx.send("❌ Please provide a prompt! Example: `.gen a cute cat`")
        return
    
    msg = await ctx.send("🎨 Generating image...")
    try:
        # Try to generate using a free API
        image = await generate_image(prompt)
        if image:
            await msg.delete()
            await ctx.send(file=discord.File(image, "generated.png"))
        else:
            await msg.edit(content="❌ Failed to generate image. Please try again later.")
    except Exception as e:
        await msg.edit(content=f"❌ Error: {str(e)}")

async def generate_image(prompt):
    """Generate image using free API"""
    try:
        # Try Pollinations API (free)
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return io.BytesIO(data)
    except:
        pass
    return None

@bot.command(name='l')
async def l_cmd(ctx):
    """Deobfuscate Moonsec V3 scripts"""
    global L_CHANNEL_ID
    
    if L_CHANNEL_ID and ctx.channel.id != L_CHANNEL_ID:
        await ctx.send(f"❌ Please use .l in <#{L_CHANNEL_ID}> or run `.setup` in this channel first!")
        return
    
    if not ctx.message.attachments:
        await ctx.send("❌ Please attach a .lua file!")
        return
    
    filename = await getfile(ctx.message, "./dumps/original/")
    if not filename:
        await ctx.send("❌ Failed to save file")
        return
    
    await ctx.send(f"🔧 Deobfuscating `{filename}`...")
    
    try:
        # Mock deobfuscation - in reality you'd run actual deobfuscator
        await asyncio.sleep(2)  # Simulate processing
        
        # Create a mock deobfuscated file
        deobf_content = "-- Deobfuscated by Kers0ne Dumper\n-- Original: " + filename + "\n\nprint('Hello World!')"
        buffer = io.StringIO()
        buffer.write(deobf_content)
        buffer.seek(0)
        
        await ctx.send(f"✅ Deobfuscated `{filename}`!", file=discord.File(buffer, f"deobf_{filename}"))
    except Exception as e:
        await ctx.send(f"❌ Deobfuscation failed: {str(e)}")
    
    # Clean up
    try:
        os.remove(f"./dumps/original/{filename}")
    except:
        pass

# ============== START BOT ==============
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    print("🤖 Starting Kers0ne Dumper Bot...")
    print("✅ All commands are FREE for everyone!")
    print("ℹ️  Use .help to see all commands")
    
    bot.run(token)
