"""
国际象棋游戏模块
使用 python-chess 库实现棋盘逻辑
支持双人房间对战（含机器人）、段位系统、计时器
"""

from .engine import ChessEngine
from .room import ChessRoom
from .game_data import ChessData

# 游戏信息
GAME_INFO = {
    'id': 'chess',
    'name': '国际象棋',
    'description': '经典国际象棋，双人房间对战，支持段位系统',
    'min_players': 2,
    'max_players': 2,
    'icon': '♟️'
}
