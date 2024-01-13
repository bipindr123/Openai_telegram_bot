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
from openai import OpenAI
import json
import os
from dotenv import load_dotenv

load_dotenv()

openai_key=os.getenv('OPENAI_KEY')
openai_base=os.getenv('OPENAI_BASE')
TOKEN = os.getenv('TOKEN')

client = OpenAI(api_key=openai_key, base_url=openai_base)
import requests

# add more as you like
available_models = [
    "gpt-4",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo",
    "gpt-4-1106-preview",
    "llama-2-70b-chat",
    "gemini-pro",
    ]

image_models = [
    'stable-diffusion-1.5' ,
    'stable-diffusion-2.1' ,
    'material-diffusion' ,
    'dreamshaper-6' ,
    'kandinsky-2.1' ,
    'wuerstchen-diffusion' ,
    'kandinsky-2.2' ,
    'realistic-vision' ,
    'timeless' ,
    'meinamix' ,
    'lyriel-1.6' ,
    'mechamix-10' ,
    'meinamix-11' ,
    'portraitplus' ,
    'dall-e-3' ,
    'dreamshaper-8' ,
    'deepfloyd-if' ,
    'pastelMixAnime' ,
    'openjourney' ,
    'sdxl'
]
voice_models = ["voice-paimon", "google-speech", "voice-adam", "voice-freya"]

vision_models = ["gemini-pro-vision", "llava-13b"]


logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)


class ImagePrompt(StatesGroup):
    waiting_for_text = State()

class Tts(StatesGroup):
    waiting_for_tts = State()

class Viz(StatesGroup):
    waiting_for_vision = State()

user_states = {}

async def logme(username, model, text):
    msg = str(username) + " " + str(model) +" "+ text
    await bot.send_message(chat_id='@evilbotlogs', text=msg)

async def generate_speech(text: str, chat_id):
    try:
        user_id = chat_id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        headers = {"Authorization": f"Bearer {openai_key}", 'Content-Type': 'application/json'}
        # json_data = {"input": text, "model": model, "language": "en"}
        s_data = {
                "prompt": text,
                "model": model,
                }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                openai_base , json=s_data
            ) as resp:
                if resp.status == 200:
                    response = await resp.read()
                    return json.loads(response.decode('utf-8'))
                else:
                    error_message = await resp.text()
                    raise Exception(
                        f"Text-to-speech API returned non-200 status code: {resp.status}. Error: {error_message}"
                    )
    except Exception as e:
        raise Exception(f"Error in generating speech: {str(e)}")
    

async def generate_vision(text: str, chat_id, im_url):
    try:
        user_id = chat_id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        headers = {"Authorization": f"Bearer {openai_key}", 'Content-Type': 'application/json'}
        # json_data = {"input": text, "model": model, "language": "en"}
        
        if model == "gemini-pro-vision":
            in_messages =[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {
                            "type": "image_url",
                            "image_url": im_url
                        },
                    ],
                }
            ]
        else:
            in_messages=[
                    {"role": "system", "content": im_url},
                    {"role": "user", "content": text},
                ]
        
        resp = client.chat.completions.create(
            model=model,
            messages=in_messages,
            stream=False,
        )

        ai_response = resp.choices[0].message.content
        return ai_response

    except Exception as e:
        raise Exception(f"Error : {str(e)}")


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
            text="Text-to-Speech (BROKEN)", callback_data="audio_nested_keyboard"
        )
        vision_button = types.InlineKeyboardButton(
            text="Vision", callback_data="vision_nested_keyboard"
        )

        model_buttons = []
        model_buttons.append([chat_button])
        model_buttons.append([image_button])
        model_buttons.append([tts_button])
        model_buttons.append([vision_button])

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
    in ("text_nested_keyboard", "image_nested_keyboard", "audio_nested_keyboard", "vision_nested_keyboard")
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

    elif callback_query.data == "audio_nested_keyboard":
        model_buttons = [
            [types.InlineKeyboardButton(text=model, callback_data=model)]
            for model in voice_models
        ]
    else:
        model_buttons = [
            [types.InlineKeyboardButton(text=model, callback_data=model)]
            for model in vision_models
        ]

    model_keyboard = types.InlineKeyboardMarkup(inline_keyboard=model_buttons)
    await bot.send_message(
        user_id, f"Please select a model", reply_markup=model_keyboard
    )


@dp.callback_query(
    lambda query: query.data in available_models
    or query.data in image_models
    or query.data in voice_models
    or query.data in vision_models
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
    
    elif callback_query.data in vision_models:
        await callback_query.message.answer(
            "Enter your promt in this format: \"question ,, https://image.jpg\"  "
        )
        await state.set_state(Viz.waiting_for_vision)
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
    await logme(message.from_user.username,model,message.text)
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
        response = client.images.generate(model=model, prompt=prompt_text, n=2)
        for img_url in response.data:
            await bot.send_photo(message.chat.id, photo=img_url.url)

    except openai.APIError as e:
        error_message = "An error occurred while creating the image: "
        if hasattr(e, "response") and "detail" in e.response:
            error_message += e.response["detail"]
        else:
            error_message += str(e)
    finally:
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


@dp.message(Tts.waiting_for_tts)
async def process_tts_text(message: types.Message, state: FSMContext):
    try:
        text = message.text
        user_id = message.chat.id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        
        await logme(message.from_user.username , model, message.text)

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

@dp.message(Viz.waiting_for_vision)
async def process_vision(message: types.Message, state: FSMContext):
    try:
        text = message.text
        user_id = message.chat.id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        
        await logme(message.from_user.username , model, message.text)

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

        text, im_url = text.split(" ,, ")

        if not text:
            text = "Please enter valid text."

        resp = await generate_vision(text, message.chat.id, im_url)
        await message.reply(resp)

    except Exception as error:
        print("An exception occurred:", error)
        await message.reply("Error in text-to-speech synthesis.")


async def generate_tts_for_text(text: str, chat_id: int):
    if text:
        resp = await generate_speech(text, chat_id)
        url = resp["url"]
        await bot.send_audio(chat_id, audio=url, title=text[:5], performer="evilgrin")
            


@dp.message(F.content_type.in_({"text"}))
async def chat_message(message: types.Message):
    user_id = message.from_user.id
    user_data = user_states.get(user_id, {})
    model = user_data.get('model')
    await logme(message.from_user.username , model, message.text)
    if model:
        conversation = user_data["conversation"]
        conversation.append({"role": "user", "content": message.text})
        try:
            response = client.chat.completions.create(model=model, messages=conversation)
            conversation.append(response.choices[0].message)
            ai_response = response.choices[0].message.content
            await message.reply(ai_response)

        except Exception as e:
            error_message = "An error occurred text: "
            if hasattr(e, "response") and "detail" in e.response:
                error_message += e.response["detail"]
            else:
                error_message += str(e)
            await message.answer(error_message)

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
