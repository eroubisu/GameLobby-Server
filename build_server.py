"""
服务器打包脚本
将服务器文件打包成带版本号的zip包
在 Windows 上打包，在 Ubuntu 上用 Python 运行
输出: server_v版本号.zip
"""

import os
import zipfile

# ============ 版本号配置 ============
VERSION = "1.0.0"
# ===================================

# 需要打包的文件
SERVER_FILES = [
    'server.py',
    'server/__init__.py',
    'server/chat_server.py',
    'server/config.py',
    'server/lobby_engine.py',
    'server/player_manager.py',
    'server/user_schema.py',
    'server/version.txt',  # 打包时自动生成
    'games/__init__.py',
    'games/mahjong/__init__.py',
    'games/mahjong/actions.py',
    'games/mahjong/bot_ai.py',
    'games/mahjong/engine.py',
    'games/mahjong/game_data.py',
    'games/mahjong/help.txt',
    'games/mahjong/room.py',
    'games/mahjong/scoring.py',
    'games/mahjong/tenpai.py',
    'games/mahjong/yaku.py',
    'games/jrpg/__init__.py',
    'games/jrpg/config.json',
    'games/jrpg/game_data.py',
    'games/jrpg/game_engine.py',
    'games/jrpg/help.txt',
]

# 数据目录（不打包，在云端单独管理）
# data/users/        - 用户数据
# data/chat_logs/    - 聊天日志


def build_server():
    """打包服务器"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    output_name = f"server_v{VERSION}"
    output_zip = os.path.join(base_dir, f"{output_name}.zip")
    
    print("=" * 50)
    print(f"  游戏大厅服务器打包工具 v{VERSION}")
    print("=" * 50)
    print()
    
    # 生成 version.txt
    version_file = os.path.join(base_dir, 'server', 'version.txt')
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(VERSION)
    print(f"生成版本文件: server/version.txt")
    
    # 删除旧文件
    if os.path.exists(output_zip):
        os.remove(output_zip)
    
    print(f"正在打包服务器...")
    print()
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加服务器文件
        for file_path in SERVER_FILES:
            full_path = os.path.join(base_dir, file_path)
            if os.path.exists(full_path):
                zf.write(full_path, file_path)
                print(f"  添加: {file_path}")
            else:
                print(f"  警告: {file_path} 不存在，跳过")
    
    print()
    print("=" * 50)
    print("  ✓ 打包成功!")
    print("=" * 50)
    print(f"  输出文件: {output_zip}")
    print(f"  文件大小: {os.path.getsize(output_zip) / 1024:.1f} KB")
    print()
    
    # 删除临时的 version.txt
    if os.path.exists(version_file):
        os.remove(version_file)
        print(f"✓ 已删除 server/version.txt")
    
    return output_zip


if __name__ == '__main__':
    build_server()
    input("按回车键退出...")
