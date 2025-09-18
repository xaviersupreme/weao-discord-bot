# --- THE FIX: This must be the very first thing the program does ---
import eventlet
eventlet.monkey_patch()
# ------------------------------------------------------------------

import discord
from discord.ext import tasks
import os
from flask import Flask, render_template
from flask_socketio import SocketIO
from threading import Thread
from datetime import datetime, timezone
import subprocess
import json
from collections import deque
import logging

# --- PROFESSIONAL LOGGING & WEB SERVER SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask('')
socketio = SocketIO(app, async_mode='threading')
log_messages = deque(maxlen=50)

def log_and_emit(message):
    logging.info(message)
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    full_message = f"[{timestamp}] {message}"
    log_messages.append(full_message)
    socketio.emit('new_log', {'data': full_message})

# --- WEB ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    log_and_emit("--> [Web Console] A user connected to the status page.")
    socketio.emit('history', {'logs': list(log_messages)})

# --- CONFIGURATION ---
TOKEN = os.environ['TOKEN']
CHANNEL_ID = int(os.environ['CHANNEL_ID'])
BOT_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

# --- BOT CODE ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
previous_statuses = {}

def get_executor_statuses():
    log_and_emit("--> [API Fetch] Attempting to pull data from WEAO API...")
    url = "https://weao.xyz/api/status/exploits"
    command = ['curl', '--silent', '--connect-timeout', '10', '-A', "WEAO-3PService", url]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        log_and_emit("--> [API Fetch] Success! Data received.")
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
        log_and_emit(f"--> [API Fetch] FAILED. An error occurred: {e}")
        return None

@client.event
async def on_ready():
    log_and_emit(f'{client.user} has connected to Discord!')
    check_executor_status.start()

@tasks.loop(seconds=120)
async def check_executor_status():
    await client.wait_until_ready()
    global previous_statuses
    log_and_emit("Checking executor statuses...")
    data = get_executor_statuses()
    if data and isinstance(data, list):
        current_statuses = {item.get('title'): item for item in data if 'title' in item}
        if not previous_statuses:
            previous_statuses = current_statuses
            log_and_emit("Initial status check complete. Will notify on future changes.")
            return
        for name, current_data in current_statuses.items():
            last_data = previous_statuses.get(name)
            if last_data and last_data.get('updateStatus') is False and current_data.get('updateStatus') is True:
                channel = client.get_channel(CHANNEL_ID)
                if channel and isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(title=f"✅ {name} is Back Online!", description="This executor OR external has just been updated.", color=discord.Color.brand_green(), timestamp=datetime.now(timezone.utc))
                    embed.set_author(name="Bot Status", url=BOT_URL, icon_url="https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f7e2.png")
                    if client.user and client.user.avatar:
                        embed.set_footer(text=f"WEAO Status Bot • {current_data.get('updatedDate', 'N/A')}", icon_url=client.user.avatar.url)
                    detected_status = "Yes ;(" if current_data.get('detected') else "No :3"
                    embed.add_field(name="Detected by Hyperion?", value=detected_status, inline=True)
                    embed.add_field(name="Roblox Version", value=f"`{current_data.get('rbxversion', 'N/A')}`", inline=True)
                    embed.add_field(name="⠀", value="⠀", inline=True)
                    price_info = "Free" if current_data.get('free') else f"`{current_data.get('cost', 'Paid')}`"
                    key_system = "Yes" if current_data.get('keysystem') else "No"
                    embed.add_field(name="Price", value=price_info, inline=True)
                    embed.add_field(name="Key System?", value=key_system, inline=True)
                    embed.add_field(name="Version", value=f"`{current_data.get('version', 'N/A')}`", inline=True)
                    links = []
                    if website := current_data.get('websitelink'): links.append(f"**[Official Website]({website})**")
                    if discord_link := current_data.get('discordlink'): links.append(f"**[Discord Server]({discord_link})**")
                    if purchase_link := current_data.get('purchaselink'): links.append(f"**[Purchase Here]({purchase_link})**")
                    if links: embed.add_field(name="🔗 Quick Links", value=" | ".join(links), inline=False)
                    embed.add_field(name="Bot Status", value=f"**[Click here to view the live status page.]({BOT_URL})**", inline=False)
                    try:
                        allowed_mentions = discord.AllowedMentions(everyone=True)
                        await channel.send(content="@everyone", embed=embed, allowed_mentions=allowed_mentions)
                        log_and_emit(f"Sent polished embed notification for {name}.")
                    except discord.Forbidden:
                        log_and_emit(f"Error: Missing permissions in channel {CHANNEL_ID}.")
                    except Exception as e:
                        log_and_emit(f"An unexpected error occurred: {e}")
                else:
                    log_and_emit(f"Error: Channel {CHANNEL_ID} not found or not a text channel.")
        previous_statuses = current_statuses

# --- STARTUP ---
def run_bot():
    client.run(TOKEN)

bot_thread = Thread(target=run_bot)
bot_thread.start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
