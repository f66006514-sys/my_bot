import asyncio
import logging
import os
from PIL import Image, ImageFilter, ImageEnhance
import io

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

TOKEN = "8841584811:AAF51W8lPun-g56spkEx4AZywXNMgHSiArw"
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# Papkalarni yaratish
for folder in ["asl_rasmlar", "tayyor_rasmlar", "original_photos", "processed_photos"]:
    os.makedirs(folder, exist_ok=True)

user_last_photo = {}
user_text_state = {}  # user_id -> "waiting_text" holati

def get_photo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Rasm haqida"), KeyboardButton(text="Rasmni kichraytirish")],
            [KeyboardButton(text="Qora-oq"), KeyboardButton(text="Sepiya")],
            [KeyboardButton(text="Negativ"), KeyboardButton(text="Xiralashtirish")],
            [KeyboardButton(text="Yorqinlikni oshirish"), KeyboardButton(text="Kontrastni oshirish")],
            [KeyboardButton(text="90° aylantirish"), KeyboardButton(text="Rasmni siqish")],
            [KeyboardButton(text="Aniqlik"), KeyboardButton(text="Piksellashtirish")],
            [KeyboardButton(text="Stiker qilish"), KeyboardButton(text="Chegara qo'shish")],
            [KeyboardButton(text="Matn yozish"), KeyboardButton(text="Statistika")],
            [KeyboardButton(text="Yordam")]
        ],
        resize_keyboard=True
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "📷 *Foto Bot*\n\n"
        "Rasm yoki stiker yuboring va effekt tanlang!\n\n"
        "/stats — statistika\n"
        "/help — yordam",
        reply_markup=get_photo_keyboard(),
        parse_mode="Markdown"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📷 *Yordam*\n\n"
        "1. Rasm yoki stiker yuboring\n"
        "2. Menyudan effekt tanlang\n\n"
        "Mavjud effektlar:\n"
        "🖼 Rasm haqida\n"
        "📉 Rasmni kichraytirish\n"
        "⬛ Qora-oq\n"
        "🟤 Sepiya\n"
        "🔄 Negativ\n"
        "🌫 Xiralashtirish\n"
        "☀️ Yorqinlikni oshirish\n"
        "🎨 Kontrastni oshirish\n"
        "🔃 90° aylantirish\n"
        "🗜 Rasmni siqish\n"
        "🔍 Aniqlik\n"
        "🟦 Piksellashtirish\n"
        "🎭 Stiker qilish\n"
        "🖼 Chegara qo'shish\n"
        "✏️ Matn yozish (matn yoki matn:rang formatida)",
        parse_mode="Markdown"
    )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    stats_file = f"tayyor_rasmlar/stats_{user_id}.txt"
    count = 0
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            count = int(f.read())

    asl_count = len([f for f in os.listdir('asl_rasmlar') if os.path.isfile(f'asl_rasmlar/{f}')])
    tayyor_count = len([f for f in os.listdir('tayyor_rasmlar') if os.path.isfile(f'tayyor_rasmlar/{f}') and not f.endswith('.txt')])

    await message.answer(
        f"📊 *Statistika*\n\n"
        f"Ishlangan rasmlar: {count}\n"
        f"Saqlangan asl rasmlar: {asl_count}\n"
        f"Yaratilgan effektlar: {tayyor_count}",
        parse_mode="Markdown"
    )

async def save_photo_stats(user_id: int):
    stats_file = f"tayyor_rasmlar/stats_{user_id}.txt"
    count = 0
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            count = int(f.read())
    count += 1
    with open(stats_file, "w") as f:
        f.write(str(count))

async def get_image_from_user(user_id: int) -> tuple[Image.Image, bytes] | None:
    """Foydalanuvchi oxirgi rasmini yuklab olib PIL Image qaytaradi"""
    photo_data = user_last_photo.get(user_id)
    if not photo_data:
        return None

    photo_type, file_id = photo_data

    file = await bot.get_file(file_id)
    downloaded = await bot.download_file(file.file_path)
    raw_bytes = downloaded.getvalue()

    image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA" if photo_type == "sticker" else "RGB")
    return image, raw_bytes

