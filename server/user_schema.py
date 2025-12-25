"""
用户属性模板与完整性检查
仿照雀魂的段位系统设计
"""

from datetime import datetime

# ==================== 雀魂段位系统 ====================

# 段位定义 (段位ID, 段位名称, 段位星级, 升段所需点数, 降段保护点数)
RANKS = {
    # 初心 - 不会降段
    'novice_1': {'name': '初心一', 'tier': 1, 'stars': 1, 'points_up': 20, 'points_down': None},
    'novice_2': {'name': '初心二', 'tier': 1, 'stars': 2, 'points_up': 20, 'points_down': None},
    'novice_3': {'name': '初心三', 'tier': 1, 'stars': 3, 'points_up': 20, 'points_down': None},
    
    # 雀士 - 不会降回初心
    'adept_1': {'name': '雀士一', 'tier': 2, 'stars': 1, 'points_up': 80, 'points_down': None},
    'adept_2': {'name': '雀士二', 'tier': 2, 'stars': 2, 'points_up': 80, 'points_down': 0},
    'adept_3': {'name': '雀士三', 'tier': 2, 'stars': 3, 'points_up': 80, 'points_down': 0},
    
    # 雀杰
    'expert_1': {'name': '雀杰一', 'tier': 3, 'stars': 1, 'points_up': 100, 'points_down': 0},
    'expert_2': {'name': '雀杰二', 'tier': 3, 'stars': 2, 'points_up': 100, 'points_down': 0},
    'expert_3': {'name': '雀杰三', 'tier': 3, 'stars': 3, 'points_up': 100, 'points_down': 0},
    
    # 雀豪
    'master_1': {'name': '雀豪一', 'tier': 4, 'stars': 1, 'points_up': 200, 'points_down': 0},
    'master_2': {'name': '雀豪二', 'tier': 4, 'stars': 2, 'points_up': 200, 'points_down': 0},
    'master_3': {'name': '雀豪三', 'tier': 4, 'stars': 3, 'points_up': 200, 'points_down': 0},
    
    # 雀圣
    'saint_1': {'name': '雀圣一', 'tier': 5, 'stars': 1, 'points_up': 400, 'points_down': 0},
    'saint_2': {'name': '雀圣二', 'tier': 5, 'stars': 2, 'points_up': 400, 'points_down': 0},
    'saint_3': {'name': '雀圣三', 'tier': 5, 'stars': 3, 'points_up': 400, 'points_down': 0},
    
    # 魂天 - 最高段位
    'celestial': {'name': '魂天', 'tier': 6, 'stars': 0, 'points_up': None, 'points_down': 0},
}

# 段位顺序（用于升降段）
RANK_ORDER = [
    'novice_1', 'novice_2', 'novice_3',
    'adept_1', 'adept_2', 'adept_3',
    'expert_1', 'expert_2', 'expert_3',
    'master_1', 'master_2', 'master_3',
    'saint_1', 'saint_2', 'saint_3',
    'celestial'
]

# 段位场类型（日语读法）
# 友人场: yuujin (友人)
# 铜之间: dou (銅)
# 银之间: gin (銀)  
# 金之间: kin (金)
# 玉之间: gyoku (玉)
# 王座之间: ouza (王座)
MATCH_TYPES = {
    'yuujin': {'name': '友人場', 'name_cn': '友人场', 'ranked': False, 'min_rank': None},
    'dou': {'name': '銅の間', 'name_cn': '铜之间', 'ranked': True, 'min_rank': 'novice_1'},
    'gin': {'name': '銀の間', 'name_cn': '银之间', 'ranked': True, 'min_rank': 'adept_1'},
    'kin': {'name': '金の間', 'name_cn': '金之间', 'ranked': True, 'min_rank': 'expert_1'},
    'gyoku': {'name': '玉の間', 'name_cn': '玉之间', 'ranked': True, 'min_rank': 'master_1'},
    'ouza': {'name': '王座の間', 'name_cn': '王座之间', 'ranked': True, 'min_rank': 'saint_1'},
}

# 游戏模式（日语读法）
# 东风战: tonpu (東風)
# 半庄战: hanchan (半荘)
GAME_MODES = {
    'tonpu': {'name': '東風戦', 'name_cn': '东风战', 'rounds': 1},
    'hanchan': {'name': '半荘戦', 'name_cn': '半庄战', 'rounds': 2},
}

