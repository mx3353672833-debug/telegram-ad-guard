# Telegram Ad Guard 定制版

本目录包含“每人每小时一条广告、超额删除并禁言、滚动七天三次永久禁言”的定制实现。

请从 [使用说明.md](使用说明.md) 开始配置和部署。

---

# 上游项目：AI 反垃圾广告机器人 for Telegram

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
  <img src="https://img.shields.io/badge/Python-3.10+-red" alt="Python 3.10+">
  <a href="https://github.com/luoyanglang/AI-Anti-Spam-Bot"><img src="https://img.shields.io/github/stars/luoyanglang/AI-Anti-Spam-Bot" alt="GitHub stars"></a>
</p>

<p align="center">
  <b>🤖 基于 AI 的 Telegram 群组反垃圾广告机器人</b>
</p>

<p align="center">
  <a href="https://t.me/xiaolangzaibot">🎯 演示 Bot</a> •
  <a href="https://t.me/langgefabu">📢 发布频道</a> •
  <a href="https://t.me/langgepython">💬 交流群组</a> •
  <a href="README.md">English</a>
</p>

---

## ⚠️ 使用声明

**如果你使用本项目，请：**
- ✅ 保留 Bot 中的开发者信息（`/start` 命令）
- ✅ 在你的项目中注明来源
- ✅ 不要移除代码中的版权声明

**这是对开源作者最基本的尊重 🙏**

> 💡 **官方版本**：这是原作者维护的官方仓库，Fork 版本可能已过时。

---

## ✨ 特性

- 🛡️ **智能检测**：使用 AI 识别文字、图片、贴纸中的垃圾广告
- 📝 **可见内容检测**：图片说明文字和引用片段也会参与风控判断
- 🔁 **回复与转发覆盖**：回复原文和转发可见内容也会进入提取与检测
- 🎯 **多模型支持**：OpenAI、通义千问、DeepSeek 任选
- 📊 **灵活策略**：可配置检测天数、发言次数、验证次数等
- 🔓 **人性化管理**：一键解封、管理面板
- 📢 **广告按钮**：支持在封禁通知下方添加自定义广告按钮
- ⚡ **高性能**：异步处理，不阻塞消息
- 🔄 **验证机制**：通过检测的用户不再重复检测，节省 API 调用
- 🔁 **自动重试**：AI API 调用失败自动重试（3次，指数退避）
- 📝 **日志持久化**：运行日志保存到 `data/bot.log`
- 🧹 **自动清理**：封禁通知和欢迎消息支持按配置自动删除
- 📈 **运行统计**：`/stats` 命令查看检测统计数据
- 🌍 **多语言支持**：支持中文/英文切换

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config.example.yml config.yml
# 编辑 config.yml，填入你的配置
```

**必填项：**
- `telegram.token` - 你的机器人 Token（从 [@BotFather](https://t.me/BotFather) 获取）
- `telegram.owners` - 超级管理员 ID（你的 Telegram ID，可通过 [@userinfobot](https://t.me/userinfobot) 获取）
- AI 模型配置（选择一个）：
  - `openai.api_key` - OpenAI API Key
  - `qwen.api_key` - 通义千问 API Key
  - `deepseek.api_key` - DeepSeek API Key

### 3. 运行

```bash
python bot.py
```

### 4. 添加到群组

1. 把机器人添加到群组
2. 设置为管理员（需要删除消息、封禁用户权限）
3. 发送 `/start` 测试

## 📖 使用指南

### 用户命令

- `/start` - 查看机器人信息
- `/admin` - 查看管理面板（管理员）

### 管理员命令

- `/unban <用户ID>` - 解除禁言
- `/unban` (回复消息) - 解除被回复用户的禁言

### 超级管理员命令

- `/add_ad 标题|链接|过期时间|权重` - 添加广告按钮
- `/all_ad` - 查看所有广告
- `/del_ad <ID>` - 删除广告
- `/stats` - 查看运行统计（检测次数、封禁率等）

**广告按钮示例：**
```
/add_ad 官方频道|https://t.me/mychannel|2099-12-31 23:59:59|100
```

## ⚙️ 配置说明

### 基础配置

```yaml
telegram:
  token: "your-bot-token"
  owners: ["your-telegram-id"]  # 超级管理员
  allow_any_group: true          # 允许任何群组
  groups: []                     # 白名单群组（allow_any_group=false 时生效）

# 语言设置
language: "zh"  # 可选: zh / en
```

### AI 模型选择

```yaml
ai_model: "deepseek"  # 可选: openai / qwen / deepseek
```

**模型对比：**

| 模型 | 优势 | 价格 | 图片支持 |
|------|------|------|----------|
| OpenAI | 准确率高 | 较贵 | ✅ gpt-4o-mini |
| 通义千问 | 中文好 | 中等 | ✅ qwen-vl-max |
| DeepSeek | 便宜 | 最低 | ❌ |

### 检测策略

```yaml
strategy:
  joined_days: 3              # 加入天数阈值
  min_messages: 3             # 最少发言次数
  spam_score: 80              # 垃圾评分阈值 (0-100)
  verification_times: 1       # 验证通过次数限制
  check_message_count: true   # 是否检查发言次数