async def apply_effect(message: Message, effect_name: str, effect_func):
    user_id = message.from_user.id
    result = await get_image_from_user(user_id)

    if not result:
        await message.answer("❗ Avval rasm yoki stiker yuboring!")
        return

    image, raw_bytes = result
    status_msg = await message.answer(f"⏳ {effect_name} qo'llanmoqda...")

    try:
        processed_image = effect_func(image)

        # Natijani saqlash (tayyor_rasmlar papkasiga)
        save_filename = f"tayyor_rasmlar/{user_id}_{effect_name.replace(' ', '_')}.jpg"
        processed_image.convert("RGB").save(save_filename, format="JPEG", quality=95)

        output_buffer = io.BytesIO()
        processed_image.convert("RGB").save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)

        await message.answer_photo(
            BufferedInputFile(output_buffer.getvalue(), filename="processed.jpg"),
            caption=f"✅ '{effect_name}' effekti qo'llandi!\n💾 Rasm saqlandi."
        )

        await save_photo_stats(user_id)
        await status_msg.delete()

    except Exception as e:
        await status_msg.delete()
        await message.answer(f"❌ Xatolik: {str(e)}")

# ── RASM qabul qilish ──────────────────────────────────────────────────────────
@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    photo_obj = message.photo[-1]

    user_last_photo[user_id] = ("photo", photo_obj.file_id)

    file = await bot.get_file(photo_obj.file_id)
    downloaded = await bot.download_file(file.file_path)

    filename = f"asl_rasmlar/{user_id}_{photo_obj.file_id}.jpg"
    with open(filename, "wb") as f:
        f.write(downloaded.getvalue())

    await message.answer(
        "✅ Rasm qabul qilindi va saqlandi! Effekt tanlang.",
        reply_markup=get_photo_keyboard()
    )

# ── STIKER qabul qilish ────────────────────────────────────────────────────────
@router.message(F.sticker)
async def handle_sticker(message: Message):
    user_id = message.from_user.id
    sticker = message.sticker

    # Faqat oddiy rasmli stikerlarni qo'llab-quvvatlash (webp)
    if sticker.is_animated or sticker.is_video:
        await message.answer("❗ Hozircha faqat oddiy (statik) stikerlar qabul qilinadi.")
        return

    user_last_photo[user_id] = ("sticker", sticker.file_id)

    file = await bot.get_file(sticker.file_id)
    downloaded = await bot.download_file(file.file_path)

    filename = f"asl_rasmlar/{user_id}_{sticker.file_id}.webp"
    with open(filename, "wb") as f:
        f.write(downloaded.getvalue())

    await message.answer(
        "✅ Stiker qabul qilindi va saqlandi! Effekt tanlang.",
        reply_markup=get_photo_keyboard()
    )

# ── EFFEKTLAR ─────────────────────────────────────────────────────────────────
@router.message(F.text == "Rasm haqida")
async def photo_info(message: Message):
    user_id = message.from_user.id
    result = await get_image_from_user(user_id)

    if not result:
        await message.answer("❗ Avval rasm yoki stiker yuboring!")
        return

    image, raw_bytes = result
    size_kb = len(raw_bytes) // 1024

    await message.answer(
        f"🖼 *Rasm haqida*\n\n"
        f"📐 O'lchami: {image.width} x {image.height}px\n"
        f"🎨 Rejim: {image.mode}\n"
        f"📦 Hajmi: {size_kb} KB\n"
        f"📋 Format: {image.format or 'JPEG/WEBP'}",
        parse_mode="Markdown"
    )

@router.message(F.text == "Rasmni kichraytirish")
async def resize_photo(message: Message):
    def effect(img):
        return img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    await apply_effect(message, "Rasmni kichraytirish", effect)

@router.message(F.text == "Qora-oq")
async def bw_photo(message: Message):
    await apply_effect(message, "Qora-oq", lambda img: img.convert("L").convert("RGB"))

@router.message(F.text == "Sepiya")
async def sepia_photo(message: Message):
    def effect(img):
        img = img.convert("RGB")
        pixels = img.load()
        for i in range(img.width):
            for j in range(img.height):
                r, g, b = pixels[i, j]
                pixels[i, j] = (
                    min(255, int(r * 0.393 + g * 0.769 + b * 0.189)),
                    min(255, int(r * 0.349 + g * 0.686 + b * 0.168)),
                    min(255, int(r * 0.272 + g * 0.534 + b * 0.131)),
                )
        return img
    await apply_effect(message, "Sepiya", effect)

