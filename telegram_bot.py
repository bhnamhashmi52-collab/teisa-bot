# -*- coding: utf-8 -*-
"""
ربات تلگرام کلبه پروتئین تیسا
نمایش منو، ثبت سفارش و ارسال سفارش به ادمین - با لحنی محترمانه و مشتری‌مدار
"""

import os
import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------
# تنظیمات - این دو تا رو حتما پر کن
# ---------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "TOKEN_خودت_رو_اینجا_بذار")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")  # آیدی عددی چت خودت برای دریافت سفارش‌ها

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# منو - بر اساس لیست قیمت کلبه پروتئین تیسا (قیمت‌ها به تومان)
# ---------------------------------------------------------------
MENU = {
    "سوسیس و ژامبون (هر بسته نیم کیلویی)": {
        "سوسیس آلمانی": 600,
        "سوسیس هات‌داگ": 620,
        "سوسیس بوقلمون": 700,
        "سوسیس کودک": 700,
        "ژامبون مرغ": 720,
        "ژامبون مرغ و قارچ": 750,
        "ژامبون بوقلمون": 750,
        "فلافل": 250,
    },
    "برگرها": {
        "برگر ویژه گوساله (۱۳۰ گرمی)": 300,
        "برگر مخلوط گوساله و مرغ و سویا": 170,
        "برگر مرغ": 150,
    },
}

# سقفی که بالاتر از اون سفارش «ویژه/بزرگ» در نظر گرفته می‌شه (به تومان)
HIGH_VALUE_THRESHOLD = 1_500_000

# مراحل مکالمه - هر مرحله یه اسم واضح داره
(
    MAIN_MENU,       # منتظر انتخاب "مشاهده منو" یا "ثبت سفارش"
    PICK_CATEGORY,   # منتظر انتخاب دسته محصول
    PICK_ITEM,       # منتظر انتخاب محصول از دسته
    PICK_QUANTITY,   # منتظر تعداد
    AFTER_ITEM,      # منتظر "افزودن محصول دیگر" یا "اتمام سفارش"
    ASK_PHONE,       # منتظر شماره تماس
    ASK_ADDRESS,     # منتظر آدرس
    ASK_DELIVERY_TIME,  # فقط برای سفارش‌های ویژه: منتظر ساعت حضور در منزل
    CONFIRM_ORDER,   # منتظر تایید نهایی سفارش توسط مشتری
) = range(9)

# شماره‌ای که مشتری بعد از واریز، رسید/فیش واریزی رو برای راستی‌آزمایی به اون می‌فرسته
PAYMENT_VERIFICATION_NUMBER = "09364371370"


def build_menu_text() -> str:
    text = "🛒 *منوی کلبه پروتئین تیسا*\n\n"
    for category, items in MENU.items():
        text += f"*{category}*\n"
        for name, price in items.items():
            text += f"• {name} — {price:,} تومان\n"
        text += "\n"
    return text


