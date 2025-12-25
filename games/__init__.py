"""
游戏模块
"""

# 注册的游戏列表
GAMES = {}


def register_game(game_id, game_module):
    """注册游戏"""
    GAMES[game_id] = game_module


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


# 自动注册游戏
from . import jrpg
from . import mahjong

register_game('jrpg', jrpg)
register_game('mahjong', mahjong)
