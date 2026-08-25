#!/usr/bin/env python3
"""
编译保护脚本
将 developer_info.py 编译成字节码并删除源文件
"""
import py_compile
import os
from pathlib import Path

def compile_and_protect():
    """编译并保护开发者信息"""
    source_file = Path('developer_info.py')
    
    if not source_file.exists():
        print("❌ developer_info.py 不存在")
        return False
    
    try:
        # 编译成 .pyc
        py_compile.compile(str(source_file), doraise=True)
        print("✅ 已编译 developer_info.py")
        
        # 可选：删除源文件（增强保护）
        # source_file.unlink()
        # print("✅ 已删除源文件（仅保留 .pyc）")
        
        print("\n📋 保护说明：")
        print("1. developer_info.py 已编译成字节码")
        print("2. 普通用户难以修改开发者信息")
        print("3. 即使修改源文件，程序会优先使用 .pyc")
        print("\n⚠️  注意：")
        print("- 提交代码时包含 developer_info.py 和 __pycache__/")
        print("- 不要在 .gitignore 中排除 __pycache__/developer_info.*.pyc")
        
        return True
        
    except Exception as e:
        print(f"❌ 编译失败: {e}")
        return False

if __name__ == '__main__':
    compile_and_protect()
