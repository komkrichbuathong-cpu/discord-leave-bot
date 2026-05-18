from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import json
import os
from datetime import datetime
import pytz

# ======================
# ตั้งค่า
# ======================

LEAVE_CHANNEL_NAME = "ลา"
SUMMARY_CHANNEL_NAME = "สรุปลา"
THAI_TZ = pytz.timezone("Asia/Bangkok")

DATA_FILE = "leave_data.json"

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
# โหลด / เซฟข้อมูล
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


# ======================
# เวลาใช้งาน
# ======================

def is_active_time():
    now = datetime.now(THAI_TZ)
    hour = now.hour
    return 18 <= hour < 24


# ======================
# Embed
# ======================

def build_embed():
    now = datetime.now(THAI_TZ)

    twenty_names = "\n".join(
        [f"• {x}" for x in leave_data["20:00"]]
    ) or "ไม่มี"

    twentytwo_names = "\n".join(
        [f"• {x}" for x in leave_data["22:00"]]
    ) or "ไม่มี"

    embed = discord.Embed(
        title="📅 ระบบเช็คชื่อลา",
        description="กดปุ่มด้านล่างเพื่อเลือกเวลาลา",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🗓 วันที่",
        value=now.strftime("%d/%m/%Y"),
        inline=False
    )

    embed.add_field(
        name="🕒 เวลาไทย",
        value=now.strftime("%H:%M:%S"),
        inline=False
    )

    embed.add_field(
        name="🌙 ลาเวลา 20:00",
        value=twenty_names,
        inline=False
    )

    embed.add_field(
        name="🌌 ลาเวลา 22:00",
        value=twentytwo_names,
        inline=False
    )

    embed.set_footer(text="เปิดใช้งาน 18:00 - 00:00")

    return embed


# ======================
# ปุ่ม
# ======================

class LeaveView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="20:00", emoji="🌙", style=discord.ButtonStyle.primary)
    async def leave_20(self, interaction: discord.Interaction, button: Button):

        if not is_active_time():
            await interaction.response.send_message(
                "⛔ ระบบเปิดเฉพาะ 18:00 - 00:00",
                ephemeral=True
            )
            return

        name = interaction.user.display_name

        if name in leave_data["22:00"]:
            leave_data["22:00"].remove(name)

        if name not in leave_data["20:00"]:
            leave_data["20:00"].append(name)

        save_data()

        await update_leave_message(interaction.guild)

        await interaction.response.send_message(
            "✅ ลาเวลา 20:00 สำเร็จ",
            ephemeral=True
        )

    @discord.ui.button(label="22:00", emoji="🌌", style=discord.ButtonStyle.success)
    async def leave_22(self, interaction: discord.Interaction, button: Button):

        if not is_active_time():
            await interaction.response.send_message(
                "⛔ ระบบเปิดเฉพาะ 18:00 - 00:00",
                ephemeral=True
            )
            return

        name = interaction.user.display_name

        if name in leave_data["20:00"]:
            leave_data["20:00"].remove(name)

        if name not in leave_data["22:00"]:
            leave_data["22:00"].append(name)

        save_data()

        await update_leave_message(interaction.guild)

        await interaction.response.send_message(
            "✅ ลาเวลา 22:00 สำเร็จ",
            ephemeral=True
        )

    @discord.ui.button(label="ยกเลิก", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_leave(self, interaction: discord.Interaction, button: Button):

        name = interaction.user.display_name

        if name in leave_data["20:00"]:
            leave_data["20:00"].remove(name)

        if name in leave_data["22:00"]:
            leave_data["22:00"].remove(name)

        save_data()

        await update_leave_message(interaction.guild)

        await interaction.response.send_message(
            "❌ ยกเลิกการลาแล้ว",
            ephemeral=True
        )


# ======================
# อัปเดตข้อความหลัก
# ======================

async def update_leave_message(guild):

    global message_id

    channel = discord.utils.get(
        guild.text_channels,
        name=LEAVE_CHANNEL_NAME
    )

    if not channel:
        return

    try:
        if message_id:
            msg = await channel.fetch_message(message_id)
            await msg.edit(
                embed=build_embed(),
                view=LeaveView()
            )
            return
    except:
        pass

    msg = await channel.send(
        embed=build_embed(),
        view=LeaveView()
    )

    message_id = msg.id


# ======================
# อัปเดตเวลาเรียลไทม์
# ======================

@tasks.loop(seconds=30)
async def refresh_embed():

    for guild in bot.guilds:
        await update_leave_message(guild)


# ======================
# สรุปรายชื่อ
# ======================

@tasks.loop(minutes=1)
async def auto_summary():

    now = datetime.now(THAI_TZ)

    for guild in bot.guilds:

        channel = discord.utils.get(
            guild.text_channels,
            name=SUMMARY_CHANNEL_NAME
        )

        if not channel:
            continue

        if now.hour == 20 and now.minute == 0:

            names = leave_data["20:00"]

            text = "\n".join(
                [f"• {x}" for x in names]
            ) or "ไม่มีผู้ลา"

            await channel.send(
                f"📢 สรุปรายชื่อผู้ลาเวลา 20:00\n\n{text}"
            )

        if now.hour == 22 and now.minute == 0:

            names = leave_data["22:00"]

            text = "\n".join(
                [f"• {x}" for x in names]
            ) or "ไม่มีผู้ลา"

            await channel.send(
                f"📢 สรุปรายชื่อผู้ลาเวลา 22:00\n\n{text}"
            )


# ======================
# รีเซ็ตเที่ยงคืน
# ======================

@tasks.loop(minutes=1)
async def daily_reset():

    global leave_data

    now = datetime.now(THAI_TZ)

    if now.hour == 0 and now.minute == 0:
        leave_data = {
            "20:00": [],
            "22:00": []
        }

        save_data()

        for guild in bot.guilds:
            await update_leave_message(guild)


# ======================
# Ready
# ======================

@bot.event
async def on_ready():
    print(f"ออนไลน์แล้ว: {bot.user}")

    load_data()

    refresh_embed.start()
    auto_summary.start()
    daily_reset.start()

    for guild in bot.guilds:
        await update_leave_message(guild)


keep_alive()
bot.run(os.getenv("TOKEN"))
