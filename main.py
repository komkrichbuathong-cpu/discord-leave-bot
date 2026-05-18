import os
import json
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from flask import Flask
from threading import Thread
from datetime import datetime
import pytz

# ======================
# Flask keep alive (Render)
# ======================

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ======================
# CONFIG
# ======================

TOKEN = os.getenv("TOKEN")

LEAVE_CHANNEL_NAME = "ลา"
SUMMARY_CHANNEL_NAME = "สรุปลา"

THAI_TZ = pytz.timezone("Asia/Bangkok")

DATA_FILE = "leave_data.json"
STATE_FILE = "state.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

leave_data = {
    "20:00": [],
    "22:00": []
}

message_id = None

# ======================
# LOAD / SAVE DATA
# ======================

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(leave_data, f, ensure_ascii=False, indent=4)

def load_data():
    global leave_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            leave_data = json.load(f)
    except:
        save_data()

def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"message_id": message_id}, f)

def load_state():
    global message_id
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            message_id = data.get("message_id")
    except:
        message_id = None

# ======================
# TIME CONTROL
# ======================

def is_active_time():
    now = datetime.now(THAI_TZ)
    return 18 <= now.hour < 24

# ======================
# EMBED
# ======================

def build_embed():
    now = datetime.now(THAI_TZ)

    def fmt(lst):
        if not lst:
            return "ไม่มี"
        return "\n".join([f"• <@{u}>" for u in lst])

    embed = discord.Embed(
        title="📅 ระบบเช็คชื่อลา",
        description="กดปุ่มเพื่อเลือกเวลา",
        color=discord.Color.blue()
    )

    embed.add_field(name="📆 วันที่", value=now.strftime("%d/%m/%Y"), inline=False)
    embed.add_field(name="⏰ เวลา", value=now.strftime("%H:%M:%S"), inline=False)

    embed.add_field(name="🌙 20:00", value=fmt(leave_data["20:00"]), inline=False)
    embed.add_field(name="🌌 22:00", value=fmt(leave_data["22:00"]), inline=False)

    embed.set_footer(text="ใช้งานได้ 18:00 - 00:00")

    return embed

# ======================
# VIEW (BUTTONS)
# ======================

class LeaveView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # ================= 20:00 =================
    @discord.ui.button(label="20:00", style=discord.ButtonStyle.primary)
    async def leave20(self, interaction: discord.Interaction, button: Button):

        if not is_active_time():
            return await interaction.response.send_message("⛔ ใช้ได้ 18:00–00:00", ephemeral=True)

        uid = str(interaction.user.id)

        if uid in leave_data["22:00"]:
            leave_data["22:00"].remove(uid)

        if uid not in leave_data["20:00"]:
            leave_data["20:00"].append(uid)

        save_data()
        await update_message(interaction.guild)

        await interaction.response.send_message("✅ เลือก 20:00 แล้ว", ephemeral=True)

    # ================= 22:00 =================
    @discord.ui.button(label="22:00", style=discord.ButtonStyle.success)
    async def leave22(self, interaction: discord.Interaction, button: Button):

        if not is_active_time():
            return await interaction.response.send_message("⛔ ใช้ได้ 18:00–00:00", ephemeral=True)

        uid = str(interaction.user.id)

        if uid in leave_data["20:00"]:
            leave_data["20:00"].remove(uid)

        if uid not in leave_data["22:00"]:
            leave_data["22:00"].append(uid)

        save_data()
        await update_message(interaction.guild)

        await interaction.response.send_message("✅ เลือก 22:00 แล้ว", ephemeral=True)

    # ================= CANCEL 20 =================
    @discord.ui.button(label="ยกเลิก 20:00", style=discord.ButtonStyle.danger)
    async def cancel20(self, interaction: discord.Interaction, button: Button):

        uid = str(interaction.user.id)

        if uid in leave_data["20:00"]:
            leave_data["20:00"].remove(uid)
            save_data()
            await update_message(interaction.guild)
            return await interaction.response.send_message("❌ ยกเลิก 20:00 แล้ว", ephemeral=True)

        await interaction.response.send_message("⚠️ ยังไม่ได้เลือก 20:00", ephemeral=True)

    # ================= CANCEL 22 =================
    @discord.ui.button(label="ยกเลิก 22:00", style=discord.ButtonStyle.danger)
    async def cancel22(self, interaction: discord.Interaction, button: Button):

        uid = str(interaction.user.id)

        if uid in leave_data["22:00"]:
            leave_data["22:00"].remove(uid)
            save_data()
            await update_message(interaction.guild)
            return await interaction.response.send_message("❌ ยกเลิก 22:00 แล้ว", ephemeral=True)

        await interaction.response.send_message("⚠️ ยังไม่ได้เลือก 22:00", ephemeral=True)

# ======================
# UPDATE MESSAGE
# ======================

async def update_message(guild):

    global message_id

    channel = discord.utils.get(guild.text_channels, name=LEAVE_CHANNEL_NAME)
    if not channel:
        return

    try:
        if message_id:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=build_embed(), view=LeaveView())
            return
    except:
        pass

    msg = await channel.send(embed=build_embed(), view=LeaveView())
    message_id = msg.id
    save_state()

# ======================
# AUTO RESET
# ======================

@tasks.loop(minutes=1)
async def daily_reset():

    now = datetime.now(THAI_TZ)

    if now.hour == 0 and now.minute == 0:
        leave_data["20:00"] = []
        leave_data["22:00"] = []
        save_data()

        for guild in bot.guilds:
            await update_message(guild)

# ======================
# AUTO SUMMARY
# ======================

@tasks.loop(minutes=1)
async def auto_summary():

    now = datetime.now(THAI_TZ)

    for guild in bot.guilds:

        channel = discord.utils.get(guild.text_channels, name=SUMMARY_CHANNEL_NAME)
        if not channel:
            continue

        if now.hour == 20 and now.minute == 0:
            await channel.send("📢 สรุป 20:00\n\n" +
                ("\n".join([f"• <@{u}>" for u in leave_data["20:00"]]) or "ไม่มี")
            )

        if now.hour == 22 and now.minute == 0:
            await channel.send("📢 สรุป 22:00\n\n" +
                ("\n".join([f"• <@{u}>" for u in leave_data["22:00"]]) or "ไม่มี")
            )

# ======================
# READY EVENT
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    load_data()
    load_state()

    daily_reset.start()
    auto_summary.start()

    for guild in bot.guilds:
        await update_message(guild)

# ======================
# START
# ======================

keep_alive()
bot.run(TOKEN)
