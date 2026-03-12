"""用户属性模板与段位系统 — 框架级定义

所有静态数据从 JSON 文件加载：
  - ranks.json   — 默认段位阶梯（通用/后备）
  - titles.json  — 系统/社交/活动头衔
  - items.json   — 系统物品

每个游戏可在自己目录下放置同名 JSON 覆盖/扩展：
  - games/xxx/ranks.json        — 游戏专属段位体系
  - games/xxx/titles.json       — 游戏专属头衔
  - games/xxx/items.json        — 游戏专属物品
  - games/xxx/player_data.json  — 默认玩家数据
均由 register_game() 自动加载。
"""

from datetime import datetime
import copy
import json
import os


# ══════════════════════════════════════════════════
#  从 JSON 加载框架级静态数据
# ══════════════════════════════════════════════════

_dir = os.path.dirname(__file__)


def _load_json(filename):
    path = os.path.join(_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


_ranks_data = _load_json('ranks.json')
RANKS = _ranks_data['ranks']
RANK_ORDER = _ranks_data['rank_order']

_titles_data = _load_json('titles.json')
TITLE_LIBRARY = _titles_data['titles']
TITLE_SOURCES = _titles_data['sources']

_items_data = _load_json('items.json')
ITEM_LIBRARY = _items_data['items']
ITEM_SOURCES = _items_data['sources']


# ══════════════════════════════════════════════════
#  注入内部注册表
# ══════════════════════════════════════════════════

_GAME_PLAYER_DEFAULTS = {}   # {game_id: {默认玩家数据}}
_RANK_TO_TITLE = {}           # {rank_id: title_id}
_GAME_RANKS = {}              # {game_id: {'ranks': {...}, 'rank_order': [...]}}


# ══════════════════════════════════════════════════
#  注入接口（由 games/__init__.py::register_game 调用）
# ══════════════════════════════════════════════════

def register_game_titles(titles: dict) -> None:
    TITLE_LIBRARY.update(titles)


def register_game_title_sources(sources: dict) -> None:
    TITLE_SOURCES.update(sources)


def register_game_items(items: dict) -> None:
    ITEM_LIBRARY.update(items)


def register_game_item_sources(sources: dict) -> None:
    ITEM_SOURCES.update(sources)


def register_game_player_defaults(game_id: str, defaults: dict) -> None:
    _GAME_PLAYER_DEFAULTS[game_id] = defaults


def register_rank_titles(mapping: dict) -> None:
    _RANK_TO_TITLE.update(mapping)


def register_game_ranks(game_id: str, ranks: dict, rank_order: list) -> None:
    """注入游戏专属段位体系（覆盖框架默认）"""
    _GAME_RANKS[game_id] = {'ranks': ranks, 'rank_order': rank_order}


# ══════════════════════════════════════════════════
#  段位查询（支持 game_type 切换段位体系）
# ══════════════════════════════════════════════════

def _get_ranks(game_type=None):
    if game_type and game_type in _GAME_RANKS:
        return _GAME_RANKS[game_type]['ranks']
    return RANKS


def get_rank_order(game_type=None):
    if game_type and game_type in _GAME_RANKS:
        return _GAME_RANKS[game_type]['rank_order']
    return RANK_ORDER


def get_rank_info(rank_id, game_type=None):
    ranks = _get_ranks(game_type)
    order = get_rank_order(game_type)
    return ranks.get(rank_id, ranks[order[0]])


def get_rank_name(rank_id, game_type=None):
    return get_rank_info(rank_id, game_type)['name']


def get_rank_index(rank_id, game_type=None):
    order = get_rank_order(game_type)
    try:
        return order.index(rank_id)
    except ValueError:
        return 0


def calculate_rank_change(current_rank, points_change, game_type=None):
    """计算段位变化。Returns: (new_rank, new_points, promoted, demoted)"""
    rank_info = get_rank_info(current_rank, game_type)
    rank_idx = get_rank_index(current_rank, game_type)
    order = get_rank_order(game_type)

    new_points = max(0, points_change)
    promoted = False
    demoted = False
    new_rank = current_rank

    if rank_info['points_up'] is not None and new_points >= rank_info['points_up']:
        if rank_idx < len(order) - 1:
            new_rank = order[rank_idx + 1]
            new_points = 0
            promoted = True
    elif rank_info['points_down'] is not None and new_points < rank_info['points_down']:
        if rank_idx > 0:
            prev_rank = order[rank_idx - 1]
            prev_tier = get_rank_info(prev_rank, game_type)['tier']
            current_tier = rank_info['tier']
            if current_tier > 2 or (current_tier == 2 and prev_tier == 2):
                new_rank = prev_rank
                new_points = get_rank_info(new_rank, game_type)['points_up'] // 2
                demoted = True

    return new_rank, new_points, promoted, demoted


# ══════════════════════════════════════════════════
#  头衔 / 物品查询
# ══════════════════════════════════════════════════

def get_title_info(title_id):
    return TITLE_LIBRARY.get(title_id)


def get_title_name(title_id):
    info = TITLE_LIBRARY.get(title_id)
    if info:
        return info['name']
    return title_id


def get_titles_by_source(source):
    return {k: v for k, v in TITLE_LIBRARY.items() if v['source'] == source}


def get_all_title_names():
    return {info['name']: tid for tid, info in TITLE_LIBRARY.items()}


def grant_title(player_data, title_id):
    titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
    titles.setdefault('owned', [])
    if title_id not in titles['owned']:
        titles['owned'].append(title_id)
    player_data['titles'] = titles


def get_item_info(item_id):
    return ITEM_LIBRARY.get(item_id)


def get_item_name(item_id):
    info = ITEM_LIBRARY.get(item_id)
    if info:
        return info['name']
    return item_id


def get_title_id_from_rank(rank_id):
    return _RANK_TO_TITLE.get(rank_id)


# ══════════════════════════════════════════════════
#  默认用户属性模板
# ══════════════════════════════════════════════════

def get_default_user_template(name="", password_hash=""):
    template = {
        'name': name,
        'password_hash': password_hash,
        'created_at': datetime.now().isoformat(),

        'level': 1,
        'exp': 0,
        'gold': 100,
        'accessory': None,
        'avatar': None,

        'social_stats': {
            'login_days': 0,
            'last_login_date': '',
            'chat_messages': 0,
            'invites_sent': 0,
        },

        'inventory': {
            'rename_card': 2,
        },

        'titles': {
            'owned': ['newcomer'],
            'displayed': ['newcomer'],
        },

        'window_layout': None,
    }

    for game_id, defaults in _GAME_PLAYER_DEFAULTS.items():
        template[game_id] = copy.deepcopy(defaults)

    return template


# ══════════════════════════════════════════════════
#  数据完整性
# ══════════════════════════════════════════════════

def ensure_user_schema(user_data):
    """确保用户数据包含所有必需属性。Returns: (data, changes)"""
    if not user_data:
        return None, []

    template = get_default_user_template()
    changes = []

    # ── 历史数据迁移 ──

    if 'rename_cards' in user_data and 'inventory' not in user_data:
        user_data['inventory'] = {'rename_card': user_data.pop('rename_cards', 2)}
        changes.append("迁移: rename_cards -> inventory.rename_card")
    elif 'rename_cards' in user_data:
        user_data.pop('rename_cards', None)
        changes.append("删除: 旧字段 rename_cards")

    if 'title' in user_data:
        user_data.pop('title', None)
        changes.append("删除: 旧字段 title")

    _name_to_id = {info['name']: tid for tid, info in TITLE_LIBRARY.items()}
    titles = user_data.get('titles')
    if titles:
        for key in ('owned', 'displayed'):
            lst = titles.get(key, [])
            migrated = []
            for t in lst:
                if t in _name_to_id:
                    migrated.append(_name_to_id[t])
                    changes.append(f"迁移头衔: '{t}' -> '{_name_to_id[t]}'")
                else:
                    migrated.append(t)
            titles[key] = migrated

    games_data = user_data.get('games', {})
    if isinstance(games_data, dict) and 'jrpg' in games_data:
        jrpg_data = games_data.pop('jrpg')
        if 'gold' in jrpg_data:
            user_data['gold'] = user_data.get('gold', 0) + jrpg_data.pop('gold', 0)
            changes.append("迁移: games.jrpg.gold -> gold")
        if 'jrpg' not in user_data:
            user_data['jrpg'] = jrpg_data
            changes.append("迁移: games.jrpg -> jrpg")
        if not games_data:
            user_data.pop('games', None)
            changes.append("删除: 空的 games 字段")

    # ── 递归补全缺失字段 ──

    def merge_dict(target, source, path=""):
        for key, default_value in source.items():
            current_path = f"{path}.{key}" if path else key
            if key in ('name', 'password_hash', 'created_at', 'avatar'):
                continue
            if key not in target:
                target[key] = copy.deepcopy(default_value)
                changes.append(f"添加: {current_path}")
            elif isinstance(default_value, dict) and isinstance(target[key], dict):
                merge_dict(target[key], default_value, current_path)

    merge_dict(user_data, template)
    return user_data, changes
