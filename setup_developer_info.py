#!/usr/bin/env python3
import yaml
import re
from pathlib import Path

def load_developer_info():
    """加载开发者信息"""
    with open('MY_INFO.yml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def update_bot_py(info):
    """更新 bot.py 中的 /start 命令"""
    bot_file = Path('bot.py')
    if not bot_file.exists():
        print("⚠️  bot.py 不存在，跳过")
        return
    
    content = bot_file.read_text(encoding='utf-8')
    
    # 构建新的联系信息
    contact_lines = []
    contact_lines.append(f"👨‍💻 开发者：{info['developer']['name']}")
    contact_lines.append(f"📦 项目：github.com/{info['developer']['github_username']}/{info['developer']['project_repo']}")
    
    if info['developer'].get('telegram_channel'):
        contact_lines.append(f"📢 频道：{info['developer']['telegram_channel']}")
    if info['developer'].get('telegram_contact'):
        contact_lines.append(f"💬 联系：{info['developer']['telegram_contact']}")
    
    contact_text = "\\n".join(contact_lines)
    
    # 使用更精确的正则，只匹配 cmd_start 函数内的 reply_text
    pattern = r'(async def cmd_start\(.*?\):.*?"""处理 /start 命令""".*?await update\.message\.reply_text\(\s*)".*?"(.*?\))'
    
    replacement = rf'\1"👋 你好！我是 AI 反垃圾广告机器人\\n\\n"'
    replacement += r'"🛡️ 功能：智能识别文字、图片中的垃圾广告\\n"'
    replacement += r'"📊 管理员使用 /admin 查看管理面板\\n"'
    replacement += r'"🎯 超级管理员可使用 /add_ad 管理广告按钮\\n\\n"'
    replacement += f'"{contact_text}\\n\\n"'
    replacement += r'"把我添加到群组并设为管理员即可开始工作!"'
    replacement += r'\2'
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if new_content != content:
        bot_file.write_text(new_content, encoding='utf-8')
        print("✅ 已更新 bot.py")
    else:
        print("⚠️  bot.py 未找到匹配的 /start 命令，跳过")


def update_readme(info):
    """更新 README.md"""
    readme_file = Path('README.md')
    content = readme_file.read_text(encoding='utf-8')
    
    # 更新徽章
    badges = f'''<p align="center">
<a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-red" alt="Python 3.10+"></a>
<a href="https://github.com/{info['developer']['github_username']}/{info['developer']['project_repo']}"><img src="https://img.shields.io/github/stars/{info['developer']['github_username']}/{info['developer']['project_repo']}" alt="GitHub stars"></a>
</p>'''
    
    # 如果已有徽章，替换；否则在标题后添加
    if '<p align="center">' in content:
        content = re.sub(r'<p align="center">.*?</p>', badges, content, flags=re.DOTALL, count=1)
    else:
        content = content.replace('# AI Anti-Spam Bot for Telegram', f'# AI Anti-Spam Bot for Telegram\n\n{badges}')
    
    # 更新联系方式
    contact_section = f'''## 📮 联系

- 📦 GitHub: [@{info['developer']['github_username']}](https://github.com/{info['developer']['github_username']})
- 🌟 项目: [github.com/{info['developer']['github_username']}/{info['developer']['project_repo']}](https://github.com/{info['developer']['github_username']}/{info['developer']['project_repo']})'''
    
    if info['developer'].get('telegram_channel'):
        contact_section += f"\n- 📢 Telegram 频道: [{info['developer']['telegram_channel']}](https://t.me/{info['developer']['telegram_channel'].lstrip('@')})"
    if info['developer'].get('telegram_contact'):
        contact_section += f"\n- 💬 Telegram 联系: [{info['developer']['telegram_contact']}](https://t.me/{info['developer']['telegram_contact'].lstrip('@')})"
    if info['developer'].get('email'):
        contact_section += f"\n- 📧 Email: {info['developer']['email']}"
    if info['developer'].get('website'):
        contact_section += f"\n- 🌐 Website: {info['developer']['website']}"
    
    # 替换联系方式部分
    if '## 📮 联系' in content:
        content = re.sub(r'## 📮 联系.*?(?=\n##|\n---|\Z)', contact_section + '\n\n', content, flags=re.DOTALL)
    else:
        content = content.replace('## 🙏 致谢', f'{contact_section}\n\n## 🙏 致谢')
    
    # 替换可能存在的占位符（用于模板项目）
    content = content.replace('your-repo', info['developer']['project_repo'])
    content = content.replace('yourusername', info['developer']['github_username'])
    content = content.replace('your-username', info['developer']['github_username'])
    
    readme_file.write_text(content, encoding='utf-8')
    print("✅ 已更新 README.md")

def update_readme_cn(info):
    """更新 README_CN.md"""
    readme_file = Path('README_CN.md')
    if not readme_file.exists():
        print("⚠️  README_CN.md 不存在，跳过")
        return
    
    content = readme_file.read_text(encoding='utf-8')
    
    # 更新徽章
    badges = f'''<p align="center">
<a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License"></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-red" alt="Python 3.10+"></a>
<a href="https://github.com/{info['developer']['github_username']}/{info['developer']['project_repo']}"><img src="https://img.shields.io/github/stars/{info['developer']['github_username']}/{info['developer']['project_repo']}" alt="GitHub stars"></a>
</p>'''
    
    if '<p align="center">' in content:
        content = re.sub(r'<p align="center">.*?</p>', badges, content, flags=re.DOTALL, count=1)
    else:
        content = content.replace('# AI 反垃圾广告机器人', f'# AI 反垃圾广告机器人\n\n{badges}')
    
    # 更新联系方式
    contact_section = f'''## 📮 联系

- 📦 GitHub: [@{info['developer']['github_username']}](https://github.com/{info['developer']['github_username']})
- 🌟 项目: [github.com/{info['developer']['github_username']}/{info['developer']['project_repo']}](https://github.com/{info['developer']['github_username']}/{info['developer']['project_repo']})'''
    
    if info['developer'].get('telegram_channel'):
        contact_section += f"\n- 📢 Telegram 频道: [{info['developer']['telegram_channel']}](https://t.me/{info['developer']['telegram_channel'].lstrip('@')})"
    if info['developer'].get('telegram_contact'):
        contact_section += f"\n- 💬 Telegram 联系: [{info['developer']['telegram_contact']}](https://t.me/{info['developer']['telegram_contact'].lstrip('@')})"
    if info['developer'].get('email'):
        contact_section += f"\n- 📧 邮箱: {info['developer']['email']}"
    if info['developer'].get('website'):
        contact_section += f"\n- 🌐 网站: {info['developer']['website']}"
    
    if '## 📮 联系' in content:
        content = re.sub(r'## 📮 联系.*?(?=\n##|\n---|\Z)', contact_section + '\n\n', content, flags=re.DOTALL)
    else:
        content = content.replace('## 🙏 致谢', f'{contact_section}\n\n## 🙏 致谢')
    
    # 替换可能存在的占位符（用于模板项目）
    content = content.replace('your-repo', info['developer']['project_repo'])
    content = content.replace('yourusername', info['developer']['github_username'])
    content = content.replace('your-username', info['developer']['github_username'])
    
    readme_file.write_text(content, encoding='utf-8')
    print("✅ 已更新 README_CN.md")

def update_deploy_md(info):
    """更新 DEPLOY.md 中的占位符"""
    deploy_file = Path('DEPLOY.md')
    if not deploy_file.exists():
        print("⚠️  DEPLOY.md 不存在，跳过")
        return
    
    content = deploy_file.read_text(encoding='utf-8')
    
    # 替换占位符
    content = content.replace('your-repo', info['developer']['project_repo'])
    content = content.replace('yourusername', info['developer']['github_username'])
    content = content.replace('your-username', info['developer']['github_username'])
    
    deploy_file.write_text(content, encoding='utf-8')
    print("✅ 已更新 DEPLOY.md")

def create_license(info):
    """创建 LICENSE 文件"""
    from datetime import datetime
    year = datetime.now().year
    
    license_text = f'''MIT License

Copyright (c) {year} {info['developer']['name']}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
    
    Path('LICENSE').write_text(license_text, encoding='utf-8')
    print("✅ 已创建 LICENSE")

def main():
    print("🚀 开始配置开发者信息...\n")
    
    # 加载信息
    try:
        info = load_developer_info()
    except FileNotFoundError:
        print("❌ 找不到 MY_INFO.yml 文件")
        print("请先复制 MY_INFO.yml.example 为 MY_INFO.yml 并填写信息")
        return
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return
    
    # 验证必填项
    required = ['name', 'github_username', 'project_repo']
    for field in required:
        if not info['developer'].get(field) or info['developer'][field].startswith('你的'):
            print(f"❌ 请先在 MY_INFO.yml 中填写 {field}")
            return
    
    print(f"📝 开发者: {info['developer']['name']}")
    print(f"📦 项目: {info['developer']['github_username']}/{info['developer']['project_repo']}\n")
    
    # 更新文件
    try:
        update_bot_py(info)
        update_readme(info)
        update_readme_cn(info)
        update_deploy_md(info)
        create_license(info)
        
        print("\n✨ 配置完成！")
        print("\n📋 下一步：")
        print("1. 检查修改的文件")
        print("2. 准备预览图片（可选）")
        print("3. git add . && git commit -m 'feat: 添加开发者信息'")
        print("4. git push")
        
    except Exception as e:
        print(f"\n❌ 配置失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
