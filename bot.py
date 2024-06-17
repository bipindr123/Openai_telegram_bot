import asyncio
import logging
import re
import sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
import openai
from openai import OpenAI
import json
import os
from dotenv import load_dotenv
import imgbbpy

load_dotenv()

openai_key=os.getenv('OPENAI_KEY')
openai_base=os.getenv('OPENAI_BASE')
TOKEN = os.getenv('TOKEN')
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')
userlog = os.getenv('USERLOG')

client = OpenAI(api_key=openai_key, base_url=openai_base)
import requests

# add more as you like
available_models = [
"llama-3-70b",
"gpt-3.5-turbo",
"gpt-3.5-turbo-1106",
"gpt-4",
"gpt-4-turbo",
]

image_models = [
    'openjourney-xl' ,
    'realisticVision' ,
    'openjourney-v4' ,
    'dreamshaper' ,
    'absoluteReality' ,
    'meinamix' ,
    'deliberate' ,
    'dall-e-3' ,
    'deepfloyd-if' ,
    'majicmixsombre', 
    'pastelMixAnime' ,
    'sdxl'
]
voice_d  = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "serena": "pMsXgVXv3BLzUgSXRplE",
    "brian": "nPczCjzI2devNBz1zQrb",
    "jessie": "t0jbNlBVZ17f02VDIeMI"
}

voice_models = ["adam", "serena", "brian", "jessie"]

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

class Intro(StatesGroup):
    waiting_for_reason = State()

user_states = {}

async def logme(username, model, text):
    if userlog:
        if username:
            msg = str(username) + " " + str(model) +" "+ text
        else:
            msg = str() + " " + str(model) +" "+ text
        await bot.send_message(chat_id=userlog, text=msg)

async def generate_speech(text: str, chat_id):
    try:
        user_id = chat_id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        headers = {"Authorization": f"Bearer {openai_key}"}
        s_data = {
                "text": text,
                "voice_id": voice_d[model]
                }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                openai_base +"/audio/tts" , json=s_data
            ) as resp:
                if resp.status == 200:
                    print(resp)
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
        
        conversation = user_data["conversation"]

        if not im_url:
            if model == "llava-13b":
                conversation.append({"role": "user", "content": text})
            else:
                conversation.append({'role': 'user', 'content': [{'type': 'text', 'text': text}]})
        else:
            if model == "gemini-pro-vision":
                conversation.append(
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
                )
            else:
                 conversation.append({"role": "system", "content": im_url})
                 conversation.append({"role": "user", "content": text})
                
        resp = client.chat.completions.create(
            model=model,
            messages=conversation,
            stream=False,
        )
        if resp:
            ai_response = resp.choices[0].message.content
            if model == "llava-13b":
                conversation.append({"role": "user", "content": ai_response})
            else:
                conversation.append({'role': 'user', 'content': [{'type': 'text', 'text': ai_response}]})

            return ai_response
        else:
            return "server error"

    except Exception as e:
        raise Exception(f"Error : {str(e)}")

async def start_dialog(user_id, message, state: FSMContext):
    if user_id not in user_states:
        await message.reply("How did you find this bot? answer to continue")
        await state.set_state(Intro.waiting_for_reason)
        return
    user_data = user_states[user_id]

    if user_data["model"]:
        await bot.send_message(
            user_id, "Please complete the ongoing conversation first."
        )
    else:
        user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
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
        await message.reply(
            f"Choose an option:", reply_markup=model_keyboard
        )

@dp.message(Intro.waiting_for_reason)
async def handle_reason(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = message.from_user
    user_info = " ".join([message.from_user.full_name, message.from_user.username, str(message.from_user.id)])
    await logme(user_info , "Intro", message.text)
    await state.clear()

    user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
    await message.answer(
        f"Hello, {user.first_name}! I'm EvilgrinGPT created by evilgrin.",
        reply_markup=get_start_dialog_keyboard(),
    )
    await start_dialog(user_id, message, state)


@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = message.from_user
    if user_id not in user_states:
        await message.reply("How did you find this bot? answer to continue")
        await state.set_state(Intro.waiting_for_reason)
    else:
        user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
        await start_dialog()


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
            "Upload a photo with your question as the caption "
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
        await state.set_state(Tts.waiting_for_tts)
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
    user_info = " ".join([message.from_user.full_name, message.from_user.username, str(message.from_user.id)])
    await logme(user_info , model, message.text)
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
        if hasattr(e, "message"):
            error_message += e.message
        else:
            error_message += str(e)
        await message.answer(error_message)

@dp.message(lambda message: message.text.lower() == "finish dialogue" if message.text else False)
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
        user_info = " ".join([message.from_user.full_name, message.from_user.username, str(message.from_user.id)])
        await logme(user_info , model, message.text)

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
        if message.text:
            text = message.text
        else:
            if message.caption:
                text = message.caption
            else:
                message.reply("Enter valid caption")
                return
        user_id = message.chat.id
        user_data = user_states.get(user_id, {})
        model = user_data.get("model")
        
        if text.lower() == "finish dialogue":
            await state.clear()
            user_id = message.from_user.id
            user_states[user_id] = {"model": None, "button_sent": False, "conversation": []}
            await message.reply(
                'Dialogue finished. You can start a new dialogue by clicking "Start Dialogue".',
                reply_markup=get_start_dialog_keyboard(),
            )
            return
        
        if message.caption:
            res = await bot.download(message.photo[-1],  destination="/tmp/teleimg.jpg")

            client = imgbbpy.AsyncClient(IMGBB_API_KEY)
            img = await client.upload(file='/tmp/teleimg.jpg', expiration=500)
            await client.close()
            img_url = img.url
        
            user_info = " ".join([message.from_user.full_name, message.from_user.username, str(message.from_user.id)])
            await logme(user_info , model, message.text)
        else:
            img_url = None

        tmp_file_name = ""
        if re.search("file:\w*", text):
            tmp_file_name = re.search("file:\w*", text).group(0)
            text = text.replace(tmp_file_name, "")
            tmp_file_name = tmp_file_name.split(":")
            tmp_file_name = ".".join(tmp_file_name)
        
        resp = await generate_vision(text, message.chat.id, img_url)
        if tmp_file_name:
            with open("/tmp/"+tmp_file_name, "w") as docu:
                docu.write(resp)
            tmpf = FSInputFile("/tmp/"+tmp_file_name)
            await bot.send_document(message.chat.id, tmpf)
            os.remove("/tmp/"+tmp_file_name)
        await message.reply(resp)

    except Exception as error:
        print("An exception occurred:", error)
        await message.reply("Error in vision")

async def generate_tts_for_text(text: str, chat_id: int):
    if text:
        resp = await generate_speech(text, chat_id)
        url = resp["url"]
        await bot.send_audio(chat_id, audio=url, title=text[:5], performer="evilgrin")

@dp.message(F.content_type.in_({"text"}))
async def chat_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = user_states.get(user_id, {})
    model = user_data.get('model')
    user_info = " ".join([message.from_user.full_name, message.from_user.username, str(message.from_user.id)])
    await logme(user_info , model, message.text)
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
        await start_dialog(user_id, message, state)

def get_start_dialog_keyboard():
    start_button = KeyboardButton(text="Start Dialogue")
    start_markup = ReplyKeyboardMarkup(keyboard=[[start_button]], resize_keyboard=True)
    return start_markup

async def main() -> None:
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
