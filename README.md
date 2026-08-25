# Telegram Ad Guard — customized build

This build defaults to deterministic, per-group keyword moderation with no AI API required. Blocked words delete the message and permanently mute the sender; ad words use a one-per-user rolling-hour quota, a one-hour mute for over-quota ads, and a permanent mute on the third rolling-seven-day violation. Permanent mutes include an in-group appeal flow.

See [使用说明.md](使用说明.md) for the Chinese setup and group installation guide.

---

# Upstream: AI Anti-Spam Bot for Telegram

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
  <img src="https://img.shields.io/badge/Python-3.10+-red" alt="Python 3.10+">
  <a href="https://github.com/luoyanglang/AI-Anti-Spam-Bot"><img src="https://img.shields.io/github/stars/luoyanglang/AI-Anti-Spam-Bot" alt="GitHub stars"></a>
</p>

<p align="center">
  <b>🤖 AI-powered anti-spam bot for Telegram groups</b>
</p>

<p align="center">
  <a href="https://t.me/xiaolangzaibot">🎯 Demo Bot</a> •
  <a href="https://t.me/langgefabu">📢 Channel</a> •
  <a href="https://t.me/langgepython">💬 Group</a> •
  <a href="README_CN.md">简体中文</a>
</p>

---

## ⚠️ Usage Notice

**If you use this project, please:**
- ✅ Keep the developer information in the Bot (`/start` command)
- ✅ Credit the source in your project
- ✅ Do not remove copyright notices from the code

**This is the most basic respect for open source authors 🙏**

> 💡 **Official Version**: This is the official repository maintained by the original author. Forks may be outdated.

---

## ✨ Features

- 🛡️ **No-AI Keyword Mode**: Deterministic moderation without API cost or model errors
- 📢 **Per-group Ad Words**: One matched ad per user per rolling hour
- ⛔ **Per-group Blocked Words**: Immediate deletion and permanent mute
- 📨 **Appeals**: Muted users can submit an in-group appeal for admin approval
- 🔨 **Manual Moderation**: Admin `/mute` and `/unban` commands
- 📝 **Visible-Content Checks**: Image captions and quoted snippets are included in moderation
- 🔁 **Reply & Forward Coverage**: Reply content and forwarded visible content are included in extraction
- 🎯 **Multi-Model Support**: Choose from Kimi, OpenAI, Qwen, or DeepSeek
- 🚫 **Per-group Blocked Words**: Add, remove, and list immediate-delete phrases from Telegram admin commands
- 📊 **Flexible Strategy**: Configurable detection days, message count, verification times
- 🔓 **User-Friendly Management**: One-click unban, admin panel
- 📢 **Ad Buttons**: Custom advertisement buttons on ban notifications
- ⚡ **High Performance**: Async processing, non-blocking
- 🔄 **Verification System**: Verified users skip future checks, saving API calls
- 🔁 **Auto Retry**: AI API calls auto-retry on failure (3 times, exponential backoff)
- 📝 **Persistent Logs**: Runtime logs saved to `data/bot.log`
- 🧹 **Auto Cleanup**: Ban notices and welcome messages can auto-delete after a configurable delay
- 📈 **Statistics**: `/stats` command to view detection statistics
- 🌍 **Multi-Language**: Support for Chinese/English

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp config.example.yml config.yml
# Edit config.yml with your settings
```

**Required in the default `keywords` mode:**
- `telegram.token` - Your bot token (from [@BotFather](https://t.me/BotFather))
- `telegram.owners` - Optional super admin ID

AI keys are only required when `detection.mode: "ai"`:
  - `openai.api_key` - OpenAI API Key
  - `qwen.api_key` - Qwen API Key
  - `deepseek.api_key` - DeepSeek API Key
  - `kimi.api_key` - Kimi Code API Key

### 3. Run

```bash
python bot.py
```

### 4. Add to Group

1. Add the bot to your group
2. Set as admin (requires delete messages & ban users permissions)
3. Send `/start` to test

## 📖 Usage Guide

### User Commands

- `/start` - View bot info
- `/admin` - View admin panel (admins only)

### Admin Commands

- `/unban <user_id>` - Unban user
- `/unban` (reply to message) - Unban the replied user
- `/mute <user_id>` - Permanently mute a user
- `/mute` (reply to message) - Permanently mute the replied user
- `/add_adword <word or phrase>` - Add an hourly-quota ad phrase
- `/del_adword <word or phrase>` - Remove an ad phrase
- `/adwords` - List ad phrases for the current group
- `/add_blockword <word or phrase>` - Add a blocked phrase for the current group
- `/del_blockword <word or phrase>` - Remove a blocked phrase for the current group
- `/blockwords` - List blocked phrases for the current group

### Super Admin Commands

- `/add_ad title|link|expiry|weight` - Add ad button
- `/all_ad` - View all ads
- `/del_ad <ID>` - Delete ad
- `/stats` - View runtime statistics (detection count, ban rate, etc.)

**Ad Button Example:**
```
/add_ad Official Channel|https://t.me/mychannel|2099-12-31 23:59:59|100
```


## ⚙️ Configuration

### Basic Config

```yaml
telegram:
  token: "your-bot-token"
  owners: ["your-telegram-id"]  # Super admins
  allow_any_group: true          # Allow any group
  groups: []                     # Whitelist groups (when allow_any_group=false)

# Language setting
language: "zh"  # Options: zh / en
```

### Detection Mode

```yaml
detection:
  mode: "keywords"  # No AI API required; use "ai" for optional model detection
