# Persona Line Bot

これは、キャラクター人格を持つLINE Botです。  
ユーザーごとに「記憶」「人格」「状態フラグ」を保持し、自然で個性ある会話が可能です。

## 🔧 機能

- キャラ人格の切り替え（テテノ / カゲハ）
- ユーザーごとの記憶保存（「〇〇は△△だよ」形式）
- 感情・状態フラグの自動検出＆登録（例：「ねむい」「かなしい」など）
- フラグに応じた語調の変化
- OpenAI GPT-4o を使用した会話生成
- Redis による状態保存
- AIOHTTPによる非同期サーバー構築

## 🧠 人格の例

### 🌸 テテノ
- ふわふわ天然系
- 子供っぽくて優しい口調

### 🖤 カゲハ
- 皮肉屋で冷静
- 虚無系・静かなトーン

## 🚀 使用技術

- Python 3.x
- aiohttp
- OpenAI API (GPT-4o)
- Redis
- LINE Messaging API (v3)

## 🔌 実行方法

1. `.env` を用意して以下を記入：
2. 仮想環境を起動し、依存をインストール：

```bash
source venv/bin/activate
pip install -r requirements.txt