# 段位场入场限制 (玩家最低段位要求) - 保留兼容
MATCH_REQUIREMENTS = {
    'dou': 'novice_1',       # 铜之间 - 初心以上
    'gin': 'adept_1',        # 银之间 - 雀士以上  
    'kin': 'expert_1',       # 金之间 - 雀杰以上
    'gyoku': 'master_1',     # 玉之间 - 雀豪以上
    'ouza': 'saint_1',       # 王座之间 - 雀圣以上
}

# 段位点数变化表 (根据排名和段位等级)
# 格式: {tier: {place: points_change}}
RANK_POINTS_EAST = {  # 东风战
    1: {1: 20, 2: 10, 3: 0, 4: 0},      # 初心
    2: {1: 40, 2: 10, 3: -10, 4: -20},  # 雀士
    3: {1: 50, 2: 20, 3: -15, 4: -30},  # 雀杰
    4: {1: 60, 2: 20, 3: -20, 4: -40},  # 雀豪
    5: {1: 70, 2: 25, 3: -25, 4: -50},  # 雀圣
    6: {1: 80, 2: 30, 3: -30, 4: -60},  # 魂天
}

RANK_POINTS_SOUTH = {  # 南风战 (点数翻倍)
    1: {1: 40, 2: 20, 3: 0, 4: 0},
    2: {1: 80, 2: 20, 3: -20, 4: -40},
    3: {1: 100, 2: 40, 3: -30, 4: -60},
    4: {1: 120, 2: 40, 3: -40, 4: -80},
    5: {1: 140, 2: 50, 3: -50, 4: -100},
    6: {1: 160, 2: 60, 3: -60, 4: -120},
}

# ==================== 头衔库 ====================
# 所有可获得的头衔定义
# 格式: { 'id': {'name': 显示名, 'source': 来源, 'desc': 描述, 'condition': 获得条件} }

TITLE_LIBRARY = {
    # ===== 基础头衔 =====
    'newcomer': {
        'name': '新人',
        'source': 'system',
        'desc': '初来乍到',
        'condition': '注册账号即可获得',
    },
    'veteran': {
        'name': '老玩家',
        'source': 'system', 
        'desc': '久经沙场',
        'condition': '累计登录30天',
    },
    
    # ===== 麻将头衔 =====
    'mahjong_beginner': {
        'name': '初战雀士',
        'source': 'mahjong',
        'desc': '走上雀道',
        'condition': '完成第一局麻将对局',
    },
    'mahjong_adept': {
        'name': '雀士',
        'source': 'mahjong',
        'desc': '雀坛新秀',
        'condition': '达到雀士段位',
    },
    'mahjong_expert': {
        'name': '雀杰',
        'source': 'mahjong',
        'desc': '技艺娴熟',
        'condition': '达到雀杰段位',
    },
    'mahjong_master': {
        'name': '雀豪',
        'source': 'mahjong',
        'desc': '牌技高超',
        'condition': '达到雀豪段位',
    },
    'mahjong_saint': {
        'name': '雀圣',
        'source': 'mahjong',
        'desc': '出神入化',
        'condition': '达到雀圣段位',
    },
    'mahjong_celestial': {
        'name': '魂天',
        'source': 'mahjong',
        'desc': '登峰造极',
        'condition': '达到魂天段位',
    },
    'yakuman_holder': {
        'name': '役满成就者',
        'source': 'mahjong',
        'desc': '和出役满',
        'condition': '和出任意役满',
    },
    'riichi_master': {
        'name': '立直达人',
        'source': 'mahjong',
        'desc': '立直百次',
        'condition': '累计立直100次',
    },
    'tsumo_king': {
        'name': '自摸王',
        'source': 'mahjong',
        'desc': '自摸百次',
        'condition': '累计自摸和牌100次',
    },
    'first_place_hunter': {
        'name': '一位猎手',
        'source': 'mahjong',
        'desc': '常胜将军',
        'condition': '累计获得一位50次',
    },
    
    # ===== JRPG头衔 =====
    'jrpg_adventurer': {
        'name': '冒险者',
        'source': 'jrpg',
        'desc': '踏上冒险',
        'condition': '开始JRPG冒险',
    },
    'jrpg_slayer': {
        'name': '怪物猎人',
        'source': 'jrpg',
        'desc': '斩杀百怪',
        'condition': '累计击杀100只怪物',
    },
    'jrpg_wealthy': {
        'name': '土豪',
        'source': 'jrpg',
        'desc': '富甲一方',
        'condition': '持有10000金币',
    },
    
    # ===== 社交头衔 =====
    'chat_active': {
        'name': '话痨',
        'source': 'social',
        'desc': '喜欢聊天',
        'condition': '累计发送1000条消息',
    },
    'friendly': {
        'name': '友善',
        'source': 'social',
        'desc': '乐于助人',
        'condition': '邀请10位玩家加入游戏',
    },
    
    # ===== 特殊/活动头衔 =====
    'early_bird': {
        'name': '先驱者',
        'source': 'event',
        'desc': '早期玩家',
        'condition': '2025年内注册',
    },
    'christmas_2025': {
        'name': '圣诞快乐',
        'source': 'event',
        'desc': '2025圣诞节',
        'condition': '2025年圣诞节期间登录',
    },
}