@router.message(F.text == "Negativ")
async def negative_photo(message: Message):
    def effect(img):
        img = img.convert("RGB")
        pixels = img.load()
        for i in range(img.width):
            for j in range(img.height):
                r, g, b = pixels[i, j]
                pixels[i, j] = (255 - r, 255 - g, 255 - b)
        return img
    await apply_effect(message, "Negativ", effect)

@router.message(F.text == "Xiralashtirish")
async def blur_photo(message: Message):
    await apply_effect(message, "Xiralashtirish", lambda img: img.filter(ImageFilter.GaussianBlur(radius=5)))

@router.message(F.text == "Yorqinlikni oshirish")
async def brightness_photo(message: Message):
    await apply_effect(message, "Yorqinlikni oshirish", lambda img: ImageEnhance.Brightness(img).enhance(1.8))

@router.message(F.text == "Kontrastni oshirish")
async def contrast_photo(message: Message):
    await apply_effect(message, "Kontrastni oshirish", lambda img: ImageEnhance.Contrast(img).enhance(2.0))

@router.message(F.text == "90° aylantirish")
async def rotate_photo(message: Message):
    await apply_effect(message, "90° aylantirish", lambda img: img.rotate(-90, expand=True))

@router.message(F.text == "Aniqlik")
async def sharpen_photo(message: Message):
    await apply_effect(message, "Aniqlik", lambda img: img.filter(ImageFilter.SHARPEN))