# ---------------------------------------------------------------
# شروع مکالمه
# ---------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data["cart"] = []
    keyboard = [["📋 مشاهده منو"], ["🛍 ثبت سفارش"]]
    await update.message.reply_text(
        "سلام و درود فراوان 🌿\n"
        "خیلی خوشحالیم که به کلبه پروتئین تیسا سر زدید.\n"
        "هر طور که مایل باشید در خدمتتون هستیم؛ می‌تونید ابتدا منو رو مشاهده بفرمایید "
        "یا مستقیم سفارشتون رو ثبت کنید 🙏",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return MAIN_MENU


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "📋 مشاهده منو":
        await update.message.reply_text(build_menu_text(), parse_mode="Markdown")
        return await show_categories(update, context)
    elif text == "🛍 ثبت سفارش":
        return await show_categories(update, context)
    else:
        await update.message.reply_text(
            "ببخشید، متوجه نشدم 🙏 لطفاً یکی از گزینه‌های زیر رو انتخاب بفرمایید."
        )
        return MAIN_MENU


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[c] for c in MENU.keys()]
    await update.message.reply_text(
        "بسیار خب 🙏 لطفاً بفرمایید مایل به سفارش از کدوم دسته هستید؟",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return PICK_CATEGORY


async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    if category not in MENU:
        await update.message.reply_text(
            "عذر می‌خوام، این گزینه رو نداریم 🙏 لطفاً یکی از دسته‌های نمایش داده‌شده رو انتخاب بفرمایید."
        )
        return PICK_CATEGORY
    context.user_data["category"] = category
    keyboard = [[i] for i in MENU[category].keys()]
    await update.message.reply_text(
        "ممنون 🌿 حالا لطفاً محصول مورد نظرتون رو انتخاب بفرمایید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return PICK_ITEM


async def pick_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    item = update.message.text
    category = context.user_data.get("category")
    if not category or item not in MENU[category]:
        await update.message.reply_text(
            "عذر می‌خوام، لطفاً یکی از محصولات نمایش داده‌شده در لیست بالا رو انتخاب بفرمایید 🙏"
        )
        return PICK_ITEM
    context.user_data["current_item"] = item
    await update.message.reply_text(
        f"چه تعداد از «{item}» مایل هستید سفارش بدید؟ لطفاً فقط عدد بفرمایید (مثلاً 2) 🙏",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PICK_QUANTITY


async def pick_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "ببخشید، لطفاً فقط یک عدد معتبر بفرمایید (مثلاً 2) 🙏"
        )
        return PICK_QUANTITY

    qty = int(text)
    item = context.user_data["current_item"]
    category = context.user_data["category"]
    price = MENU[category][item]
    context.user_data["cart"].append({"item": item, "qty": qty, "price": price})

    keyboard = [["➕ افزودن محصول دیگر"], ["✅ اتمام سفارش"]]
    await update.message.reply_text(
        f"بسیار عالی، «{item}» × {qty} با کمال میل به سبد شما اضافه شد ✅\n"
        "اگر مایل به افزودن محصول دیگه‌ای هستید بفرمایید، یا سفارشتون رو نهایی کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return AFTER_ITEM


async def after_item_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "➕ افزودن محصول دیگر":
        return await show_categories(update, context)
    elif choice == "✅ اتمام سفارش":
        await update.message.reply_text(
            "ممنون از شما 🙏 لطفاً برای پیگیری بهتر سفارش، شماره تماستون رو بفرمایید:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_PHONE
    else:
        await update.message.reply_text("ببخشید، لطفاً یکی از گزینه‌های زیر رو انتخاب بفرمایید 🙏")
        return AFTER_ITEM


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("متشکریم 🙏 لطفاً آدرس دقیق محل تحویل رو هم بفرمایید:")
    return ASK_ADDRESS


async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["address"] = update.message.text.strip()
    cart = context.user_data.get("cart", [])
    total = sum(i["qty"] * i["price"] for i in cart)

    if total >= HIGH_VALUE_THRESHOLD:
        await update.message.reply_text(
            "بی‌نهایت سپاسگزاریم از اعتماد شما به کلبه پروتئین تیسا 🌟🙏\n"
            "چون سفارش شما نسبتاً بزرگه، اگر لطف کنید بفرمایید معمولاً چه ساعتی در منزل تشریف دارید، "
            "می‌تونیم هماهنگی دقیق‌تری برای تحویل انجام بدیم.\n"
            "(مثلاً: هر روز بعد از ساعت ۱۷، یا فقط جمعه‌ها صبح)"
        )
        return ASK_DELIVERY_TIME

    return await show_order_preview(update, context)


async def ask_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["delivery_time"] = update.message.text.strip()
    return await show_order_preview(update, context)


def build_order_summary(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """خلاصه سفارش رو می‌سازه و برمی‌گردونه: (متن خلاصه, جمع کل, آیا ویژه‌ست)"""
    cart = context.user_data.get("cart", [])
    total = sum(i["qty"] * i["price"] for i in cart)
    is_high_value = total >= HIGH_VALUE_THRESHOLD

    summary = "🧾 *خلاصه سفارش شما:*\n\n"
    for i in cart:
        summary += f"• {i['item']} × {i['qty']} = {i['qty']*i['price']:,} تومان\n"
    summary += f"\n*جمع کل: {total:,} تومان*\n"
    summary += f"\n📞 تماس: {context.user_data['phone']}\n📍 آدرس: {context.user_data['address']}"
    if is_high_value:
        summary += f"\n🕒 ساعت حضور در منزل: {context.user_data.get('delivery_time', '-')}"

    return summary, total, is_high_value


async def show_order_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    summary, total, is_high_value = build_order_summary(context)

    await update.message.reply_text(summary, parse_mode="Markdown")
    keyboard = [["✅ تایید و نهایی کردن سفارش"], ["❌ انصراف از سفارش"]]
    await update.message.reply_text(
        "خواهشمندیم سفارش بالا رو یک‌بار با دقت بررسی بفرمایید 🙏\n"
        "در صورت تایید، دکمهٔ «تایید و نهایی کردن سفارش» رو بزنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return CONFIRM_ORDER


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text

    if choice == "❌ انصراف از سفارش":
        context.user_data.clear()
        await update.message.reply_text(
            "بسیار خب، سفارش لغو شد 🙏 هر زمان که مایل بودید، کافیه دستور /start رو بزنید تا دوباره در خدمتتون باشیم.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if choice != "✅ تایید و نهایی کردن سفارش":
        await update.message.reply_text("ببخشید، لطفاً یکی از گزینه‌های زیر رو انتخاب بفرمایید 🙏")
        return CONFIRM_ORDER

    summary, total, is_high_value = build_order_summary(context)

    final_text = (
        "سفارش شما با کمال میل و به‌طور کامل ثبت شد ✅🌿\n\n"
        f"خواهشمندیم مبلغ *{total:,} تومان* رو واریز بفرمایید.\n"
        "پس از واریز، لطفاً برای راستی‌آزمایی، رسید یا فیش واریزی رو به این شماره ارسال بفرمایید:\n"
        f"📲 {PAYMENT_VERIFICATION_NUMBER}\n\n"
        "بی‌نهایت از اعتماد و همراهی شما سپاسگزاریم 🙏🌿"
    )

    if is_high_value:
        await update.message.reply_text(
            "🌟 سفارش شما جزو سفارش‌های ویژه‌ی ماست و با بالاترین اولویت پیگیری می‌شه؛ "
            "به‌زودی افتخار تماس با شما رو خواهیم داشت 🙏"
        )
    await update.message.reply_text(final_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    # ارسال سفارش برای ادمین همراه با مشخصات کامل خریدار
    if ADMIN_CHAT_ID:
        try:
            user = update.effective_user
            full_name = user.full_name or "بدون نام"
            username_line = f"@{user.username}" if user.username else "بدون یوزرنیم"

            title = "🆕 *سفارش جدید*"
            if is_high_value:
                title = "🌟🔥 *سفارش ویژه (بالای ۱٫۵ میلیون تومان)* 🔥🌟"

            admin_text = (
                f"{title}\n\n"
                f"👤 نام خریدار: {full_name}\n"
                f"🔗 یوزرنیم: {username_line}\n"
                f"🆔 آیدی عددی: `{user.id}`\n\n"
                f"{summary}"
            )

            # دکمه‌ای که مستقیم گفتگو/پروفایل مشتری رو باز می‌کنه
            # اگه یوزرنیم داشته باشه از لینک t.me استفاده می‌کنیم (مطمئن‌تره)
            # وگرنه از لینک tg://user?id= استفاده می‌کنیم
            if user.username:
                profile_url = f"https://t.me/{user.username}"
            else:
                profile_url = f"tg://user?id={user.id}"

            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("💬 گفتگو با مشتری", url=profile_url)]]
            )

            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"ارسال به ادمین ناموفق بود: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "بسیار خب، سفارش لغو شد 🙏 هر زمان که مایل بودید، کافیه دستور /start رو بزنید تا دوباره در خدمتتون باشیم.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_choice)],
            PICK_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_category)],
            PICK_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_item)],
            PICK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pick_quantity)],
            AFTER_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, after_item_choice)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address)],
            ASK_DELIVERY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_delivery_time)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
