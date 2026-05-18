import os
import json
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
from datetime import datetime
import pytz

# ======================
# TOKEN CHECK (สำคัญมาก)
# ======================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ TOKEN ไม่ถูกตั้งค่าใน Render")
    exit()

# ======================
# CONFIG
# ======================

LEAVE_CHANNEL_NAME = "ลา"
SUMMARY_CHANNEL_NAME = "สรุปลา"
THAI_TZ = pytz.timezone("Asia/Bangkok")

DATA_FILE = "leave_data.json"
STATE_FILE = "state.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

leave_data = {"20:00": [], "22:00": []}
message_id = None

# ======================
# LOAD / SAVE SAFE
# ======================

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(leave_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("save_data error:", e)

def load_data():
    global leave_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            leave_data = json.load(f)
    except:
        leave_data = {"20:00": [], "22:00": []}
        save_data()

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"message_id": message_id}, f)
    except:
        pass

def load_state():
    global message_id
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            message_id = json.load(f).get("message_id")
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
        return "\n".join([f"• <@{u}>" for u in lst]) if lst else "ไม่มี"

    embed = discord.Embed(
        title="📅 ระบบเช็คชื่อลา",
        color=discord.Color.blue()
    )

    embed.add_field(name="📆 วันที่", value=now.strftime("%d/%m/%Y"), inline=False)
    embed.add_field(name="🌙 20:00", value=fmt(leave_data["20:00"]), inline=False)
    embed.add_field(name="🌌 22:00", value=fmt(leave_data["22:00"]), inline=False)

    embed.set_footer(text="ใช้งาน 18:00 - 00:00")

    return embed

# ======================
# BUTTONS
# ======================

class LeaveView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="20:00", style=discord.ButtonStyle.primary)
    async def t20(self, i: discord.Interaction, b: Button):

        if not is_active_time():
            return await i.response.send_message("⛔ ยังไม่ถึงเวลา", ephemeral=True)

        uid = str(i.user.id)

        if uid in leave_data["22:00"]:
            leave_data["22:00"].remove(uid)

        if uid not in leave_data["20:00"]:
            leave_data["20:00"].append(uid)

        save_data()
        await update_message(i.guild)

        await i.response.send_message("✅ เลือก 20:00 แล้ว", ephemeral=True)

    @discord.ui.button(label="22:00", style=discord.ButtonStyle.success)
    async def t22(self, i: discord.Interaction, b: Button):

        if not is_active_time():
            return await i.response.send_message("⛔ ยังไม่ถึงเวลา", ephemeral=True)

        uid = str(i.user.id)

        if uid in leave_data["20:00"]:
            leave_data["20:00"].remove(uid)

        if uid not in leave_data["22:00"]:
            leave_data["22:00"].append(uid)

        save_data()
        await update_message(i.guild)

        await i.response.send_message("✅ เลือก 22:00 แล้ว", ephemeral=True)

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

    try:
        msg = await channel.send(embed=build_embed(), view=LeaveView())
        message_id = msg.id
        save_state()
    except Exception as e:
        print("update_message error:", e)

# ======================
# LOOP (NO CRASH ZONE)
# ======================

@tasks.loop(minutes=1)
async def time_loop():

    now = datetime.now(THAI_TZ)

    # 🔴 00:00 reset + stop safe
    if now.hour == 0 and now.minute == 0:
        leave_data["20:00"] = []
        leave_data["22:00"] = []
        save_data()

    # ❌ ไม่ shutdown ทันที (กัน exit early)

# ======================
# SUMMARY
# ======================

@tasks.loop(minutes=1)
async def summary_loop():

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
# READY
# ======================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    load_data()
    load_state()

    time_loop.start()
    summary_loop.start()

    for guild in bot.guilds:
        await update_message(guild)

# ======================
# START
# ======================

bot.run(TOKEN)