# 头衔来源分类
TITLE_SOURCES = {
    'system': '系统',
    'mahjong': '麻将',
    'jrpg': 'JRPG',
    'social': '社交',
    'event': '活动',
}

# ==================== 物品库 ====================
# 所有物品定义
# 格式: { 'id': {'name': 显示名, 'source': 来源, 'desc': 描述, 'stackable': 是否可叠加} }

ITEM_LIBRARY = {
    # ===== 通用物品 =====
    'rename_card': {
        'name': '改名卡',
        'source': 'system',
        'desc': '可以修改一次用户名',
        'stackable': True,
    },
    'gold': {
        'name': '金币',
        'source': 'system',
        'desc': '通用货币',
        'stackable': True,
    },
    
    # ===== 麻将物品 =====
    
    # ===== JRPG物品 =====
}

# 物品来源分类
ITEM_SOURCES = {
    'system': '系统',
    'mahjong': '麻将',
    'jrpg': 'JRPG',
}


def get_item_info(item_id):
    """获取物品信息"""
    return ITEM_LIBRARY.get(item_id)


def get_item_name(item_id):
    """获取物品显示名"""
    info = ITEM_LIBRARY.get(item_id)
    if info:
        return info['name']
    return item_id


def get_title_info(title_id):
    """获取头衔信息"""
    return TITLE_LIBRARY.get(title_id)


def get_title_name(title_id):
    """获取头衔显示名"""
    info = TITLE_LIBRARY.get(title_id)
    if info:
        return info['name']
    # 兼容旧数据（直接存的是名称）
    return title_id


def get_titles_by_source(source):
    """按来源获取头衔列表"""
    return {k: v for k, v in TITLE_LIBRARY.items() if v['source'] == source}


def get_all_title_names():
    """获取所有头衔名称映射"""
    return {info['name']: tid for tid, info in TITLE_LIBRARY.items()}


# ==================== 默认用户属性模板 ====================

def get_default_user_template(name="", password_hash=""):
    """获取默认的用户属性模板"""
    return {
        # 账号基础信息
        'name': name,
        'password_hash': password_hash,
        'created_at': datetime.now().isoformat(),
        
        # 大厅基础信息
        'level': 1,
        'exp': 0,
        'gold': 100,
        'title': '新人',
        'accessory': None,
        'avatar': None,
        
        # 背包系统 {物品id: 数量}
        'inventory': {
            'rename_card': 2,  # 默认赠送2张改名卡
        },
        
        # 头衔系统 (可拥有多个，最多显示3个)
        'titles': {
            'owned': ['新人'],           # 已拥有的头衔
            'displayed': ['新人'],        # 当前显示的头衔 (最多3个)
        },
        
        # 麻将段位系统 (仿雀魂)
        'mahjong': {
            'rank': 'novice_1',           # 当前段位
            'rank_points': 0,             # 段位点数 (用于升降段)
            'max_rank': 'novice_1',       # 历史最高段位
            
            # 统计数据
            'stats': {
                'total_games': 0,         # 总对局数
                'wins': 0,                # 一位次数
                'second': 0,              # 二位次数
                'third': 0,               # 三位次数
                'fourth': 0,              # 四位次数
                
                'east_games': 0,          # 东风战次数
                'south_games': 0,         # 南风战次数
                'ranked_games': 0,        # 段位战次数
                
                'ron_count': 0,           # 荣和次数
                'tsumo_count': 0,         # 自摸次数
                'deal_in_count': 0,       # 放铳次数
                'riichi_count': 0,        # 立直次数
                
                'highest_hand': None,     # 最高得点役满记录
                'yakuman_count': 0,       # 役满次数
            },
        },
        
        # 其他游戏的存档数据
        'games': {
            'jrpg': {
                'level': 1,
                'exp': 0,
                'exp_to_next': 100,
                'hp': 100,
                'max_hp': 100,
                'attack': 10,
                'defense': 5,
                'gold': 50,
                'current_area': 'forest',
                'inventory': [],
                'equipment': {'weapon': None, 'armor': None}
            }
        }
    }


