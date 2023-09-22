import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
import openai
import requests
from fp.fp import FreeProxy

TOKEN = ''
openai.api_key = ''
openai.api_base = ""

# add more as you like
available_models = [
    "you-chat",
    "oasst-llama-2-70b",
    "llama-2-70b",
    "inflection-1",
    "gpt-4-0613",
    "gpt-4",
    "gpt-3.5-turbo-16k-0613",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo",
    "flan-t5-xxl",
    "decilm-6b-instruct",
    "claude-2-100k",
    "chatglm-2-6b",
]

image_models = [
    "wuerstchen-diffusion",
    "toonyou",
    "theallys-mix-2",
    "stable-diffusion-1.4",
    "shonins-beautiful",
    "sdxl",
    "sdv-1.4",
    "run-diffusion",
    "rev-animated",
    "realistic-vision-5",
    "realistic-vision-2",
    "realistic-vision",
    "portraitplus",
    "orange-mix",
    "meinamix-9",
    "meinamix-11",
    "lyriel-1.6",
    "dreamshaper-8",
    "dreamshaper-6",
    "dall-e",
    "anything-diffusion-5",
    "anime-diffusion-xl",
    "absolute-reality-1.8",
]
voice_models = ["voice-paimon", "google-speech", "voice-adam", "voice-freya"]


logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)


class ImagePrompt(StatesGroup):
    waiting_for_text = State()


class Tts(StatesGroup):
    waiting_for_tt = State()


user_states = {}

async def generate_speech(text: str, chat_id):
    try:
        user_id = chat_id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        headers = {"Authorization": f"Bearer {openai.api_key}"}
        json_data = {"input": text, "model": model, "language": "en"}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                openai.api_base + "/audio/speech", json=json_data
            ) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    return response
                else:
                    error_message = await resp.text()
                    raise Exception(
                        f"Text-to-speech API returned non-200 status code: {resp.status}. Error: {error_message}"
                    )
    except Exception as e:
        raise Exception(f"Error in generating speech: {str(e)}")


async def start_dialog(user_id):
    user_data = user_states[user_id]
    if user_data["model"]:
        await bot.send_message(
            user_id, "Please complete the ongoing conversation first."
        )
    else:
        chat_button = types.InlineKeyboardButton(
            text="Chat", callback_data="text_nested_keyboard"
        )
        image_button = types.InlineKeyboardButton(
            text="Create Image", callback_data="image_nested_keyboard"
        )
        tts_button = types.InlineKeyboardButton(
            text="Text-to-Speech", callback_data="audio_nested_keyboard"
        )

        model_buttons = []
        model_buttons.append([chat_button])
        model_buttons.append([image_button])
        model_buttons.append([tts_button])
        # Create keyboard
        model_keyboard = types.InlineKeyboardMarkup(inline_keyboard=model_buttons)
        await bot.send_message(
            user_id, f"Choose an option:", reply_markup=model_keyboard
        )


@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = message.from_user
    user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
    await message.answer(
        f"Hello, {user.first_name}! I'm EvilgrinGPT created by evilgrin.",
        reply_markup=get_start_dialog_keyboard(),
    )
    await start_dialog(user_id)


@dp.callback_query(
    lambda query: query.data
    in ("text_nested_keyboard", "image_nested_keyboard", "audio_nested_keyboard")
)
async def nested_keyboard(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if callback_query.data == "text_nested_keyboard":
        model_buttons = [
            [types.InlineKeyboardButton(text=model, callback_data=model)]
            for model in available_models
        ]
    elif callback_query.data == "image_nested_keyboard":
        model_buttons = [
            [types.InlineKeyboardButton(text=model, callback_data=model)]
            for model in image_models
        ]
    else:
        model_buttons = [
            [types.InlineKeyboardButton(text=model, callback_data=model)]
            for model in voice_models
        ]

    model_keyboard = types.InlineKeyboardMarkup(inline_keyboard=model_buttons)
    await bot.send_message(
        user_id, f"Please select a model", reply_markup=model_keyboard
    )


@dp.callback_query(
    lambda query: query.data in available_models
    or query.data in image_models
    or query.data in voice_models
)
async def select_model_or_image_prompt(
    callback_query: types.CallbackQuery, state: FSMContext
):
    user_id = callback_query.from_user.id

    if user_id not in user_states:
        user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}

    await callback_query.answer()
    if callback_query.data in image_models:
        await callback_query.message.answer("Enter text for the prompt:")
        await state.set_state(ImagePrompt.waiting_for_text)
        selected_model = callback_query.data
        user_states[user_id]["model"] = selected_model
        await callback_query.message.edit_text(
            f"Selected Model: {selected_model}.\nSend a message to start the dialogue."
        )

        cancel_button = KeyboardButton(text="Finish Dialogue")
        cancel_markup = ReplyKeyboardMarkup(
            keyboard=[[cancel_button]], resize_keyboard=True
        )
        await callback_query.message.answer(
            'You can finish the dialogue by pressing the "Finish Dialogue" button.',
            reply_markup=cancel_markup,
        )
        user_states[user_id]["button_sent"] = True

    elif callback_query.data in voice_models:
        await callback_query.message.answer(
            "Limit is 50 characters. Enter the text for speech synthesis:"
        )
        await state.set_state(Tts.waiting_for_tt)
        selected_model = callback_query.data
        user_states[user_id]["model"] = selected_model
        await callback_query.message.edit_text(
            f"Selected Model: {selected_model}.\nSend a message to start the dialogue."
        )

        cancel_button = KeyboardButton(text="Finish Dialogue")
        cancel_markup = ReplyKeyboardMarkup(
            keyboard=[[cancel_button]], resize_keyboard=True
        )
        await callback_query.message.answer(
            'You can finish the dialogue by pressing the "Finish Dialogue" button.',
            reply_markup=cancel_markup,
        )
        user_states[user_id]["button_sent"] = True
    else:
        selected_model = callback_query.data
        user_states[user_id]["model"] = selected_model
        await callback_query.message.edit_text(
            f"Selected Model: {selected_model}.\nSend a message to start the dialogue."
        )
        cancel_button = KeyboardButton(text="Finish Dialogue")
        cancel_markup = ReplyKeyboardMarkup(
            keyboard=[[cancel_button]], resize_keyboard=True
        )
        await callback_query.message.answer(
            'You can finish the dialogue by pressing the "Finish Dialogue" button.',
            reply_markup=cancel_markup,
        )
        user_states[user_id]["button_sent"] = True


