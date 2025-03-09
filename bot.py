import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from dotenv import load_dotenv

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

# Check if user has the Event Host role
def is_event_host(ctx):
    return any(role.name == "Event Host" for role in ctx.author.roles)

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

# Register log slash command (Only Event Hosts can use)
@bot.tree.command(name="log")
async def log(
    interaction: discord.Interaction,
    host: discord.Member,
    co: discord.Member,
    attendees: str,
    multiplier: int = 1,  # 1, 2, 3, 4, or 5 multiplier
):
    if not is_event_host(interaction):  # Check if user has Event Host role
        await interaction.response.send_message("You do not have permission to log events. Please contact an admin.", ephemeral=True)
        return

    if log_channel_id is None:
        await interaction.response.send_message("Please set the log channel first using /setlogchannel.", ephemeral=True)
        return

    log_channel = bot.get_channel(log_channel_id)

    # Ensure log_channel is valid
    if log_channel is None:
        await interaction.response.send_message("Log channel is invalid or not found.", ephemeral=True)
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

    # Points system: give points based on multiplier
    all_participants = [host, co] + attendee_members
    for user in all_participants:
        # Check and give the appropriate role based on points
        current_points = points_data.get(str(user.id), 0)
        new_points = current_points + multiplier

        points_data[str(user.id)] = new_points
        # Add the role based on new points
        role_name = f"{new_points}p"
        role = discord.utils.get(interaction.guild.roles, name=role_name)

        if not role:
            role = await interaction.guild.create_role(name=role_name)

        await user.add_roles(role)

    save_data(points_data)

    # Log event message in Log Channel
    log_message = f"Host: {host.mention}\nCo: {co.mention}\nAttendees: {' '.join(a.mention for a in attendee_members)}"
    await log_channel.send(log_message)

    await interaction.response.send_message("Event logged and roles updated successfully!")

# Register givehost slash command (assign Event Host role)
@bot.tree.command(name="givehost")
async def givehost(interaction: discord.Interaction, member: discord.Member):
    # Check if the user has permission to assign roles (admin/mod)
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You do not have permission to assign roles.")
        return

    role = discord.utils.get(interaction.guild.roles, name="Event Host")
    if not role:
        # Create the role if it doesn't exist
        role = await interaction.guild.create_role(name="Event Host")

    await member.add_roles(role)
    await interaction.response.send_message(f"{member.mention} has been given the Event Host role.")

# Run the bot
bot.run(TOKEN)