def ensure_user_schema(user_data):
    """
    确保用户数据包含所有必需的属性
    如果缺少某个属性，则使用默认值填充
    
    Args:
        user_data: 现有的用户数据字典
        
    Returns:
        (updated_data, changes): 更新后的数据和变更列表
    """
    if not user_data:
        return None, []
    
    template = get_default_user_template()
    changes = []
    
    # 迁移旧的 rename_cards 到 inventory
    if 'rename_cards' in user_data and 'inventory' not in user_data:
        user_data['inventory'] = {'rename_card': user_data.pop('rename_cards', 2)}
        changes.append("迁移: rename_cards -> inventory.rename_card")
    elif 'rename_cards' in user_data:
        # 已有 inventory，删除旧字段
        user_data.pop('rename_cards', None)
        changes.append("删除: 旧字段 rename_cards")
    
    def merge_dict(target, source, path=""):
        """递归合并字典，只添加缺失的键"""
        for key, default_value in source.items():
            current_path = f"{path}.{key}" if path else key
            
            # 跳过需要保留原值的字段
            if key in ('name', 'password_hash', 'created_at', 'avatar'):
                continue
            
            if key not in target:
                # 键不存在，添加默认值
                target[key] = default_value
                changes.append(f"添加: {current_path} = {default_value}")
            elif isinstance(default_value, dict) and isinstance(target[key], dict):
                # 递归处理嵌套字典
                merge_dict(target[key], default_value, current_path)
            # 如果键存在且类型匹配，保留原值
    
    merge_dict(user_data, template)
    return user_data, changes


def get_rank_info(rank_id):
    """获取段位信息"""
    return RANKS.get(rank_id, RANKS['novice_1'])


def get_rank_name(rank_id):
    """获取段位名称"""
    info = get_rank_info(rank_id)
    return info['name']


def get_rank_index(rank_id):
    """获取段位在顺序中的位置"""
    try:
        return RANK_ORDER.index(rank_id)
    except ValueError:
        return 0


def calculate_rank_change(current_rank, points_change):
    """
    计算段位变化
    
    Args:
        current_rank: 当前段位ID
        points_change: 点数变化
        
    Returns:
        (new_rank, new_points, promoted, demoted)
    """
    rank_info = get_rank_info(current_rank)
    rank_idx = get_rank_index(current_rank)
    
    # 假设当前点数从0开始（实际使用时需要传入当前点数）
    new_points = max(0, points_change)  # 初心不会负点
    
    promoted = False
    demoted = False
    new_rank = current_rank
    
    # 检查升段
    if rank_info['points_up'] is not None and new_points >= rank_info['points_up']:
        if rank_idx < len(RANK_ORDER) - 1:
            new_rank = RANK_ORDER[rank_idx + 1]
            new_points = 0
            promoted = True
    
    # 检查降段
    elif rank_info['points_down'] is not None and new_points < rank_info['points_down']:
        if rank_idx > 0:
            # 检查是否可以降段
            prev_rank = RANK_ORDER[rank_idx - 1]
            prev_tier = get_rank_info(prev_rank)['tier']
            current_tier = rank_info['tier']
            
            # 初心和雀士不会降到更低的大段
            if current_tier > 2 or (current_tier == 2 and prev_tier == 2):
                new_rank = prev_rank
                new_points = get_rank_info(new_rank)['points_up'] // 2  # 降段后给一半点数
                demoted = True
    
    return new_rank, new_points, promoted, demoted


def get_rank_points_change(rank_id, place, game_type='south'):
    """
    获取段位点数变化
    
    Args:
        rank_id: 段位ID
        place: 名次 (1-4)
        game_type: 'east' 或 'south'
        
    Returns:
        点数变化值
    """
    rank_info = get_rank_info(rank_id)
    tier = rank_info['tier']
    
    points_table = RANK_POINTS_SOUTH if game_type == 'south' else RANK_POINTS_EAST
    tier_points = points_table.get(tier, points_table[1])
    
    return tier_points.get(place, 0)


def can_enter_match(rank_id, match_type):
    """
    检查是否可以进入某个段位场
    
    Args:
        rank_id: 玩家段位
        match_type: 'bronze', 'silver', 'gold', 'jade', 'throne'
        
    Returns:
        bool
    """
    required_rank = MATCH_REQUIREMENTS.get(match_type, 'novice_1')
    player_idx = get_rank_index(rank_id)
    required_idx = get_rank_index(required_rank)
    
    return player_idx >= required_idx


def get_title_from_rank(rank_id):
    """根据段位生成头衔"""
    rank_info = get_rank_info(rank_id)
    return rank_info['name']
