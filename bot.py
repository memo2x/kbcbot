import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# Flask server to keep Replit awake (If you're using it)
from flask import Flask
from threading import Thread

# Flask server to keep the bot alive on Replit
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    server = Thread(target=run_flask)
    server.start()

# Load token from .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Load or create points data
def load_data():
    if not os.path.exists("points.json"):
        with open("points.json", "w") as f:
            json.dump({}, f)
    with open("points.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("points.json", "w") as f:
        json.dump(data, f, indent=4)

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

log_channel_id = None
points_channel_id = None
points_data = load_data()

# Check if the user has administrator permissions
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

# Command to give the Event Host role (only for admins)
@bot.tree.command(name="givehost")
async def give_host(interaction: discord.Interaction, member: discord.Member):
    # Only allow administrators to give the Event Host role
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command. Only administrators can use it.", ephemeral=True)
        return

    # Get the Event Host role
    event_host_role = discord.utils.get(interaction.guild.roles, name="Event Host")

    if event_host_role:
        await member.add_roles(event_host_role)
        await interaction.response.send_message(f"Successfully gave {member.mention} the Event Host role.")
    else:
        await interaction.response.send_message("The 'Event Host' role doesn't exist.", ephemeral=True)

# Register the slash command to log the event
@bot.tree.command(name="log")
async def log(
    interaction: discord.Interaction,
    host: discord.Member,
    co: discord.Member,
    attendees: str,
    multiplier: int = 1,
):
    if log_channel_id is None:
        await interaction.response.send_message("Please set the log channel first using /setlogchannel")
        return

    log_channel = bot.get_channel(log_channel_id)
    if not log_channel:
        await interaction.response.send_message("Log channel not found. Please set it again.")
        return

    # Convert the attendees string to a list of members
    attendee_mentions = attendees.split()
    attendee_members = []

    for mention in attendee_mentions:
        if mention.startswith("<@") and mention.endswith(">"):  # If it's a mention
            member_id = int(mention[2:-1])
            member = interaction.guild.get_member(member_id)
        else:  # Try to handle user ID
            try:
                member_id = int(mention)
                member = interaction.guild.get_member(member_id)
            except ValueError:
                member = None

        if member:
            attendee_members.append(member)

    # Points system: apply multiplier to points
    all_participants = [host, co] + attendee_members
    for user in all_participants:
        points_data.setdefault(str(user.id), 0)
        points_data[str(user.id)] += multiplier

    save_data(points_data)

    # Log message
    log_message = f"Host: {host.mention}\nCo: {co.mention}\nAttendees: {' '.join(a.mention for a in attendee_members)}\nMultiplier: x{multiplier}"
    await log_channel.send(log_message)

    await interaction.response.send_message("Event logged successfully!")

# Register the slash command to set the log channel
@bot.tree.command(name="setlogchannel")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    await interaction.response.send_message(f"Log channel set to {channel.mention}")

# ✅ Keep the bot alive
keep_alive()

bot.run(TOKEN)