@dp.message(ImagePrompt.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = user_states.get(user_id, {})
    model = user_data.get("model")
    if message.text.lower() == "finish dialogue":
        await state.clear()
        user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
        await message.reply(
            'Dialogue finished. You can start a new dialogue by clicking "Start Dialogue".',
            reply_markup=get_start_dialog_keyboard(),
        )
        return
    try:
        prompt_text = message.text
        response = openai.Image.create(
            model=model, prompt=prompt_text, n=4, size="1024x1024"
        )
        for image in response["data"]:
            await bot.send_photo(message.chat.id, photo=image["url"])

    except openai.error.APIError as e:
        error_message = "An error occurred while creating the image: "
        if hasattr(e, "response") and "detail" in e.response:
            error_message += e.response["detail"]
        else:
            error_message += str(e)
        await message.answer(error_message)


@dp.message(lambda message: message.text.lower() == "finish dialogue")
async def cancel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = user_states.get(user_id)
    if user_data and user_data.get("button_sent"):
        user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
        await state.clear()
        await message.answer(
            'Dialogue finished. You can start a new dialogue by clicking "Start Dialogue".',
            reply_markup=get_start_dialog_keyboard(),
        )
    else:
        await message.reply("There is no active dialogue at the moment.")


@dp.message(Tts.waiting_for_tt)
async def process_tts_text(message: types.Message, state: FSMContext):
    try:
        text = message.text

        if text.lower() == "finish dialogue":
            await state.clear()
            user_id = message.from_user.id
            user_states[user_id]["model"] = None
            user_states[user_id]["button_sent"] = False
            await message.reply(
                'Dialogue finished. You can start a new dialogue by clicking "Start Dialogue".',
                reply_markup=get_start_dialog_keyboard(),
            )
            return

        text = text.strip()

        if not text:
            text = "Please enter valid text."

        await generate_tts_for_text(text, message.chat.id)

    except Exception as error:
        print("An exception occurred:", error)
        await message.reply("Error in text-to-speech synthesis.")


async def generate_tts_for_text(text: str, chat_id: int):
    if text:
        resp = await generate_speech(text, chat_id)
        url = resp["url"]
        await bot.send_audio(chat_id, audio=url, caption=text[:5])


@dp.message(F.content_type.in_({"text"}))
async def chat_message(message: types.Message):
    user_id = message.from_user.id
    user_data = user_states.get(user_id, {})
    model = user_data.get("model")
    msg = message.from_user.username + " " + str(model) + " " + message.text
    if model:
        conversation = user_data["conversation"]
        conversation.append({"role": "user", "content": message.text})
        response = openai.ChatCompletion.create(model=model, messages=conversation)
        conversation.append(response.choices[0].message)

        ai_response = response.choices[0].message["content"]
        await message.reply(ai_response)
        if not user_data.get("button_sent", False):
            cancel_button = KeyboardButton(text="Finish Dialogue")
            cancel_markup = ReplyKeyboardMarkup(
                keyboard=[[cancel_button]], resize_keyboard=True
            )
            await message.answer(
                'You can finish the dialogue by pressing the "Finish Dialogue" button.',
                reply_markup=cancel_markup,
            )
            user_states[user_id]["button_sent"] = True
    else:
        await start_dialog(user_id)


def get_start_dialog_keyboard():
    start_button = KeyboardButton(text="Start Dialogue")
    start_markup = ReplyKeyboardMarkup(keyboard=[[start_button]], resize_keyboard=True)
    return start_markup


async def main() -> None:
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
