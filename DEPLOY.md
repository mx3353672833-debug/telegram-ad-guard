# 部署指南

> 💡 **官方项目**: [github.com/luoyanglang/AI-Anti-Spam-Bot](https://github.com/luoyanglang/AI-Anti-Spam-Bot)  
> 📢 **发布频道**: [@langgefabu](https://t.me/langgefabu)  
> 💬 **交流群组**: [@langgepython](https://t.me/langgepython)  
> 🎯 **演示 Bot**: [@xiaolangzaibot](https://t.me/xiaolangzaibot)

---

## 获取必要信息

### 1. 创建 Telegram Bot

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置名称和用户名
4. 获取 Bot Token（格式：`123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）

### 2. 获取你的 Telegram ID

1. 在 Telegram 搜索 [@userinfobot](https://t.me/userinfobot)
2. 发送 `/start`
3. 获取你的 ID（纯数字，如：`123456789`）

### 3. 获取 AI API Key

选择一个 AI 服务商：

**OpenAI**
- 访问 https://platform.openai.com/api-keys
- 创建 API Key

**通义千问（推荐国内用户）**
- 访问 https://dashscope.aliyun.com
- 开通服务并创建 API Key

**DeepSeek（性价比高）**
- 访问 https://platform.deepseek.com
- 创建 API Key

## Docker 部署（推荐）

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 克隆项目
git clone https://github.com/luoyanglang/AI-Anti-Spam-Bot.git
cd AI-Anti-Spam-Bot/python-version

# 3. 复制配置文件
cp config.example.yml config.yml

# 4. 编辑配置
nano config.yml
```

配置示例：
```yaml
telegram:
  token: "你的Bot Token"
  owners: ["你的Telegram ID"]
  allow_any_group: true

ai_model: "deepseek"

deepseek:
  api_key: "你的DeepSeek API Key"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

strategy:
  joined_days: 3
  min_messages: 3
  spam_score: 80
```

```bash
# 5. 启动
docker-compose up -d

# 6. 查看日志
docker-compose logs -f

# 停止
docker-compose down

# 重启
docker-compose restart
```

## 直接部署

```bash
# 1. 安装 Python 3.11+
python3 --version

# 2. 克隆项目
git clone https://github.com/luoyanglang/AI-Anti-Spam-Bot.git
cd AI-Anti-Spam-Bot/python-version

# 3. 安装依赖
pip3 install -r requirements.txt

# 4. 配置
cp config.example.yml config.yml
nano config.yml

# 5. 运行
python3 bot.py

# 后台运行（使用 screen 或 tmux）
screen -S bot
python3 bot.py
# Ctrl+A+D 退出 screen

# 重新连接
screen -r bot
```

## 使用 systemd（Linux 服务）

创建服务文件：
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

内容：
```ini
[Unit]
Description=Telegram Anti-Spam Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/AI-Anti-Spam-Bot/python-version
ExecStart=/usr/bin/python3 /path/to/AI-Anti-Spam-Bot/python-version/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## 添加 Bot 到群组

1. 将 Bot 添加到你的群组
2. 在群组设置中，将 Bot 设为管理员
3. 授予权限：
   - ✅ 删除消息
   - ✅ 封禁用户
4. Bot 会自动开始工作

## 测试

1. 让一个新账号加入群组
2. 新账号发送测试消息
3. 查看 Bot 日志确认检测正常

## 故障排查

**Bot 不响应**
- 检查 Token 是否正确
- 查看日志：`docker-compose logs -f`

**AI 检测失败**
- 检查 API Key 是否有效
- 检查网络连接
- 查看日志中的错误信息

**无法封禁用户**
- 确认 Bot 是群组管理员
- 确认 Bot 有封禁用户权限