```

### 消息清理配置

```yaml
message:
  ban_notice_template: |
    \#封禁预警
    [{masked_name}]({user_link}) 请注意，你的用户名或发言存在违规
    ⚠️已被AI判断为高风险用户，永久封禁
    风险分数：{score}
    📋 违规原因：
    ```
    {reason}
    ```
    🤖 AI 嘲讽：
    ```
    {mock}
    ```
  delete_ban_notice_after_seconds: 30
  delete_welcome_message_after_seconds: 30
```

任一值设为 `0` 即可关闭自动删除。

`ban_notice_template` 当前支持的变量：

- `{masked_name}`
- `{user_link}`
- `{score}`
- `{reason}`
- `{mock}`
- `{user_id}`
- `{chat_id}`
- `{channel_url}`
- `{group_url}`

如果模板里出现未知变量，代码会自动回退到默认模板，不会影响封禁主流程。

## 🧪 测试

```bash
pip install -r requirements-dev.txt
pytest
```

当前首批测试已覆盖封禁通知模板渲染、MarkdownV2 安全性，以及近期出现过的关键回归风险。

当前可见内容提取已覆盖：

- 普通文本消息
- 图片 / 媒体说明文字
- 引用片段
- 回复原消息正文 / caption
- 转发消息中的可见正文 / caption

**策略说明：**

1. **joined_days**：用户加入群组超过 N 天后不再检测
2. **min_messages**：用户发言超过 N 条后不再检测（需 `check_message_count: true`）
3. **verification_times**：用户通过 N 次检测后不再检测（0=不限制）
4. **spam_score**：AI 评分超过此值才封禁

**常用场景配置：**

#### 场景1：严格模式（检测所有新用户）
```yaml
strategy:
  joined_days: 999999
  verification_times: 0
  check_message_count: false
```

#### 场景2：宽松模式（快速通过）
```yaml
strategy:
  joined_days: 3
  min_messages: 3
  verification_times: 1
  check_message_count: true
```

#### 场景3：平衡模式（推荐）
```yaml
strategy:
  joined_days: 7
  min_messages: 5
  verification_times: 2
  check_message_count: true
```

## 🎨 广告按钮功能

封禁通知会显示自定义按钮：

```
🚫 检测到违规内容
...
⚠️ 该用户已被永久封禁

[🔓 解除禁言]  ← 管理员可点击
[📢 官方频道]  ← 你的广告
[💎 VIP 群组]  ← 你的广告
```

**管理广告：**
```bash
# 添加
/add_ad 官方频道|https://t.me/channel|2099-12-31 23:59:59|100

# 查看
/all_ad

# 删除
/del_ad 1
```

## 🐳 Docker 部署

```bash
# 1. 编辑配置
cp config.example.yml config.yml
vim config.yml

# 2. 启动
docker compose up -d

# 3. 查看日志
docker compose logs -f
```

## 📊 工作原理

```
用户发文字 / 图片 / 贴纸
    ↓
检查是否为管理员 → 是 → 放行
    ↓ 否
检查是否需要检测 → 否 → 放行
    ↓ 是
提取可见内容
    ↓
图片消息若包含说明文字或引用片段 → 先做文字预检
    ↓
AI 分析内容
    ↓
评分 < 阈值 → 放行 + 验证次数+1
    ↓
评分 ≥ 阈值 → 封禁 + 删除消息 + 发送通知
```

## 🔧 高级功能

### 自定义 Telegram API

如果你有自建 Telegram API 服务器：

```bash
export TELEGRAM_API_URL="https://your-api-server.com"
python bot.py
```

### 数据库位置

默认：`data/bot.db`

修改：
```yaml
database:
  path: "custom/path/bot.db"
```

## 📮 联系

- 👨‍💻 开发者：狼哥 ([@luoyanglang](https://t.me/luoyanglang))
- 📦 GitHub: [@luoyanglang](https://github.com/luoyanglang)
- 🌟 官方项目: [github.com/luoyanglang/AI-Anti-Spam-Bot](https://github.com/luoyanglang/AI-Anti-Spam-Bot)
- 📢 发布频道: [@langgefabu](https://t.me/langgefabu)
- 💬 交流群组: [@langgepython](https://t.me/langgepython)
- 🎯 演示 Bot: [@xiaolangzaibot](https://t.me/xiaolangzaibot) - 可拉入群组测试效果！

## 💰 支持项目

如果本项目对您有帮助，欢迎支持开发者：

- ⭐ 给项目一个 Star
- 📢 分享给更多需要的人
- 🐛 反馈 Bug 和建议
- ☕ [请作者喝杯咖啡](SPONSOR.md)

> 您的支持是项目持续更新的动力

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

感谢所有贡献者和使用者的支持！

**特别提醒：**
- 本项目采用 MIT 协议开源
- 允许商业使用，但请保留开发者信息
- 如果你修改或分发本项目，请注明原作者
- 这是对开源精神的尊重，也是项目持续发展的动力

---

<p align="center">
  ⭐ 如果这个项目对你有帮助，请给个 Star！<br>
  💰 支持开发者，让项目持续更新！
</p>
