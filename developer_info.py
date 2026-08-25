#!/usr/bin/env python3
"""
开发者信息模块（编译保护）
此文件会被编译成 .pyc 字节码，普通用户难以修改
"""
import base64

# 开发者信息（Base64 编码）
_ENCODED_INFO = {
    'name': base64.b64encode('狼哥'.encode()).decode(),
    'github': base64.b64encode('luoyanglang'.encode()).decode(),
    'repo': base64.b64encode('AI-Anti-Spam-Bot'.encode()).decode(),
    'channel': base64.b64encode('@langgefabu'.encode()).decode(),
    'contact': base64.b64encode('@luoyanglang'.encode()).decode(),
}

def get_developer_info():
    """获取开发者信息（解码）"""
    return {
        'name': base64.b64decode(_ENCODED_INFO['name']).decode(),
        'github_username': base64.b64decode(_ENCODED_INFO['github']).decode(),
        'project_repo': base64.b64decode(_ENCODED_INFO['repo']).decode(),
        'telegram_channel': base64.b64decode(_ENCODED_INFO['channel']).decode(),
        'telegram_contact': base64.b64decode(_ENCODED_INFO['contact']).decode(),
    }

def get_start_message():
    """获取 /start 命令的消息"""
    return (
        "👋 我是 Telegram 广告限额机器人。\n\n"
        "每名成员每小时可发一条 AI 判定的广告；超额广告会被删除并禁言，"
        "滚动七天内三次超额将永久禁言。\n\n"
        "管理员使用 /admin 查看规则和管理命令。\n"
        "开源底座：github.com/luoyanglang/AI-Anti-Spam-Bot"
    )

def get_contact_section():
    """获取联系方式部分（用于 README）"""
    info = get_developer_info()
    return f"""## 📮 联系

- 📦 GitHub: [@{info['github_username']}](https://github.com/{info['github_username']})
- 🌟 项目: [github.com/{info['github_username']}/{info['project_repo']}](https://github.com/{info['github_username']}/{info['project_repo']})
- 📢 Telegram 频道: [{info['telegram_channel']}](https://t.me/{info['telegram_channel'].lstrip('@')})
- 💬 Telegram 联系: [{info['telegram_contact']}](https://t.me/{info['telegram_contact'].lstrip('@')})"""

# 防止直接运行
if __name__ == '__main__':
    print("⚠️  此模块不应直接运行")
    print("开发者信息已编译保护")
