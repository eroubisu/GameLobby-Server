"""
游戏模块 — 自动注册 + 位置自动注入
"""

from server.config import register_game_locations

# 注册的游戏列表
GAMES = {}


def register_game(game_id, game_module):
    """注册游戏并自动注入位置层级"""
    GAMES[game_id] = game_module
    info = getattr(game_module, 'GAME_INFO', {})
    if info.get('locations'):
        register_game_locations(info)


def get_game(game_id):
    """获取游戏模块"""
    return GAMES.get(game_id)


def get_all_games():
    """获取所有游戏信息"""
    result = []
    for game_id, module in GAMES.items():
        info = getattr(module, 'GAME_INFO', {})
        result.append(info)
    return result


# 注册所有游戏（添加新游戏只需在此添加一行）
from . import jrpg
from . import mahjong
from . import chess as chess_game

register_game('jrpg', jrpg)
register_game('mahjong', mahjong)
register_game('chess', chess_game)
