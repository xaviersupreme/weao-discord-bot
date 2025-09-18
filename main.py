import discord
from discord.ext import tasks
import os
from flask import Flask, render_template
from threading import Thread
from datetime import datetime, timezone
import subprocess
import json

# --- WEB SERVER FOR UPTIME ROBOT ---
app = Flask('')

@app.route('/')
def home():
    return render_template('index.html')

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
TOKEN = os.environ['TOKEN']
CHANNEL_ID = int(os.environ['CHANNEL_ID'])
BOT_URL = os.environ['REPLIT_URL']

intents = discord.Intents.default()
client = discord.Client(intents=intents)

previous_statuses = {}

def get_executor_statuses():
    """Fetches statuses by running the 'curl' command."""

    print("--> [API Fetch] Attempting to pull data from WEAO API...")
    
    url = "https://weao.xyz/api/status/exploits"
    command = ['curl', '--silent', '--connect-timeout', '10', '-A', "WEAO-3PService", url]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        print("--> [API Fetch] Success! Data received.")
        
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
        print(f"--> [API Fetch] FAILED. An error occurred: {e}")
        return None

@client.event
async def on_ready():
    """This function runs when the bot has successfully connected to Discord."""
    # This test line will trigger a notification on startup
    previous_statuses["Matcha"] = {'updateStatus': False}
    print(f'{client.user} has connected to Discord!')
    check_executor_status.start()

@tasks.loop(seconds=120)
async def check_executor_status():
    """The main loop that checks for status changes."""
    await client.wait_until_ready()
    global previous_statuses
    print("Checking executor statuses...")
    data = get_executor_statuses()

    if data and isinstance(data, list):
        current_statuses = {item.get('title'): item for item in data if 'title' in item}

        if not previous_statuses:
            previous_statuses = current_statuses
            print("Initial status check complete. Will notify on future changes.")
            return

        for name, current_data in current_statuses.items():
            last_data = previous_statuses.get(name)

            if last_data and last_data.get('updateStatus') is False and current_data.get('updateStatus') is True:
                channel = client.get_channel(CHANNEL_ID)

                if channel and isinstance(channel, discord.TextChannel):

                    embed = discord.Embed(
                        title=f"✅ {name} is Back Online!",
                        description="This executor OR external has just been updated.",
                        color=discord.Color.brand_green(),
                        timestamp=datetime.now(timezone.utc)
                    )


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
                    if website := current_data.get('websitelink'):
                        links.append(f"**[Official Website]({website})**")
                    if discord_link := current_data.get('discordlink'):
                        links.append(f"**[Discord Server]({discord_link})**")
                    if purchase_link := current_data.get('purchaselink'):
                        links.append(f"**[Purchase Here]({purchase_link})**")

                    if links:
                        embed.add_field(name="🔗 Quick Links", value=" | ".join(links), inline=False)

                    embed.add_field(
                        name="Bot Status",
                        value=f"**[Click here to view the live status page.]({BOT_URL})**",
                        inline=False
                    )


                    try:
                        allowed_mentions = discord.AllowedMentions(everyone=True)
                        await channel.send(
                            content="@everyone", 
                            embed=embed, 
                            allowed_mentions=allowed_mentions
                        )
                        print(f"Sent polished embed notification for {name}.")
                    except discord.Forbidden:
                        print(f"Error: Missing permissions in channel {CHANNEL_ID}.")
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")
                else:
                    print(f"Error: Channel {CHANNEL_ID} not found or not a text channel.")

        previous_statuses = current_statuses

keep_alive()
client.run(TOKEN)
