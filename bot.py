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

# Load or create JSON data for log channel and points
def load_data():
    if not os.path.exists("data.json"):
        with open("data.json", "w") as f:
            json.dump({"log_channel_id": None, "points": {}}, f)
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
log_channel_id = data.get("log_channel_id")
points_data = data.get("points", {})

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True  # Make sure the Server Members Intent is enabled
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()

# Simple slash command
@bot.tree.command(name="hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello, World!")

# Set log channel (saved permanently)
@bot.tree.command(name="setlogchannel")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    data["log_channel_id"] = log_channel_id
    save_data(data)
    await interaction.response.send_message(f'Log channel set to {channel.mention} and saved permanently!')

# Function to get or create a role based on points
async def get_or_create_role(guild, points):
    role_name = f"{points}p"
    existing_role = discord.utils.get(guild.roles, name=role_name)
    if existing_role:
        return existing_role
    try:
        new_role = await guild.create_role(name=role_name, reason=f"Created role for {points} points")
        return new_role
    except discord.Forbidden:
        print("Bot does not have permission to create roles!")
        return None

# Function to update a member's point role: removes old point roles and assigns the new one
async def update_roles(member, new_points):
    guild = member.guild
    new_role = await get_or_create_role(guild, new_points)
    if not new_role:
        return
    # Remove roles with names like "Xp" (where X is numeric)
    roles_to_remove = [role for role in member.roles if role.name.endswith("p") and role.name[:-1].isdigit()]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove)
    await member.add_roles(new_role)

# Log command: now includes a multiplier option
@bot.tree.command(name="log")
async def log(
    interaction: discord.Interaction,
    host: discord.Member,
    co: discord.Member,
    attendees: str,  # Attendees as a space-separated string (names, mentions, or IDs)
    multiplier: int  # Multiplier value from 1 to 5
):
    # Defer the response so we have extra processing time
    await interaction.response.defer()

    # Validate multiplier range
    if multiplier < 1 or multiplier > 5:
        await interaction.followup.send("Multiplier must be between 1 and 5.")
        return

    if log_channel_id is None:
        await interaction.followup.send("Please set the log channel first using /setlogchannel.")
        return

    log_channel = bot.get_channel(log_channel_id)
    if not log_channel:
        await interaction.followup.send("Log channel is invalid. Please reset it.")
        return

    # Convert the attendees string into a list of Member objects.
    attendee_names = attendees.split()
    attendee_members = []
    for name in attendee_names:
        member = None
        # If it's a mention like <@!1234567890> or <@1234567890>
        if name.startswith("<@") and name.endswith(">"):
            mention_str = name[2:-1]
            if mention_str.startswith("!"):
                mention_str = mention_str[1:]
            try:
                member_id = int(mention_str)
                member = await interaction.guild.fetch_member(member_id)
            except Exception as e:
                print(f"Could not fetch member {name}: {e}")
                member = None
        else:
            # Try to get by username (case sensitive)
            member = discord.utils.get(interaction.guild.members, name=name)
            if not member:
                try:
                    member_id = int(name)
                    member = await interaction.guild.fetch_member(member_id)
                except Exception as e:
                    print(f"Could not fetch member {name}: {e}")
                    member = None
        if member:
            attendee_members.append(member)

    # Points system: each participant gets points equal to the multiplier.
    all_participants = [host, co] + attendee_members
    for user in all_participants:
        user_id = str(user.id)
        points_data.setdefault(user_id, 0)
        points_data[user_id] += multiplier
        await update_roles(user, points_data[user_id])  # Update the user's role

    data["points"] = points_data
    save_data(data)

    log_message = (
        f"**Host:** {host.mention}\n"
        f"**Co-host:** {co.mention}\n"
        f"**Attendees:** {' '.join(a.mention for a in attendee_members)}\n"
        f"Each participant got {multiplier} point(s)."
    )
    await log_channel.send(log_message)
    await interaction.followup.send("Event logged successfully! Roles updated.")

# Keep the bot online with a Flask server
keep_alive()
bot.run(TOKEN)
