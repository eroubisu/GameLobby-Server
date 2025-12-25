"""
服务器配置
"""

import os

# 版本号（从 version.txt 读取，由 build_server.py 打包时生成）
def _get_server_version():
    """从 version.txt 读取版本号"""
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'version.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except:
        pass
    return "dev"

SERVER_VERSION = _get_server_version()

# 网络配置
HOST = '0.0.0.0'
PORT = 5555

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
USERS_DIR = os.path.join(DATA_DIR, 'users')
CHAT_LOG_DIR = os.path.join(DATA_DIR, 'chat_logs')
CHAT_HISTORY_DIR = os.path.join(CHAT_LOG_DIR, 'history')

# 系统维护时间（北京时间凌晨4点）
MAINTENANCE_HOUR = 4

# 位置层级定义
# 格式: {位置: (显示名称, 父位置)}
LOCATION_HIERARCHY = {
    'lobby': ('游戏大厅', None),
    'profile': ('个人资料', 'lobby'),
    'jrpg': ('JRPG', 'lobby'),
    'mahjong': ('麻将', 'lobby'),
    'mahjong_room': ('房间', 'mahjong'),
    'mahjong_playing': ('对局中', 'mahjong_room'),
}

# 确保目录存在
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(CHAT_LOG_DIR, exist_ok=True)
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