```

### Optional AI Model Selection

```yaml
ai_model: "kimi"  # Options: kimi / openai / qwen / deepseek
```

**Model Comparison:**

| Model | Advantage | Price | Image Support |
|-------|-----------|-------|---------------|
| OpenAI | High accuracy | Expensive | ✅ gpt-4o-mini |
| Qwen | Good for Chinese | Medium | ✅ qwen-vl-max |
| DeepSeek | Cheap | Lowest | ❌ |

### Detection Strategy

```yaml
strategy:
  joined_days: 3              # Days since joining threshold
  min_messages: 3             # Minimum message count
  spam_score: 80              # Spam score threshold (0-100)
  verification_times: 1       # Verification pass limit
  check_message_count: true   # Check message count
```

### Message Cleanup

```yaml
message:
  ban_notice_template: |
    \#BanAlert
    [{masked_name}]({user_link}) Warning: Your username or message violates the rules
    ⚠️ Identified as high-risk user by AI, permanently banned
    Risk score: {score}
    📋 Reason:
    ```
    {reason}
    ```
    🤖 AI roast:
    ```
    {mock}
    ```
  delete_ban_notice_after_seconds: 30
  delete_welcome_message_after_seconds: 30
```

Set either value to `0` to disable auto deletion.

Supported `ban_notice_template` variables:

- `{masked_name}`
- `{user_link}`
- `{score}`
- `{reason}`
- `{mock}`
- `{user_id}`
- `{chat_id}`
- `{channel_url}`
- `{group_url}`

Unknown placeholders will fall back to the default template instead of breaking moderation.

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The first test baseline covers ban-notice template rendering, MarkdownV2 safety, and recent moderation regressions.

Current visible-content extraction covers:

- Text messages
- Photo/media captions
- Quoted snippets
- Replied message text/caption
- Forwarded visible text/caption

**Strategy Explanation:**

1. **joined_days**: Users who joined more than N days ago skip detection
2. **min_messages**: Users with more than N messages skip detection (requires `check_message_count: true`)
3. **verification_times**: Users who passed N verifications skip detection (0=unlimited)
4. **spam_score**: Only ban when AI score exceeds this value

**Common Scenarios:**

#### Scenario 1: Strict Mode (Check all new users)
```yaml
strategy:
  joined_days: 999999
  verification_times: 0
  check_message_count: false
```

#### Scenario 2: Relaxed Mode (Quick pass)
```yaml
strategy:
  joined_days: 3
  min_messages: 3
  verification_times: 1
  check_message_count: true
```

#### Scenario 3: Balanced Mode (Recommended)
```yaml
strategy:
  joined_days: 7
  min_messages: 5
  verification_times: 2
  check_message_count: true
```

## 🎨 Ad Button Feature

Ban notifications display custom buttons:

```
🚫 Spam Detected
...
⚠️ User has been permanently banned

[🔓 Unban]            ← Admins can click
[📢 Official Channel] ← Your ad
[💎 VIP Group]        ← Your ad
```

**Manage Ads:**
```bash
# Add
/add_ad Official Channel|https://t.me/channel|2099-12-31 23:59:59|100

# View
/all_ad

# Delete
/del_ad 1
```

## 🐳 Docker Deployment

```bash
# 1. Edit config
cp config.example.yml config.yml
vim config.yml

# 2. Start
docker compose up -d

# 3. View logs
docker compose logs -f
```

## 📊 How It Works

```
User sends text / photo / sticker
    ↓
Check if admin → Yes → Allow
    ↓ No
Check if needs detection → No → Allow
    ↓ Yes
Extract visible content
    ↓
Photo message with caption / quote → Text pre-check first
    ↓
AI analyzes content
    ↓
Score < threshold → Allow + verification count +1
    ↓
Score ≥ threshold → Ban + delete message + send notification
```

## 🔧 Advanced Features

### Custom Telegram API

If you have a self-hosted Telegram API server:

```bash
export TELEGRAM_API_URL="https://your-api-server.com"
python bot.py
```

### Database Location

Default: `data/bot.db`

Modify:
```yaml
database:
  path: "custom/path/bot.db"
```

## 📮 Contact

- 👨‍💻 Developer: 狼哥 ([@luoyanglang](https://t.me/luoyanglang))
- 📦 GitHub: [@luoyanglang](https://github.com/luoyanglang)
- 🌟 Official Project: [github.com/luoyanglang/AI-Anti-Spam-Bot](https://github.com/luoyanglang/AI-Anti-Spam-Bot)
- 📢 Official Channel: [@langgefabu](https://t.me/langgefabu)
- 💬 Discussion Group: [@langgepython](https://t.me/langgepython)
- 🎯 Demo Bot: [@xiaolangzaibot](https://t.me/xiaolangzaibot) - Add to your group to test!

## 💰 Support

If this project helps you, consider supporting the developer:

- ⭐ Give this project a Star on GitHub
- 📢 Share with others who might need it
- 🐛 Report bugs and suggest features
- ☕ [Buy me a coffee](SPONSOR.md)

> Your support keeps this project alive

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

MIT License

## 🙏 Acknowledgments

Thanks to all contributors and users for your support!

**Important Notice:**
- This project is open source under the MIT License
- Commercial use is allowed, but please keep the developer information
- If you modify or distribute this project, please credit the original author
- This is respect for open source spirit and motivation for continuous development

---

<p align="center">
  ⭐ If this project helps you, please give it a Star!<br>
  💰 Support the developer to keep this project alive!
</p>