@router.message(F.text == "Piksellashtirish")
async def pixelate_photo(message: Message):
    def effect(img):
        small = img.resize((img.width // 10, img.height // 10), Image.NEAREST)
        return small.resize((img.width, img.height), Image.NEAREST)
    await apply_effect(message, "Piksellashtirish", effect)

@router.message(F.text == "Stiker qilish")
async def make_sticker(message: Message):
    """Rasmni stiker formatiga (512x512 PNG shaffof fon) aylantirish"""
    user_id = message.from_user.id
    result = await get_image_from_user(user_id)

    if not result:
        await message.answer("❗ Avval rasm yoki stiker yuboring!")
        return

    image, _ = result
    status_msg = await message.answer("⏳ Stiker tayyorlanmoqda...")

    try:
        img = image.convert("RGBA")
        img.thumbnail((512, 512), Image.LANCZOS)

        # 512x512 shaffof fonga joylashtirish
        background = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        offset = ((512 - img.width) // 2, (512 - img.height) // 2)
        background.paste(img, offset)

        output_buffer = io.BytesIO()
        background.save(output_buffer, format="PNG")
        output_buffer.seek(0)

        save_filename = f"tayyor_rasmlar/{user_id}_stiker.png"
        background.save(save_filename, format="PNG")

        await message.answer_document(
            BufferedInputFile(output_buffer.getvalue(), filename="sticker.png"),
            caption="🎭 Stiker tayyor! (512x512 PNG)\n💾 Saqlandi."
        )

        await save_photo_stats(user_id)
        await status_msg.delete()

    except Exception as e:
        await status_msg.delete()
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "Chegara qo'shish")
async def add_border(message: Message):
    """Rasmga chegara qo'shish"""
    def effect(img):
        from PIL import ImageOps
        img = img.convert("RGB")
        return ImageOps.expand(img, border=20, fill=(255, 255, 255))
    await apply_effect(message, "Chegara qo'shish", effect)

@router.message(F.text == "Rasmni siqish")
async def compress_photo(message: Message):
    user_id = message.from_user.id
    result = await get_image_from_user(user_id)

    if not result:
        await message.answer("❗ Avval rasm yoki stiker yuboring!")
        return

    image, raw_bytes = result
    status_msg = await message.answer("⏳ Rasm siqilmoqda...")

    try:
        compressed = image.convert("RGB").resize(
            (image.width // 2, image.height // 2), Image.LANCZOS
        )

        output_buffer = io.BytesIO()
        compressed.save(output_buffer, format="JPEG", quality=40)
        output_buffer.seek(0)

        # Saqlash
        save_filename = f"tayyor_rasmlar/{user_id}_siqilgan.jpg"
        compressed.save(save_filename, format="JPEG", quality=40)

        original_kb = len(raw_bytes) // 1024
        new_kb = len(output_buffer.getvalue()) // 1024

        await message.answer_photo(
            BufferedInputFile(output_buffer.getvalue(), filename="compressed.jpg"),
            caption=(
                f"🗜 Rasm siqildi!\n"
                f"📦 Oldin: {original_kb} KB\n"
                f"📉 Hozir: {new_kb} KB\n"
                f"💾 Saqlandi."
            )
        )

        await save_photo_stats(user_id)
        await status_msg.delete()

    except Exception as e:
        await status_msg.delete()
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "Matn yozish")
async def ask_text_input(message: Message):
    user_id = message.from_user.id
    result = await get_image_from_user(user_id)
    if not result:
        await message.answer("❗ Avval rasm yoki stiker yuboring!")
        return
    user_text_state[user_id] = "waiting_text"
    await message.answer(
        "✏️ Rasmga yozmoqchi bo'lgan matnni yuboring:\n\n"
        "_(Format: matn — oddiy; **matn:rang** — masalan: Salom:red yoki Salom:yellow)_",
        parse_mode="Markdown"
    )

@router.message(F.text)
async def handle_text_on_image(message: Message):
    user_id = message.from_user.id

    # Faqat "waiting_text" holatida ishlaydi
    if user_text_state.get(user_id) != "waiting_text":
        return

    text_input = message.text.strip()

    # Rang ajratish: "Matn:rang" formatida
    color = "white"
    stroke_color = "black"
    if ":" in text_input:
        parts = text_input.rsplit(":", 1)
        text_to_draw = parts[0].strip()
        color_input = parts[1].strip().lower()
        color_map = {
            "white": "white", "oq": "white",
            "black": "black", "qora": "black",
            "red": "red", "qizil": "red",
            "yellow": "yellow", "sariq": "yellow",
            "blue": "blue", "ko'k": "blue",
            "green": "green", "yashil": "green",
            "orange": "orange", "to'q sariq": "orange",
            "pink": "pink", "pushti": "pink",
        }
        color = color_map.get(color_input, "white")
        stroke_color = "black" if color != "black" else "white"
    else:
        text_to_draw = text_input

    user_text_state.pop(user_id, None)

    result = await get_image_from_user(user_id)
    if not result:
        await message.answer("❗ Rasm topilmadi. Qaytadan rasm yuboring.")
        return

    image, _ = result
    status_msg = await message.answer("⏳ Matn qo'llanmoqda...")

    try:
        from PIL import ImageDraw, ImageFont
        img = image.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Font o'lchami rasmga nisbatan
        font_size = max(20, img.width // 15)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # Matnni markazga joylashtirish (pastki qismga)
        bbox = draw.textbbox((0, 0), text_to_draw, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = (img.width - text_w) // 2
        y = img.height - text_h - int(img.height * 0.07)

        # Soya (outline) — o'qish uchun kontrastli
        for dx, dy in [(-2,-2),(-2,2),(2,-2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((x + dx, y + dy), text_to_draw, font=font, fill=stroke_color)

        # Asosiy matn
        draw.text((x, y), text_to_draw, font=font, fill=color)

        # Saqlash
        save_filename = f"tayyor_rasmlar/{user_id}_matn.jpg"
        img.save(save_filename, format="JPEG", quality=95)

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)

        await message.answer_photo(
            BufferedInputFile(output_buffer.getvalue(), filename="matn_rasm.jpg"),
            caption=f"✅ Matn qo'shildi: *{text_to_draw}*\n🎨 Rang: {color}\n💾 Saqlandi.",
            parse_mode="Markdown"
        )

        await save_photo_stats(user_id)
        await status_msg.delete()

    except Exception as e:
        await status_msg.delete()
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "Statistika")
async def stats_button(message: Message):
    await cmd_stats(message)

@router.message(F.text == "Yordam")
async def help_button(message: Message):
    await cmd_help(message)

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
