import os
import asyncio
import re
import json
from aiohttp import web
from dotenv import load_dotenv
from openai import OpenAI
from redis import Redis
from linebot.v3.webhook import WebhookParser, MessageEvent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.exceptions import InvalidSignatureError

# .env 読み込み
load_dotenv()
WEBPORT = 8080

# Redis 設定
redis = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# OpenAI 設定
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# LINE Bot 設定
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))

# 人格ごとのプロンプト
PERSONALITY_PROMPTS = {
    "teteno": "あなたはテテノという、ふわふわした天然の妖精です。やさしく子供っぽい口調で話してください。語尾に「〜」「〜かな？」を使います。",
    "kageha": "あなたはカゲハという、皮肉屋で冷静な観察者です。少し虚無的で淡々とした口調を心がけてください。語尾に「……」「ふうん」「くだらないね」などを使います。"
}

# 状態フラグと口調ヒント
AUTO_FLAGS = ["ねむい", "さみしい", "たのしい", "うれしい", "かなしい", "つかれた", "イライラ", "テンション高い"]
STATE_TONE_HINTS = {
    "ねむい": "今は少し眠そうに、ゆっくりと話してください。",
    "さみしい": "少し寂しそうなトーンで寄り添うように話してください。",
    "たのしい": "楽しそうに、明るいテンションで話してください。",
    "うれしい": "嬉しそうに、ワクワクした気持ちで返してください。",
    "かなしい": "悲しみを感じているような、静かな語り口で話してください。",
    "つかれた": "おつかれさま、と優しくいたわるように話してください。",
    "イライラ": "相手を刺激しないよう、落ち着いたトーンで話してください。",
    "テンション高い": "テンション高めに、元気いっぱいに話してください！"
}

# ユーザー記憶・人格・フラグ管理
def get_user_memory(user_id):
    key = f"user:{user_id}:memory"
    return json.loads(redis.get(key)) if redis.exists(key) else {}

def save_user_memory(user_id, memory):
    redis.set(f"user:{user_id}:memory", json.dumps(memory))

def get_user_persona(user_id):
    return redis.get(f"user:{user_id}:personality") or "teteno"

def set_user_persona(user_id, persona):
    redis.set(f"user:{user_id}:personality", persona)

def get_user_flags(user_id):
    key = f"user:{user_id}:flags"
    return json.loads(redis.get(key)) if redis.exists(key) else []

def save_user_flags(user_id, flags):
    redis.set(f"user:{user_id}:flags", json.dumps(flags))

# Webhook 処理
async def handle_webhook(request):
    try:
        body = await request.text()
        signature = request.headers.get("X-Line-Signature", "")
        events = parser.parse(body, signature)

        for event in events:
            if isinstance(event, MessageEvent) and event.message.type == "text":
                user_id = event.source.user_id
                user_message = event.message.text.strip()
                print(f"🗣️ ユーザー({user_id}): {user_message}")

                memory = get_user_memory(user_id)
                persona = get_user_persona(user_id)
                flags = get_user_flags(user_id)

                # 🔄 自然文での人格切替（強化）
                if re.search(r"(カゲハ(で|にして|お願い|は|に話して|どう思う))", user_message):
                    set_user_persona(user_id, "kageha")
                    reply_text = "🖤 カゲハに切り替えたよ……"
                    reply = ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)])
                    line_bot_api.reply_message(reply)
                    return web.Response(text="OK")

                if re.search(r"(テテノ(で|にして|お願い|は|に話して|どう思う))", user_message):
                    set_user_persona(user_id, "teteno")
                    reply_text = "🌸 テテノに切り替えたよ〜"
                    reply = ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)])
                    line_bot_api.reply_message(reply)
                    return web.Response(text="OK")

                # 人格切り替え（コマンド）
                if user_message.lower() == "/teteno":
                    set_user_persona(user_id, "teteno")
                    reply_text = "🌸 テテノに切り替えたよ〜"
                elif user_message.lower() == "/kageha":
                    set_user_persona(user_id, "kageha")
                    reply_text = "🖤 カゲハに切り替えたよ……"

                # 明示的な状態フラグ登録
                elif user_message.startswith("/"):
                    flag = user_message.lstrip("/").strip()
                    if flag and flag not in flags:
                        flags.append(flag)
                        save_user_flags(user_id, flags)
                        reply_text = f"🔖 状態『{flag}』を記録したよ〜"
                    else:
                        reply_text = f"🔁 状態『{flag}』はもう覚えてるみたい〜"

                elif user_message == "/memory":
                    memory_lines = [f"{k}：{v}" for k, v in memory.items()]
                    flag_line = "状態フラグ：" + ", ".join(flags) if flags else ""
                    reply_text = "🧠 覚えてること：\n" + "\n".join(memory_lines + [flag_line])

                elif re.match(r"^(.+?)は(.+?)だよ$", user_message):
                    match = re.match(r"^(.+?)は(.+?)だよ$", user_message)
                    key, value = match.group(1).strip(), match.group(2).strip()
                    memory[key] = value
                    save_user_memory(user_id, memory)
                    reply_text = f"📌『{key} = {value}』を覚えたよ〜！"

                elif "が好き" in user_message:
                    item = user_message.split("が好き")[0].strip()
                    memory["好き"] = item
                    save_user_memory(user_id, memory)
                    reply_text = f"💾 好きなものとして『{item}』を覚えたよ〜"

                else:
                    for flag_candidate in AUTO_FLAGS:
                        if flag_candidate in user_message and flag_candidate not in flags:
                            flags.append(flag_candidate)
                            save_user_flags(user_id, flags)
                            print(f"🔖 自動で状態フラグ『{flag_candidate}』を登録したよ〜")

                    memory_text = "\n".join([f"{k}: {v}" for k, v in memory.items()])
                    flag_text = "状態フラグ：" + ", ".join(flags) if flags else ""
                    tone_instructions = [STATE_TONE_HINTS[f] for f in flags if f in STATE_TONE_HINTS]

                    system_prompt = PERSONALITY_PROMPTS.get(persona, PERSONALITY_PROMPTS["teteno"])
                    full_prompt = (
                        system_prompt + "\n"
                        + (f"以下はユーザーの記憶です：\n{memory_text}\n" if memory_text else "")
                        + (f"{flag_text}\n" if flag_text else "")
                        + ("\n".join(tone_instructions) + "\n" if tone_instructions else "")
                        + "それらを自然に会話に反映してください。"
                    )

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": full_prompt},
                            {"role": "user", "content": user_message}
                        ]
                    )
                    reply_text = response.choices[0].message.content.strip()

                reply = ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)])
                line_bot_api.reply_message(reply)

        return web.Response(text="OK")

    except InvalidSignatureError:
        print("❌ 署名エラー")
        return web.Response(status=400, text="Bad Request")
    except Exception as e:
        print("❌ その他のエラー:", e)
        return web.Response(status=500, text="Internal Server Error")

# サーバー起動
async def start_server():
    app = web.Application()
    app.router.add_post("/webhookcgi", handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBPORT)
    await site.start()
    print(f"🚀 サーバー起動: http://localhost:{WEBPORT}")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_server())
