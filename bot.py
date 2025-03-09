from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# Flask server to keep Replit awake
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

# Check if user has "Event Host" role
def is_event_host(interaction):
    return any(role.name == "Event Host" for role in interaction.user.roles)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()

# Register a simple slash command (hello)
@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello, World!")

# Register setlogchannel slash command
@bot.tree.command(name="setlogchannel")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    await interaction.response.send_message(f'Log channel set to {channel.mention}')

# Register /givehost slash command to assign "Event Host" role
@bot.tree.command(name="givehost")
async def givehost(interaction: discord.Interaction, member: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name="Event Host")
    if role not in member.roles:
        await member.add_roles(role)
        await interaction.response.send_message(f"{member.mention} has been given the Event Host role!")
    else:
        await interaction.response.send_message(f"{member.mention} already has the Event Host role!")

# Register log slash command
@bot.tree.command(name="log")
async def log(
    interaction: discord.Interaction,
    host: discord.Member,
    co: discord.Member,
    attendees: str,
    multiplier: int = 1
):
    # Check if user is Event Host
    if not is_event_host(interaction):  # Check if user has Event Host role
        await interaction.response.send_message("You don't have the required Event Host role to log events.")
        return

    if log_channel_id is None:
        await interaction.response.send_message("Please set the log channel first using /setlogchannel")
        return

    log_channel = bot.get_channel(log_channel_id)

    if not log_channel:
        await interaction.response.send_message("Invalid log channel. Please reset it.")
        return

    # Convert the attendees string to a list of members
    attendee_mentions = attendees.split()
    attendee_members = []

    for mention in attendee_mentions:
        if mention.startswith("<@") and mention.endswith(">"):  # If it's a mention
            member_id = int(mention[2:-1])
            member = interaction.guild.get_member(member_id)
        else:  
            try:
                member_id = int(mention)
                member = interaction.guild.get_member(member_id)
            except ValueError:
                member = None

        if member:
            attendee_members.append(member)

    # Points system: Create roles and assign them
    all_participants = [host, co] + attendee_members
    for user in all_participants:
        points_data.setdefault(str(user.id), 0)
        points_data[str(user.id)] += multiplier

        # Create or assign points role
        points = points_data[str(user.id)]
        role_name = f"{points}p"

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role is None:
            role = await interaction.guild.create_role(name=role_name)

        if role not in user.roles:
            await user.add_roles(role)

    save_data(points_data)

    log_message = f"Host: {host.mention}\nCo: {co.mention}\nAttendees: {' '.join(a.mention for a in attendee_members)}"
    await log_channel.send(log_message)

    await interaction.response.send_message("Event logged successfully!")

# ✅ Keep the bot online
keep_alive()
bot.run(TOKEN)
