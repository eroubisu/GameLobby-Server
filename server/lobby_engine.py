"""
游戏大厅指令引擎
"""

import os
from games import get_all_games, get_game
from .config import LOCATION_HIERARCHY


class LobbyEngine:
    """游戏大厅指令引擎"""
    
    def __init__(self):
        self.game_engines = {}  # 各游戏的引擎实例
        self.player_locations = {}  # {player_name: location} 玩家当前位置
        self.online_players = {}  # {player_name: player_data} 在线玩家数据引用
        self.invite_callback = None  # 邀请回调函数
        self.pending_confirms = {}  # {player_name: 'back'|'exit'} 待确认操作
    
    def set_invite_callback(self, callback):
        """设置邀请通知回调"""
        self.invite_callback = callback
    
    def register_player(self, player_name, player_data):
        """注册在线玩家"""
        self.online_players[player_name] = player_data
        self.player_locations[player_name] = 'lobby'
        # 清除待确认状态
        if player_name in self.pending_confirms:
            del self.pending_confirms[player_name]
    
    def unregister_player(self, player_name):
        """注销玩家"""
        if player_name in self.online_players:
            del self.online_players[player_name]
        if player_name in self.player_locations:
            # 离开当前游戏房间
            location = self.player_locations[player_name]
            if location.startswith('mahjong') and 'mahjong' in self.game_engines:
                self.game_engines['mahjong'].leave_room(player_name)
            del self.player_locations[player_name]
        # 清除待确认状态
        if player_name in self.pending_confirms:
            del self.pending_confirms[player_name]
    
    def get_player_location(self, player_name):
        """获取玩家当前位置"""
        return self.player_locations.get(player_name, 'lobby')
    
    def set_player_location(self, player_name, location):
        """设置玩家位置"""
        self.player_locations[player_name] = location
    
    def get_location_path(self, location):
        """获取位置的完整路径（面包屑导航）"""
        path = []
        current = location
        while current:
            info = LOCATION_HIERARCHY.get(current)
            if info:
                path.insert(0, info[0])
                current = info[1]
            else:
                break
        return ' > '.join(path) if path else '游戏大厅'
    
    def get_parent_location(self, location):
        """获取父位置"""
        info = LOCATION_HIERARCHY.get(location)
        return info[1] if info else None
    
    def get_online_player_names(self):
        """获取在线玩家名列表"""
        return list(self.online_players.keys())
    
    def get_main_help(self):
        """获取主帮助文本"""
        games_list = ""
        for game in get_all_games():
            games_list += f"  {game['icon']} {game['name']} ({game['id']})\n"
        
        return f"""
========== 游戏大厅 ==========

【基础指令】
  /help           - 显示此帮助
  /help <游戏>    - 查看游戏说明书
  /games          - 查看游戏列表
  /play <游戏>    - 进入游戏

【导航指令】
  /back           - 返回上一级
  /home           - 返回大厅

【可用游戏】
{games_list}
【个人中心】
  /profile        - 查看个人资料
  /mytitle        - 查看我的头衔
  /alltitle       - 查看头衔图鉴
  /title <编号>   - 切换显示的头衔

【其他指令】
  /version        - 查看版本信息
  /clear          - 清屏
  /exit           - 退出程序

==============================
提示: 输入 /help jrpg 查看JRPG说明书
"""
    
    def get_game_help(self, game_id):
        """获取游戏帮助文本"""
        # 解析参数：支持 "mahjong 1" 这样的格式
        parts = game_id.split()
        base_game = parts[0]
        sub_page = parts[1] if len(parts) > 1 else None
        
        game_module = get_game(base_game)
        if not game_module:
            return f"未找到游戏: {base_game}\n使用 /games 查看可用游戏列表。"
        
        # 麻将使用分页帮助
        if base_game == 'mahjong':
            return self._get_mahjong_help(sub_page)
        
        # 其他游戏：尝试读取帮助文件（优先 help.md，其次 help.txt）
        game_dir = os.path.dirname(game_module.__file__)
        help_files = ['help.md', 'help.txt']
        
        for help_filename in help_files:
            help_file = os.path.join(game_dir, help_filename)
            if os.path.exists(help_file):
                with open(help_file, 'r', encoding='utf-8') as f:
                    return f.read()
        
        # 没有帮助文件，返回基本信息
        info = game_module.GAME_INFO
        return f"""
========== {info['name']} ==========
{info.get('description', '暂无描述')}

玩家人数: {info['min_players']}-{info['max_players']}人

使用 /play {info['id']} 开始游戏
==============================
"""

    def _get_mahjong_help(self, page=None):
        """获取麻将分页帮助"""
        if page == '1':
            return """麻将帮助 - 房间指令

【创建/加入】
  /create [类型]  创建房间
    类型: 东风/南风/铜/银/金/玉/王座
  /rooms         查看房间列表
  /join <ID>     加入指定房间

【段位系统】
  /rank          查看段位详情
  /stats         查看战绩统计

【房间管理】
  /bot           添加机器人（房主）
  /start         开始游戏（房主）
  /room          查看房间状态
  /invite @名    邀请玩家
  /accept        接受邀请

【导航】
  /back          返回上一级
  /home          返回大厅

返回目录: /help mahjong"""
        
        elif page == '2':
            return """麻将帮助 - 游戏操作

【手牌】
  /h /hand       查看手牌
  /d <n>         打第n张牌
  /dora          查看宝牌
  /tenpai /t     听牌分析

【鸣牌】
  /pong          碰
  /kong          明杠
  /chow [n]      吃（下家专用）
  /pass          过

【杠】
  /ankan [n]     暗杠
  /kakan [n]     加杠

【和牌】
  /ron /hu       荣和
  /tsumo         自摸
  /chankan       抢杠

【特殊】
  /riichi <n>    立直
  /kyuushu /9    九种九牌

返回目录: /help mahjong"""
        
        elif page == '3':
            return """麻将帮助 - 役种表

【1番】
立直 一发 门清自摸 断幺九 平和
一杯口 役牌 岭上开花 抢杠
海底摸月 河底捞鱼

【2番】
双立直 三色同顺 一气通贯
混全 七对子 对对和 三暗刻
三杠子 小三元 三色同刻 混老头

【3番】混一色 纯全 二杯口
【6番】清一色

【役满】
天和 地和 四暗刻 国士无双
大三元 小四喜 大四喜 字一色
清老头 绿一色 九莲宝灯 四杠子

返回目录: /help mahjong"""
        
        elif page == '4':
            return """麻将帮助 - 规则说明

【基本规则】
・4人对战，东风战/半庄战
・初始25000点，返点30000点
・支持吃/碰/杠/立直

【宝牌系统】
・表宝牌：指示牌的下一张
・杠宝牌：每杠翻开1张
・里宝牌：立直和牌可翻
・赤宝牌：赤5万/条/筒各1张

【流局类型】
・荒牌流局：牌山摸完
・九种九牌：第一巡9种幺九牌
・四风连打：第一巡四家同风
・四杠散了：两人以上开4杠
・四家立直：四人都立直

返回目录: /help mahjong"""
        
        else:
            return """麻将帮助

【目录】
  /help mahjong 1   房间指令
  /help mahjong 2   游戏操作
  /help mahjong 3   役种表
  /help mahjong 4   规则说明

【快速开始】
  /create    创建房间
  /bot       添加机器人
  /start     开始游戏
  /d <n>     打第n张牌

输入对应指令查看详细内容"""

    def get_games_list(self):
        """获取游戏列表"""
        text = "【游戏列表】\n\n"
        for game in get_all_games():
            text += f"  {game['icon']} {game['name']}\n"
            text += f"     ID: {game['id']}\n"
            text += f"     人数: {game['min_players']}-{game['max_players']}人\n"
            text += f"     {game.get('description', '')}\n\n"
        text += "使用 /play <游戏ID> 进入游戏"
        return text
    
    def get_profile(self, player_data, player_name):
        """获取个人资料并进入profile页面"""
        rename_cards = player_data.get('rename_cards', 2)
        self.set_player_location(player_name, 'profile')
        
        # 获取头衔信息
        titles = player_data.get('titles', {'owned': ['新人'], 'displayed': ['新人']})
        displayed = titles.get('displayed', ['新人'])
        displayed_str = ' | '.join(displayed) if displayed else '(无)'
        
        # 获取段位信息
        from .user_schema import get_rank_name
        mahjong_data = player_data.get('mahjong', {})
        rank_name = get_rank_name(mahjong_data.get('rank', 'novice_1'))
        
        return {
            'action': 'location_update',
            'location': 'profile',
            'message': f"""
========== 个人资料 ==========
昵称: {player_data['name']}
等级: Lv.{player_data['level']}
金币: {player_data['gold']}G
段位: {rank_name}
头衔: 【{displayed_str}】
饰品: {player_data.get('accessory') or '无'}
改名卡: {rename_cards}张
注册时间: {player_data.get('created_at', '未知')[:10]}
==============================

【可用操作】
  /avatar        - 修改头像
  /mytitle       - 查看我的头衔
  /alltitle      - 查看头衔图鉴
  /rename <新名> - 修改用户名
  /password      - 修改密码
  /delete        - 删除账号
  /back          - 返回大厅
"""
        }
    
    def _handle_profile_command(self, player_name, player_data, cmd, args):
        """处理个人资料页面的指令"""
        if cmd == '/avatar':
            return {'action': 'request_avatar'}
        
        elif cmd == '/rename':
            if not args:
                return "用法: /rename <新用户名>"
            
            new_name = args.strip()
            rename_cards = player_data.get('rename_cards', 2)
            
            if rename_cards <= 0:
                return "你没有改名卡了。"
            
            if len(new_name) < 2 or len(new_name) > 12:
                return "用户名长度需要在2-12个字符之间。"
            
            # 检查用户名是否已存在
            from .player_manager import PlayerManager
            if PlayerManager.player_exists(new_name):
                return f"用户名 '{new_name}' 已被使用。"
            
            # 设置待确认状态
            self.pending_confirms[player_name] = ('rename', new_name)
            return f"确定要将用户名改为 '{new_name}' 吗？（消耗1张改名卡）\n输入 /y 确认，其他任意键取消。"
        
        elif cmd == '/password':
            self.pending_confirms[player_name] = ('password_start', None)
            return "请输入新密码（6-20个字符）："
        
        elif cmd == '/delete':
            self.pending_confirms[player_name] = ('delete_start', None)
            return "警告：删除账号不可恢复！\n请输入你的用户名以确认："
        
        return None
    
    def process_command(self, player_data, command):
        """处理指令"""
        player_name = player_data['name']
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 获取玩家当前位置
        location = self.get_player_location(player_name)
        
        # 检查是否有待确认操作
        pending = self.pending_confirms.get(player_name)
        if pending:
            # 处理复杂的多步骤确认流程
            if isinstance(pending, tuple):
                pending_type = pending[0]
                pending_data = pending[1] if len(pending) > 1 else None
                
                # 改名确认
                if pending_type == 'rename':
                    if cmd == '/y':
                        del self.pending_confirms[player_name]
                        return self._do_rename(player_name, player_data, pending_data)
                    else:
                        del self.pending_confirms[player_name]
                        return "已取消改名。"
                
                # 修改密码流程
                elif pending_type == 'password_start':
                    # 用户输入的是新密码
                    new_password = command.strip()
                    if len(new_password) < 6 or len(new_password) > 20:
                        del self.pending_confirms[player_name]
                        return "密码长度需要在6-20个字符之间。已取消。"
                    self.pending_confirms[player_name] = ('password_confirm', new_password)
                    return "请再次输入新密码确认："
                
                elif pending_type == 'password_confirm':
                    confirm_password = command.strip()
                    if confirm_password != pending_data:
                        del self.pending_confirms[player_name]
                        return "两次输入的密码不一致。已取消。"
                    del self.pending_confirms[player_name]
                    return self._do_change_password(player_name, pending_data)
                
                # 删除账号流程
                elif pending_type == 'delete_start':
                    input_name = command.strip()
                    if input_name != player_name:
                        del self.pending_confirms[player_name]
                        return "用户名不匹配。已取消。"
                    self.pending_confirms[player_name] = ('delete_password', None)
                    return "请输入你的密码："
                
                elif pending_type == 'delete_password':
                    input_password = command.strip()
                    del self.pending_confirms[player_name]
                    return self._do_delete_account(player_name, input_password)
                
                # 创建房间交互式选择
                elif pending_type == 'create_room':
                    from games.mahjong.room import MahjongRoom
                    from .user_schema import get_rank_name, get_rank_index
                    
                    current_mode = pending_data.get('game_mode') if pending_data else None
                    current_match = pending_data.get('match_type') if pending_data else None
                    
                    input_val = command.strip().lower()
                    
                    # 去掉开头的/
                    while input_val.startswith('/'):
                        input_val = input_val[1:]
                    
                    # 返回
                    if input_val in ['back', 'b']:
                        del self.pending_confirms[player_name]
                        return "已取消。"
                    
                    if current_match is None:
                        # 第一步：选择段位场
                        match_type = None
                        if input_val in ['1', 'yuujin']:
                            match_type = 'yuujin'
                        elif input_val in ['2', 'dou']:
                            match_type = 'dou'
                        elif input_val in ['3', 'gin']:
                            match_type = 'gin'
                        elif input_val in ['4', 'kin']:
                            match_type = 'kin'
                        elif input_val in ['5', 'gyoku']:
                            match_type = 'gyoku'
                        elif input_val in ['6', 'ouza']:
                            match_type = 'ouza'
                        
                        if match_type is None:
                            return f"无效选择 '{input_val}'，请输入 1-6。"
                        
                        # 检查段位要求
                        match_info = MahjongRoom.MATCH_TYPES.get(match_type, {})
                        if match_info.get('ranked'):
                            player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
                            min_rank = match_info.get('min_rank', 'novice_1')
                            player_rank_idx = get_rank_index(player_rank)
                            min_rank_idx = get_rank_index(min_rank)
                            if player_rank_idx < min_rank_idx:
                                del self.pending_confirms[player_name]
                                return f"段位不足！{match_info['name_cn']}需要 {get_rank_name(min_rank)} 以上。"
                        
                        # 更新状态，进入选择游戏模式
                        self.pending_confirms[player_name] = ('create_room', {'game_mode': None, 'match_type': match_type})
                        
                        text = f"已选择: {match_info.get('name_cn', match_type)}\n\n"
                        text += "请选择游戏模式:\n\n"
                        text += "  1. tonpu (東風戦/东风战) - 4局\n"
                        text += "  2. hanchan (半荘戦/半庄战) - 8局"
                        return text
                    
                    # 第二步：选择游戏模式
                    game_mode = None
                    if input_val in ['1', 'tonpu', 'ton']:
                        game_mode = 'tonpu'
                    elif input_val in ['2', 'hanchan', 'han']:
                        game_mode = 'hanchan'
                    
                    if game_mode is None:
                        return f"无效选择 '{input_val}'，请输入 1 或 2。"
                    
                    # 清除待确认状态
                    del self.pending_confirms[player_name]
                    
                    # 创建房间
                    engine = self.game_engines.get('mahjong')
                    if not engine:
                        return "麻将引擎未初始化，请先 /play mahjong"
                    
                    avatar = player_data.get('avatar')
                    
                    room, error = engine.create_room(player_name, game_mode=game_mode, match_type=current_match)
                    
                    if error:
                        return f"{error}"
                    
                    # 设置玩家头像和段位
                    room.set_player_avatar(player_name, avatar)
                    player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
                    room.set_player_rank(player_name, player_rank)
                    self.set_player_location(player_name, 'mahjong_room')
                    
                    mode_info = MahjongRoom.GAME_MODES.get(game_mode, {})
                    match_info = MahjongRoom.MATCH_TYPES.get(current_match, {})
                    is_ranked = match_info.get('ranked', False)
                    
                    msg = f"""
房间创建成功！

房间ID: {room.room_id}
段位场: {match_info.get('name_cn', '友人场')}
模式: {mode_info.get('name_cn', '半庄战')}"""
                    
                    if is_ranked:
                        msg += f"\n类型: 段位战"
                    
                    msg += f"""
你的位置: 东（房主）

【邀请其他玩家】
  /invite @玩家名  - 邀请在线玩家

【等待中...】 {room.get_player_count()}/4
"""
                    
                    return {
                        'action': 'mahjong_room_update',
                        'location': 'mahjong_room',
                        'message': msg,
                        'room_data': room.get_table_data()
                    }
                
                # 未知的 pending_type，清除并继续
                else:
                    del self.pending_confirms[player_name]
            
            # 简单的 /y 确认
            else:
                if cmd == '/y':
                    del self.pending_confirms[player_name]
                    if pending == 'exit':
                        return {'action': 'exit'}
                    elif pending == 'back':
                        return self._do_back_confirm(player_name)
                else:
                    del self.pending_confirms[player_name]
                    return "已取消。"
        
        # 全局指令（在任何地方都可用）
        if cmd == '/help':
            if args:
                return self.get_game_help(args.lower())
            return self.get_main_help()
        
        elif cmd == '/games':
            return self.get_games_list()
        
        elif cmd == '/profile':
            return self.get_profile(player_data, player_name)
        
        elif cmd == '/clear':
            return {'action': 'clear'}
        
        elif cmd == '/version':
            from .config import SERVER_VERSION
        
        # 背包系统 - 查看背包 (全局可用)
        elif cmd == '/item':
            from .user_schema import ITEM_LIBRARY, ITEM_SOURCES
            
            inventory = player_data.get('inventory', {'rename_card': 2})
            gold = player_data.get('gold', 0)
            
            filter_source = args.lower() if args else None
            
            text = "【背包】\n\n"
            text += f"金币: {gold}\n\n"
            
            # 按来源分组显示
            for source_id, source_name in ITEM_SOURCES.items():
                if filter_source and filter_source != source_id:
                    continue
                    
                items_in_source = []
                for item_id, count in inventory.items():
                    if item_id == 'gold':
                        continue
                    item_info = ITEM_LIBRARY.get(item_id)
                    if item_info and item_info['source'] == source_id and count > 0:
                        items_in_source.append((item_id, item_info, count))
                
                if items_in_source:
                    text += f"【{source_name}】\n"
                    for item_id, info, count in items_in_source:
                        text += f"  {info['name']} x{count} - {info['desc']}\n"
                    text += "\n"
            
            if not any(count > 0 for item_id, count in inventory.items() if item_id != 'gold'):
                text += "(背包空空如也)\n"
            
            return text
        
        # 头衔系统 - 查看我的头衔库 (全局可用)
        elif cmd == '/mytitle':
            from .user_schema import TITLE_LIBRARY
            
            titles = player_data.get('titles', {'owned': ['新人'], 'displayed': ['新人']})
            owned = titles.get('owned', ['新人'])
            displayed = titles.get('displayed', ['新人'])
            
            text = "【我的头衔库】\n\n"
            if displayed:
                text += f"当前显示: {' | '.join(displayed)}\n\n"
            else:
                text += "当前显示: (无)\n\n"
            text += "已拥有的头衔:\n"
            for i, title in enumerate(owned, 1):
                mark = " [显示中]" if title in displayed else ""
                title_info = None
                for tid, info in TITLE_LIBRARY.items():
                    if info['name'] == title:
                        title_info = info
                        break
                desc = f" - {title_info['desc']}" if title_info else ""
                text += f"  {i}. {title}{mark}{desc}\n"
            
            total_titles = len(TITLE_LIBRARY)
            text += f"\n已收集: {len(owned)}/{total_titles}"
            text += "\n\n/title <编号> - 切换显示（最多3个）"
            text += "\n/title clear - 清除所有显示"
            text += "\n/alltitle - 查看头衔图鉴"
            return text
        
        # 头衔图鉴 - 查看所有可获得的头衔 (全局可用)
        elif cmd == '/alltitle':
            from .user_schema import TITLE_LIBRARY, TITLE_SOURCES
            
            titles = player_data.get('titles', {'owned': ['新人'], 'displayed': ['新人']})
            owned = titles.get('owned', ['新人'])
            
            filter_source = args.lower() if args else None
            
            if filter_source and filter_source not in TITLE_SOURCES:
                text = "可用的筛选类别:\n"
                for src, name in TITLE_SOURCES.items():
                    text += f"  /alltitles {src} - {name}头衔\n"
                return text
            
            text = "【头衔图鉴】\n"
            if filter_source:
                text += f"(筛选: {TITLE_SOURCES[filter_source]})\n"
            text += "\n"
            
            current_source = None
            category_total = 0
            category_owned = 0
            for tid, info in TITLE_LIBRARY.items():
                source = info['source']
                if filter_source and source != filter_source:
                    continue
                category_total += 1
                name = info['name']
                is_owned = name in owned
                if is_owned:
                    category_owned += 1
                if source != current_source:
                    current_source = source
                    source_name = TITLE_SOURCES.get(source, source)
                    text += f"--- {source_name} ---\n"
                status = "[已获得]" if is_owned else "[未获得]"
                text += f"  {status} {name}\n"
                text += f"       {info['desc']}\n"
                text += f"       条件: {info['condition']}\n"
            
            if filter_source:
                text += f"\n已收集: {category_owned}/{category_total}"
            else:
                text += f"\n已收集: {len(owned)}/{len(TITLE_LIBRARY)}"
            return text
        
        # 切换显示头衔 (全局可用)
        elif cmd == '/title':
            if not args:
                return "用法: /title <编号> 或 /title clear"
            
            titles = player_data.get('titles', {'owned': ['新人'], 'displayed': ['新人']})
            owned = titles.get('owned', ['新人'])
            displayed = titles.get('displayed', [])
            
            if args.lower() == 'clear':
                titles['displayed'] = []
                player_data['titles'] = titles
                from .player_manager import PlayerManager
                PlayerManager.save_player_data(player_name, player_data)
                return "已清除所有显示的头衔。"
            
            try:
                idx = int(args) - 1
                if idx < 0 or idx >= len(owned):
                    return f"无效的编号。你有 {len(owned)} 个头衔。"
                
                title = owned[idx]
                
                if title in displayed:
                    displayed.remove(title)
                    msg = f"已取消显示头衔: {title}"
                else:
                    if len(displayed) >= 3:
                        return "最多只能显示3个头衔。请先取消其他头衔。"
                    displayed.append(title)
                    msg = f"已添加显示头衔: {title}"
                
                titles['displayed'] = displayed
                player_data['titles'] = titles
                from .player_manager import PlayerManager
                PlayerManager.save_player_data(player_name, player_data)
                return msg + f"\n当前显示: {' | '.join(displayed) if displayed else '(无)'}"
                
            except ValueError:
                return "请输入头衔编号。使用 /titles 查看列表。"
            return {
                'action': 'version',
                'server_version': SERVER_VERSION,
                'message': f"服务器版本: v{SERVER_VERSION}"
            }
        
        elif cmd == '/exit':
            # 设置待确认状态
            self.pending_confirms[player_name] = 'exit'
            return "确定要退出程序吗？输入 /y 确认，其他任意键取消。"
        
        # /home - 直接返回大厅
        elif cmd == '/home':
            return self._do_home(player_name)
        
        # /back - 返回上一级
        elif cmd == '/back':
            return self._do_back(player_name)
        
        # ========== 个人资料页面指令 ==========
        if location == 'profile':
            result = self._handle_profile_command(player_name, player_data, cmd, args)
            if result:
                return result
        
        # 进入游戏
        elif cmd == '/play':
            if location != 'lobby':
                return "请先返回大厅再进入其他游戏。输入 /home 返回大厅。"
            
            if not args:
                return "用法: /play <游戏ID>\n使用 /games 查看可用游戏列表。"
            
            game_id = args.lower()
            game_module = get_game(game_id)
            if not game_module:
                return f"未找到游戏: {game_id}"
            
            # 初始化游戏引擎（如果还没有）
            if game_id not in self.game_engines:
                if game_id == 'jrpg':
                    from games.jrpg import JRPGData, JRPGEngine
                    self.game_engines['jrpg'] = JRPGEngine(JRPGData())
                elif game_id == 'mahjong':
                    from games.mahjong import MahjongData, MahjongEngine
                    self.game_engines['mahjong'] = MahjongEngine(MahjongData())
            
            # 设置位置
            self.set_player_location(player_name, game_id)
            
            info = game_module.GAME_INFO
            
            # 麻将游戏特殊提示
            if game_id == 'mahjong':
                # 获取玩家段位
                from .user_schema import get_rank_name
                rank_id = player_data.get('mahjong', {}).get('rank', 'novice_1')
                rank_name = get_rank_name(rank_id)
                rank_points = player_data.get('mahjong', {}).get('rank_points', 0)
                
                return {
                    'action': 'location_update',
                    'location': game_id,
                    'message': f"""
{info['icon']} 进入 {info['name']}

你的段位: {rank_name} ({rank_points}pt)

【麻将指令】
  /create      - 创建房间 (交互式选择)
  /rooms       - 查看房间列表
  /join <房间ID> - 加入房间
  /rank        - 查看段位详情
  /stats       - 查看战绩统计
  /back        - 返回上一级

输入 /help mahjong 查看完整说明
"""
                }
            
            return {
                'action': 'location_update',
                'location': game_id,
                'message': f"""
{info['icon']} 进入 {info['name']}

输入 /help {game_id} 查看游戏说明
输入 /back 返回上一级
"""
            }
        
        # ========== 麻将游戏专用指令 ==========
        if location.startswith('mahjong') and 'mahjong' in self.game_engines:
            result = self._handle_mahjong_command(player_name, player_data, cmd, args)
            if result:
                return result
        
        # 如果在JRPG游戏中，转发给游戏引擎处理
        if location == 'jrpg' and 'jrpg' in self.game_engines:
            engine = self.game_engines['jrpg']
            
            # 获取游戏存档
            game_save = player_data.get('games', {}).get('jrpg', {})
            if not game_save:
                return "游戏存档损坏，请联系管理员。"
            
            # 将玩家名添加到游戏存档中供引擎使用
            game_save['name'] = player_name
            
            result = engine.process_command(game_save, command)
            
            # 同步游戏存档回玩家数据
            if 'games' not in player_data:
                player_data['games'] = {}
            player_data['games']['jrpg'] = game_save
            
            if result:
                return result
        
        # 未知指令
        if location != 'lobby':
            game_id = location.split('_')[0] if '_' in location else location
            return f"未知指令。输入 /help {game_id} 查看游戏帮助。"
        return "未知指令。输入 /help 查看帮助。"
    
    def _process_ranked_result(self, room, rankings):
        """
        处理段位场游戏结果，更新玩家段位点数
        
        Args:
            room: 麻将房间对象
            rankings: 按分数排序的玩家位置列表 [第1名pos, 第2名pos, ...]
            
        Returns:
            rank_changes: {pos: {points_change, new_rank, promoted, demoted, ...}}
        """
        from .user_schema import (
            get_rank_points_change, get_rank_info, get_rank_name,
            calculate_rank_change, get_title_from_rank
        )
        from .player_manager import PlayerManager
        
        rank_changes = {}
        game_type_base = 'south' if room.game_type in ['bronze', 'silver', 'gold', 'jade', 'throne'] else room.game_type
        
        for place, pos in enumerate(rankings, 1):
            player_name = room.players[pos]
            if not player_name or room.is_bot(player_name):
                continue
            
            # 加载玩家数据
            player_data = PlayerManager.load_player_data(player_name)
            if not player_data:
                continue
            
            mahjong_data = player_data.get('mahjong', {})
            current_rank = mahjong_data.get('rank', 'novice_1')
            current_points = mahjong_data.get('rank_points', 0)
            stats = mahjong_data.get('stats', {})
            
            # 计算点数变化
            points_change = get_rank_points_change(current_rank, place, game_type_base)
            new_points = max(0, current_points + points_change)
            
            # 检查升降段
            rank_info = get_rank_info(current_rank)
            new_rank = current_rank
            promoted = False
            demoted = False
            
            # 升段检查
            points_up = rank_info.get('points_up')
            if points_up and new_points >= points_up:
                from .user_schema import RANK_ORDER, get_rank_index
                idx = get_rank_index(current_rank)
                if idx < len(RANK_ORDER) - 1:
                    new_rank = RANK_ORDER[idx + 1]
                    new_points = 0
                    promoted = True
            
            # 降段检查
            points_down = rank_info.get('points_down')
            if points_down is not None and new_points < points_down and current_points + points_change < 0:
                from .user_schema import RANK_ORDER, get_rank_index
                idx = get_rank_index(current_rank)
                if idx > 0:
                    prev_rank = RANK_ORDER[idx - 1]
                    prev_info = get_rank_info(prev_rank)
                    # 初心不降段，雀士不降回初心
                    if rank_info['tier'] > 2 or (rank_info['tier'] == 2 and prev_info['tier'] == 2):
                        new_rank = prev_rank
                        new_points = prev_info.get('points_up', 40) // 2
                        demoted = True
            
            # 更新统计数据
            stats['total_games'] = stats.get('total_games', 0) + 1
            stats['ranked_games'] = stats.get('ranked_games', 0) + 1
            if game_type_base == 'east':
                stats['east_games'] = stats.get('east_games', 0) + 1
            else:
                stats['south_games'] = stats.get('south_games', 0) + 1
            
            # 更新名次统计
            place_keys = ['wins', 'second', 'third', 'fourth']
            stats[place_keys[place - 1]] = stats.get(place_keys[place - 1], 0) + 1
            
            # 更新麻将数据
            mahjong_data['rank'] = new_rank
            mahjong_data['rank_points'] = new_points
            mahjong_data['stats'] = stats
            
            # 更新历史最高段位
            from .user_schema import get_rank_index
            if get_rank_index(new_rank) > get_rank_index(mahjong_data.get('max_rank', 'novice_1')):
                mahjong_data['max_rank'] = new_rank
            
            # 如果升段，添加新头衔
            if promoted:
                new_title = get_title_from_rank(new_rank)
                titles = player_data.get('titles', {'owned': ['新人'], 'displayed': ['新人']})
                if new_title not in titles['owned']:
                    titles['owned'].append(new_title)
                player_data['titles'] = titles
            
            player_data['mahjong'] = mahjong_data
            
            # 保存玩家数据
            PlayerManager.save_player_data(player_name, player_data)
            
            # 记录变化
            rank_changes[pos] = {
                'player': player_name,
                'place': place,
                'points_change': points_change,
                'new_points': new_points,
                'old_rank': current_rank,
                'new_rank': new_rank,
                'new_rank_name': get_rank_name(new_rank),
                'promoted': promoted,
                'demoted': demoted
            }
        
        return rank_changes
    
    def _handle_mahjong_command(self, player_name, player_data, cmd, args):
        """处理麻将游戏指令"""
        engine = self.game_engines['mahjong']
        avatar = player_data.get('avatar')
        location = self.get_player_location(player_name)
        
        # 创建房间
        if cmd == '/create':
            if location != 'mahjong':
                return "请先返回麻将大厅再创建房间。"
            
            from games.mahjong.room import MahjongRoom
            from .user_schema import get_rank_name, get_rank_index
            
            # 解析参数：/create [game_mode] [match_type]
            # game_mode: tonpu(东风战) / hanchan(半庄战)
            # match_type: yuujin(友人场) / dou(铜) / gin(银) / kin(金) / gyoku(玉) / ouza(王座)
            
            game_mode = None
            match_type = None
            
            if args:
                parts = args.lower().split()
                for part in parts:
                    # 游戏模式
                    if part in ['tonpu', 'ton', 't', 'east', 'e']:
                        game_mode = 'tonpu'
                    elif part in ['hanchan', 'han', 'h', 'south', 's']:
                        game_mode = 'hanchan'
                    # 段位场类型
                    elif part in ['yuujin', 'yuu', 'y', 'friend', 'f']:
                        match_type = 'yuujin'
                    elif part in ['dou', 'd', 'bronze', 'copper']:
                        match_type = 'dou'
                    elif part in ['gin', 'g', 'silver']:
                        match_type = 'gin'
                    elif part in ['kin', 'k', 'gold']:
                        match_type = 'kin'
                    elif part in ['gyoku', 'jade']:
                        match_type = 'gyoku'
                    elif part in ['ouza', 'o', 'throne']:
                        match_type = 'ouza'
            
            # 如果没有指定参数，进入交互式选择
            if game_mode is None or match_type is None:
                # 设置待确认状态
                self.pending_confirms[player_name] = ('create_room', {'game_mode': game_mode, 'match_type': match_type})
                
                if match_type is None:
                    # 先选段位场
                    player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
                    player_rank_idx = get_rank_index(player_rank)
                    
                    text = "请选择段位场:\n\n"
                    text += "  1. yuujin (友人场) - 不影响段位\n"
                    
                    match_list = [
                        ('dou', '銅の間', '铜之间', 'novice_1'),
                        ('gin', '銀の間', '银之间', 'adept_1'),
                        ('kin', '金の間', '金之间', 'expert_1'),
                        ('gyoku', '玉の間', '玉之间', 'master_1'),
                        ('ouza', '王座の間', '王座之间', 'saint_1'),
                    ]
                    
                    for i, (key, jp_name, cn_name, min_rank) in enumerate(match_list, 2):
                        min_rank_idx = get_rank_index(min_rank)
                        can_enter = player_rank_idx >= min_rank_idx
                        status = "" if can_enter else f" (需要{get_rank_name(min_rank)})"
                        text += f"  {i}. {key} ({cn_name}){status}\n"
                    
                    return text
                else:
                    # 已选段位场，选游戏模式
                    match_info = MahjongRoom.MATCH_TYPES.get(match_type, {})
                    text = f"已选择: {match_info.get('name_cn', match_type)}\n\n"
                    text += "请选择游戏模式:\n\n"
                    text += "  1. tonpu (東風戦/东风战) - 4局\n"
                    text += "  2. hanchan (半荘戦/半庄战) - 8局"
                    return text
            
            # 检查段位要求
            match_info = MahjongRoom.MATCH_TYPES.get(match_type, MahjongRoom.MATCH_TYPES['yuujin'])
            if match_info.get('ranked'):
                player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
                min_rank = match_info.get('min_rank', 'novice_1')
                player_rank_idx = get_rank_index(player_rank)
                min_rank_idx = get_rank_index(min_rank)
                if player_rank_idx < min_rank_idx:
                    return f"段位不足！{match_info['name_cn']}需要 {get_rank_name(min_rank)} 以上。\n你的段位: {get_rank_name(player_rank)}"
            
            room, error = engine.create_room(player_name, game_mode=game_mode, match_type=match_type)
            if error:
                return f"{error}"
            
            # 设置玩家头像和段位
            room.set_player_avatar(player_name, avatar)
            player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
            room.set_player_rank(player_name, player_rank)
            self.set_player_location(player_name, 'mahjong_room')
            
            mode_info = MahjongRoom.GAME_MODES.get(game_mode, {})
            is_ranked = match_info.get('ranked', False)
            
            msg = f"""
房间创建成功！

房间ID: {room.room_id}
段位场: {match_info.get('name_cn', '友人场')}
模式: {mode_info.get('name_cn', '半庄战')}"""
            
            if is_ranked:
                msg += f"\n类型: 段位战"
            
            msg += f"""
你的位置: 东（房主）

【邀请其他玩家】
  /invite @玩家名  - 邀请在线玩家

【等待中...】 {room.get_player_count()}/4
"""
            
            return {
                'action': 'mahjong_room_update',
                'location': 'mahjong_room',
                'message': msg,
                'room_data': room.get_table_data()
            }
        
        # 取消操作
        elif cmd == '/cancel':
            if player_name in self.pending_confirms:
                del self.pending_confirms[player_name]
                return "已取消。"
            return "没有待处理的操作。"
        
        # 查看房间列表
        elif cmd == '/rooms':
            rooms = engine.list_rooms()
            if not rooms:
                return "当前没有可加入的房间。\n使用 /create 创建新房间。"
            
            from games.mahjong.room import MahjongRoom
            text = "【房间列表】\n\n"
            for r in rooms:
                text += f"  {r['room_id']}\n"
                text += f"     房主: {r['host']}\n"
                text += f"     类型: {r.get('game_type_name', '友人场 半庄战')}\n"
                text += f"     人数: {r['player_count']}/4\n\n"
            text += "使用 /join <房间ID> 加入房间"
            return text
        
        # 查看段位
        elif cmd == '/rank':
            from .user_schema import get_rank_info, RANK_ORDER, get_rank_index
            
            mahjong_data = player_data.get('mahjong', {})
            rank_id = mahjong_data.get('rank', 'novice_1')
            rank_points = mahjong_data.get('rank_points', 0)
            max_rank = mahjong_data.get('max_rank', 'novice_1')
            rank_info = get_rank_info(rank_id)
            max_rank_info = get_rank_info(max_rank)
            
            # 升段进度
            points_up = rank_info.get('points_up')
            if points_up:
                progress = min(100, int(rank_points / points_up * 100))
                progress_bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
            else:
                progress_bar = '████████████ MAX'
                progress = 100
            
            text = f"""【段位信息】

当前段位: {rank_info['name']}
段位点数: {rank_points}pt"""
            
            if points_up:
                text += f" / {points_up}pt"
            
            text += f"""
升段进度: [{progress_bar}] {progress}%
历史最高: {max_rank_info['name']}
"""
            return text
        
        # 查看战绩统计
        elif cmd == '/stats':
            mahjong_data = player_data.get('mahjong', {})
            stats = mahjong_data.get('stats', {})
            
            total = stats.get('total_games', 0)
            wins = stats.get('wins', 0)
            second = stats.get('second', 0)
            third = stats.get('third', 0)
            fourth = stats.get('fourth', 0)
            
            if total > 0:
                win_rate = wins / total * 100
                avg_place = (wins * 1 + second * 2 + third * 3 + fourth * 4) / total
            else:
                win_rate = 0
                avg_place = 0
            
            text = f"""【战绩统计】

总对局数: {total}

【名次分布】
  1位: {wins} ({wins/max(total,1)*100:.1f}%)
  2位: {second} ({second/max(total,1)*100:.1f}%)
  3位: {third} ({third/max(total,1)*100:.1f}%)
  4位: {fourth} ({fourth/max(total,1)*100:.1f}%)

平均顺位: {avg_place:.2f}
一位率: {win_rate:.1f}%

【和牌统计】
  荣和: {stats.get('ron_count', 0)}
  自摸: {stats.get('tsumo_count', 0)}
  放铳: {stats.get('deal_in_count', 0)}
  立直: {stats.get('riichi_count', 0)}
  役满: {stats.get('yakuman_count', 0)}
"""
            return text
            return text
        
        # 加入房间
        elif cmd == '/join':
            if location != 'mahjong':
                return "请先返回麻将大厅再加入房间。"
            
            if not args:
                return "用法: /join <房间ID>\n使用 /rooms 查看房间列表。"
            
            room_id = args.strip()
            room = engine.get_room(room_id)
            
            if not room:
                return "房间不存在。"
            
            # 检查段位要求
            from .user_schema import can_enter_match, get_rank_name
            from games.mahjong.room import MahjongRoom
            type_info = MahjongRoom.GAME_TYPES.get(room.game_type, {})
            
            if type_info.get('ranked'):
                player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
                if not can_enter_match(player_rank, room.game_type):
                    min_rank = type_info.get('min_rank', 'novice_1')
                    return f"段位不足！{type_info['name']}需要 {get_rank_name(min_rank)} 以上。\n你的段位: {get_rank_name(player_rank)}"
            
            room, error = engine.join_room(room_id, player_name)
            if error:
                return f"{error}"
            
            # 设置玩家头像、段位和位置
            room.set_player_avatar(player_name, avatar)
            player_rank = player_data.get('mahjong', {}).get('rank', 'novice_1')
            room.set_player_rank(player_name, player_rank)
            self.set_player_location(player_name, 'mahjong_room')
            pos = room.get_position(player_name)
            
            # 构建消息
            join_msg = f"""
成功加入房间！

房间ID: {room.room_id}
你的位置: {room.POSITIONS[pos]}
房主: {room.host}

【等待中...】 {room.get_player_count()}/4
"""
            
            # 构建通知消息
            notify_msg = f"{player_name} 加入了房间"
            if room.is_full():
                notify_msg += "\n人已齐！房主可以输入 /start 开始游戏"
            
            return {
                'action': 'mahjong_room_update',
                'location': 'mahjong_room',
                'message': join_msg,
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room_id,
                    'message': notify_msg,
                    'room_data': room.get_table_data()
                }
            }
        
        # 邀请玩家
        elif cmd == '/invite':
            if not args or not args.startswith('@'):
                return "用法: /invite @玩家名"
            
            target = args[1:].strip()
            
            # 检查自己是否在房间
            room = engine.get_player_room(player_name)
            if not room:
                return "你还没有创建或加入房间。"
            
            # 检查目标是否在线
            if target not in self.online_players:
                return f"玩家 {target} 不在线。"
            
            if target == player_name:
                return "不能邀请自己。"
            
            # 检查目标是否已在房间
            if engine.get_player_room(target):
                return f"{target} 已经在一个房间中了。"
            
            # 发送邀请
            engine.send_invite(player_name, target, room.room_id)
            
            # 通知被邀请者
            if self.invite_callback:
                self.invite_callback(target, {
                    'type': 'game_invite',
                    'from': player_name,
                    'game': 'mahjong',
                    'room_id': room.room_id,
                    'message': f" {player_name} 邀请你加入麻将房间！\n输入 /play mahjong 然后 /accept 接受邀请"
                })
            
            return f"已向 {target} 发送邀请"
        
        # 接受邀请
        elif cmd == '/accept':
            invite = engine.get_invite(player_name)
            if not invite:
                return "你没有收到邀请，或邀请已过期。"
            
            room_id = invite['room_id']
            engine.clear_invite(player_name)
            
            room, error = engine.join_room(room_id, player_name)
            if error:
                return f"{error}"
            
            # 设置玩家头像和位置
            room.set_player_avatar(player_name, avatar)
            self.set_player_location(player_name, 'mahjong_room')
            pos = room.get_position(player_name)
            
            return {
                'action': 'mahjong_room_update',
                'location': 'mahjong_room',
                'message': f"""
接受邀请，加入房间成功！

房间ID: {room.room_id}
你的位置: {room.POSITIONS[pos]}

【等待中...】 {room.get_player_count()}/4
""",
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room_id,
                    'message': f"{player_name} 接受邀请加入了房间",
                    'room_data': room.get_table_data()
                }
            }
        

        
        # 添加机器人
        elif cmd == '/bot':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            
            if room.host != player_name:
                return "只有房主才能添加机器人。"
            
            if room.state != 'waiting':
                return "游戏已开始，无法添加机器人。"
            
            # 解析要添加的数量
            count = 1
            if args:
                try:
                    count = int(args.strip())
                    if count < 1:
                        count = 1
                    elif count > 3:
                        count = 3  # 最多添加3个bot
                except ValueError:
                    count = 1
            
            # 添加多个bot
            added_bots = []
            for _ in range(count):
                if room.is_full():
                    break
                success, result = room.add_bot()
                if success:
                    added_bots.append(result)
                else:
                    break
            
            if not added_bots:
                return "无法添加机器人，房间可能已满。"
            
            bot_names = ', '.join(added_bots)
            notify_msg = f"机器人 {bot_names} 加入了房间"
            if room.is_full():
                notify_msg += "\n人已齐！房主可以输入 /start 开始游戏"
            
            return {
                'action': 'mahjong_bot_join',
                'message': f"已添加机器人: {bot_names}",
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'message': notify_msg,
                    'room_data': room.get_table_data()
                }
            }
        
        # 踢出玩家或机器人
        elif cmd == '/kick':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            
            if room.host != player_name:
                return "只有房主才能踢出玩家。"
            
            if room.state != 'waiting':
                return "游戏已开始，无法踢出玩家。"
            
            if not args:
                # 显示可踢出的玩家列表
                players_list = []
                for i in range(4):
                    p = room.players[i]
                    if p and p != player_name:
                        mark = " (bot)" if room.is_bot(p) else ""
                        players_list.append(f"  {i+1}. {p}{mark}")
                
                if not players_list:
                    return "房间里没有其他玩家可以踢出。"
                
                return "用法: /kick <编号> 或 /kick @名字\n\n当前玩家:\n" + '\n'.join(players_list)
            
            # 解析目标
            target = args.strip()
            target_name = None
            
            # 尝试按编号查找
            try:
                idx = int(target) - 1
                if 0 <= idx < 4 and room.players[idx] and room.players[idx] != player_name:
                    target_name = room.players[idx]
            except ValueError:
                pass
            
            # 尝试按名字查找（需要@前缀）
            if not target_name and target.startswith('@'):
                name = target[1:]  # 去掉@
                for i in range(4):
                    p = room.players[i]
                    if p and p != player_name and (p == name or p.lower() == name.lower()):
                        target_name = p
                        break
            
            if not target_name:
                return f"找不到玩家: {target}\n用法: /kick <编号> 或 /kick @名字"
            
            # 执行踢出
            is_bot = room.is_bot(target_name)
            pos = room.remove_player(target_name)
            if pos < 0:
                return "踢出失败。"
            
            # 如果是bot，从bots集合中移除
            if is_bot:
                room.bots.discard(target_name)
            
            kick_msg = f"{target_name} 被踢出了房间"
            
            return {
                'action': 'mahjong_player_kick',
                'message': f"已踢出: {target_name}",
                'room_data': room.get_table_data(),
                'kicked_player': target_name,
                'notify_room': {
                    'room_id': room.room_id,
                    'message': kick_msg,
                    'room_data': room.get_table_data()
                }
            }
        
        # 开始游戏（仅房主可用）
        elif cmd == '/start':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            
            if room.host != player_name:
                return "只有房主才能开始游戏。"
            
            if room.state != 'waiting':
                return "游戏已经开始了。"
            
            if not room.is_full():
                return f"需要4名玩家才能开始游戏。当前: {room.get_player_count()}/4"
            
            # 开始游戏
            if room.start_game(engine.game_data):
                # 设置所有玩家的位置为 mahjong_playing
                for p in room.players.values():
                    if p and isinstance(p, str) and not p.startswith('机器人'):
                        self.set_player_location(p, 'mahjong_playing')
                
                # 获取当前玩家的手牌（座位可能变了）
                pos = room.get_position(player_name)
                my_hand = room.hands[pos]
                
                # 获取庄家信息
                dealer_pos = room.dealer
                dealer_name = room.players[dealer_pos]
                
                # 庄家有14张牌，标记最后一张为新摸的
                drawn_tile = None
                if pos == dealer_pos and len(my_hand) == 14:
                    drawn_tile = my_hand[-1]
                
                # 我的自风
                my_wind = room.get_player_wind(pos)
                
                msg = f" 游戏开始！座位已随机分配\n\n"
                msg += f"庄家: {dealer_name}\n"
                msg += f"你的位置: {my_wind}家\n\n"
                
                if pos == dealer_pos:
                    msg += "🎲 你是庄家，请出牌！\n输入 /d 编号 打出一张牌"
                else:
                    msg += f"轮到 {dealer_name} 出牌\n输入 /h 查看手牌"
                
                # 获取听牌分析
                tenpai_analysis = room.get_tenpai_analysis(pos)
                
                return {
                    'action': 'mahjong_game_start',
                    'location': 'mahjong_playing',
                    'message': msg,
                    'hand': my_hand,
                    'drawn': drawn_tile,  # 庄家的第14张牌
                    'room_data': room.get_table_data(),
                    'room_id': room.room_id,  # 用于机器人自动打牌
                    'dealer_name': dealer_name,  # 用于机器人自动打牌
                    'tenpai_analysis': tenpai_analysis,
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f" 游戏开始！座位已随机分配\n庄家: {dealer_name}\n输入 /h 查看手牌",
                        'room_data': room.get_table_data(),
                        'game_started': True,  # 标记游戏开始，让其他玩家也查看手牌
                        'location': 'mahjong_playing'
                    }
                }
            else:
                return "开始游戏失败。"
        
        # 开始下一局（流局或和牌后）
        elif cmd == '/next':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            
            if room.state != 'finished':
                return "当前局还未结束。"
            
            next_round_result = room.start_next_round()
            
            if next_round_result:
                # 确保所有玩家位置为 mahjong_playing
                for p in room.players.values():
                    if p and isinstance(p, str) and not p.startswith('机器人'):
                        self.set_player_location(p, 'mahjong_playing')
                
                pos = room.get_position(player_name)
                my_hand = room.hands[pos]
                
                dealer_pos = room.dealer
                dealer_name = room.players[dealer_pos]
                
                drawn_tile = None
                if pos == dealer_pos and len(my_hand) == 14:
                    drawn_tile = my_hand[-1]
                
                my_wind = room.get_player_wind(pos)
                
                round_wind = room.round_wind
                round_number = room.round_number + 1
                honba = room.honba
                
                msg = f" {round_wind}{round_number}局 {honba}本场 开始！\n\n"
                msg += f"庄家: {dealer_name}\n"
                msg += f"你的位置: {my_wind}家\n\n"
                
                if pos == dealer_pos:
                    msg += "🎲 你是庄家，请出牌！\n输入 /d 编号 打出一张牌"
                else:
                    msg += f"轮到 {dealer_name} 出牌\n输入 /h 查看手牌"
                
                tenpai_analysis = room.get_tenpai_analysis(pos)
                
                return {
                    'action': 'mahjong_game_start',
                    'location': 'mahjong_playing',
                    'message': msg,
                    'hand': my_hand,
                    'drawn': drawn_tile,
                    'room_data': room.get_table_data(),
                    'room_id': room.room_id,
                    'dealer_name': dealer_name,
                    'tenpai_analysis': tenpai_analysis,
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f" {round_wind}{round_number}局 {honba}本场 开始！\n庄家: {dealer_name}\n输入 /h 查看手牌",
                        'room_data': room.get_table_data(),
                        'game_started': True,
                        'location': 'mahjong_playing'
                    }
                }
            else:
                # 游戏结束 - 所有玩家返回房间
                for p in room.players.values():
                    if p and isinstance(p, str) and not p.startswith('机器人'):
                        self.set_player_location(p, 'mahjong_room')
                
                scores = room.scores
                players = room.players
                result_lines = ["游戏结束！最终结果："]
                # 按分数排序
                rankings = sorted(range(4), key=lambda i: scores[i], reverse=True)
                for rank, i in enumerate(rankings):
                    result_lines.append(f"  {rank+1}. {players[i]}: {scores[i]}点")
                
                # 段位场处理段位点数变化
                rank_changes = None
                if room.is_ranked_match():
                    rank_changes = self._process_ranked_result(room, rankings)
                    if rank_changes:
                        result_lines.append("")
                        result_lines.append("【段位点数变化】")
                        for pos in rankings:
                            player = players[pos]
                            if player and not room.is_bot(player):
                                change_info = rank_changes.get(pos, {})
                                pts = change_info.get('points_change', 0)
                                sign = '+' if pts >= 0 else ''
                                result_lines.append(f"  {player}: {sign}{pts}pt")
                                if change_info.get('promoted'):
                                    result_lines.append(f"    升段！→ {change_info.get('new_rank_name', '')}")
                                elif change_info.get('demoted'):
                                    result_lines.append(f"    降段... → {change_info.get('new_rank_name', '')}")
                
                return {
                    'action': 'mahjong_game_end',
                    'location': 'mahjong_room',
                    'message': '\n'.join(result_lines),
                    'room_data': room.get_table_data(),
                    'rank_changes': rank_changes,
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': '\n'.join(result_lines),
                        'room_data': room.get_table_data(),
                        'location': 'mahjong_room',
                        'rank_changes': rank_changes
                    }
                }
        
        # 查看当前房间状态
        elif cmd == '/room' or cmd == '/status':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。\n使用 /create 创建房间或 /rooms 查看房间列表。"
            
            pos = room.get_position(player_name)
            text = f"""
【房间状态】
房间ID: {room.room_id}
房主: {room.host}
状态: {'等待中' if room.state == 'waiting' else '游戏中'}
你的位置: {room.POSITIONS[pos]}

【座位】
"""
            for i in range(4):
                player = room.players[i] or "(空位)"
                mark = " ← 你" if i == pos else ""
                text += f"  {room.POSITIONS[i]}: {player}{mark}\n"
            
            text += f"\n人数: {room.get_player_count()}/4"
            
            # 如果满员且是房主，提示可以开始游戏
            if room.is_full() and room.host == player_name and room.state == 'waiting':
                text += "\n\n人已齐！输入 /start 开始游戏"
            
            return {
                'action': 'mahjong_room_update',
                'message': text,
                'room_data': room.get_table_data()
            }
        
        # 查看宝牌
        elif cmd == '/dora':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            if room.state != 'playing':
                return "游戏还未开始。"
            
            from games.mahjong.game_data import DORA_NEXT, normalize_tile
            
            # 显示宝牌指示牌和对应的宝牌
            text = "【宝牌信息】\n\n"
            text += f"📍 场风: {room.round_wind}场 第{room.round_number + 1}局\n"
            text += f"📍 本场数: {room.honba}\n\n"
            
            text += "宝牌指示牌:\n"
            for i, indicator in enumerate(room.dora_indicators):
                dora = DORA_NEXT.get(normalize_tile(indicator), indicator)
                text += f"  {i+1}. [{indicator}] → 宝牌: [{dora}]\n"
            
            text += f"\n💎 赤宝牌: 赤五万、赤五条、赤五筒 (各1张)\n"
            text += f"\n📊 剩余牌数: {len(room.deck)} 张\n"
            text += f"📊 杠次数: {room.kan_count}\n"
            
            # 立直时提示有里宝牌
            pos = room.get_position(player_name)
            if room.riichi[pos]:
                text += "\n🔒 你已立直，和牌时可翻开里宝牌！"
            
            return text
        
        # ========== 游戏中指令 ==========
        
        # 查看手牌
        elif cmd == '/hand' or cmd == '/h':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            if room.state != 'playing':
                return "游戏还未开始。"
            
            pos = room.get_position(player_name)
            
            # 获取听牌分析
            tenpai_analysis = room.get_tenpai_analysis(pos)
            
            return {
                'action': 'mahjong_hand_update',
                'message': "",
                'hand': room.hands[pos],
                'room_data': room.get_table_data(),
                'tenpai_analysis': tenpai_analysis
            }
        
        # 打牌 - 支持 /d 编号 或 /discard 牌名
        elif cmd == '/d' or cmd == '/discard':
            room = engine.get_player_room(player_name)
            if not room:
                return "你不在任何房间中。"
            if room.state != 'playing':
                return "游戏还未开始。"
            
            pos = room.get_position(player_name)
            if room.current_turn != pos:
                current_player = room.players[room.current_turn]
                return f"还没轮到你，当前轮到 {current_player}。"
            
            if not args:
                return "用法: /d <编号>\n例如: /d 1 (打第1张牌)"
            
            # 支持编号或牌名
            arg = args.strip()
            hand = room.hands[pos]
            
            # 检查是否在等待吃碰杠操作
            if room.waiting_for_action:
                return "⏳ 等待玩家操作中（吃/碰/杠）..."
            
            # 先解析要打的牌
            if arg.isdigit():
                idx = int(arg) - 1  # 转为0-based索引
                if idx < 0 or idx >= len(hand):
                    return f"无效编号，手牌共 {len(hand)} 张 (1-{len(hand)})"
                tile = hand[idx]
            else:
                tile = arg
                if tile not in hand:
                    return f"你没有这张牌: {tile}\n输入 /h 查看手牌"
            
            # 立直后只能打最后摸到的牌（摸切）
            if room.riichi[pos]:
                drawn_tile = hand[-1] if hand else None
                if drawn_tile and tile != drawn_tile:
                    drawn_idx = len(hand)
                    return f"🔒 立直中只能摸切！请输入 /d {drawn_idx}"
            
            if room.discard_tile(pos, tile):
                # 获取下家信息
                next_pos = room.current_turn
                next_player = room.players[next_pos]
                
                # 如果有人可以吃碰杠，先不让下家摸牌
                if room.waiting_for_action:
                    my_new_hand = room.hands[pos]
                    action_count = len(room.action_players)
                    action_hint = f" [等待操作({action_count})]" if action_count > 0 else ""
                    return {
                        'action': 'mahjong_discard',
                        'message': f"打出 [{tile}]，轮到 {next_player}{action_hint}",
                        'hand': my_new_hand,
                        'room_data': room.get_table_data(),
                        'notify_room': {
                            'room_id': room.room_id,
                            'discard_info': {
                                'player': player_name,
                                'tile': tile,
                                'next_player': next_player,  # 显示下家名字
                                'drawn_tile': None,  # 但不摸牌
                                'waiting_action': True  # 标记等待状态
                            },
                            'room_data': room.get_table_data()
                        }
                    }
                
                # 没人可以操作，下家摸牌
                drawn = room.draw_tile(next_pos)
                
                # 检查是否荒牌流局（牌堆摸完）
                if drawn is None:
                    # 荒牌流局
                    ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                    room.state = 'finished'
                    
                    # 构建流局消息
                    tenpai_names = [room.players[i] for i in ryuukyoku_result['tenpai']]
                    noten_names = [room.players[i] for i in ryuukyoku_result['noten']]
                    
                    msg_lines = ["荒牌流局！牌山已摸完"]
                    if tenpai_names:
                        msg_lines.append(f"📗 听牌: {', '.join(tenpai_names)}")
                    if noten_names:
                        msg_lines.append(f"📕 未听: {', '.join(noten_names)}")
                    
                    # 显示点数变化
                    for i in range(4):
                        change = ryuukyoku_result['score_changes'][i]
                        if change != 0:
                            sign = '+' if change > 0 else ''
                            msg_lines.append(f"  {room.players[i]}: {sign}{change}")
                    
                    # 显示是否连庄
                    if ryuukyoku_result.get('renchan'):
                        msg_lines.append(f"🔄 {room.players[room.dealer]} 连庄")
                    else:
                        msg_lines.append(f"➡️ 轮庄")
                    
                    my_new_hand = room.hands[pos]
                    
                    return {
                        'action': 'mahjong_ryuukyoku',
                        'message': '\n'.join(msg_lines),
                        'hand': my_new_hand,
                        'room_data': room.get_table_data(),
                        'ryuukyoku_result': ryuukyoku_result,
                        'notify_room': {
                            'room_id': room.room_id,
                            'message': '\n'.join(msg_lines),
                            'room_data': room.get_table_data()
                        }
                    }
                
                next_player = room.players[next_pos]
                
                # 更新当前玩家手牌（打牌后）
                my_new_hand = room.hands[pos]
                
                return {
                    'action': 'mahjong_discard',
                    'message': f"打出 [{tile}]，轮到 {next_player}",
                    'hand': my_new_hand,
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'discard_info': {
                            'player': player_name,
                            'tile': tile,
                            'next_player': next_player,
                            'drawn_tile': drawn  # 下家摸到的牌
                        },
                        'room_data': room.get_table_data()
                    }
                }
            else:
                return f"你没有这张牌: {tile}\n输入 /h 查看手牌"
        
        # 碰
        elif cmd == '/pong':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            last_tile = room.last_discard
            
            if not last_tile:
                return "没有可以碰的牌"
            
            # 检查是否可以碰
            actions = room.check_actions(pos, last_tile)
            if 'pong' not in actions:
                return f"你没有足够的 [{last_tile}] 来碰"
            
            # 执行碰操作
            if room.do_pong(pos, last_tile):
                tenpai_analysis = room.get_tenpai_analysis(pos)
                return {
                    'action': 'mahjong_pong',
                    'message': f"碰 [{last_tile}]，请出牌",
                    'hand': room.hands[pos],
                    'need_discard': True,  # 碰后需要出牌
                    'tenpai_analysis': tenpai_analysis,
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f"{player_name} 碰 [{last_tile}]",
                        'room_data': room.get_table_data()
                    }
                }
            return "碰失败"
        
        # 杠
        elif cmd == '/kong':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            last_tile = room.last_discard
            
            if not last_tile:
                return "没有可以杠的牌"
            
            actions = room.check_actions(pos, last_tile)
            if 'kong' not in actions:
                return f"你没有足够的 [{last_tile}] 来杠"
            
            success, need_draw = room.do_kong(pos, last_tile)
            if success:
                # 杠后补牌（从岭上）
                drawn = room.draw_tile(pos, from_dead_wall=True) if need_draw else None
                tenpai_analysis = room.get_tenpai_analysis(pos)
                return {
                    'action': 'mahjong_kong',
                    'message': f"杠 [{last_tile}]" + (f"，岭上牌 [{drawn}]" if drawn else "") + "，请出牌",
                    'hand': room.hands[pos],
                    'drawn': drawn,
                    'tenpai_analysis': tenpai_analysis,
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f"{player_name} 杠 [{last_tile}]",
                        'room_data': room.get_table_data()
                    }
                }
            return "杠失败"
        
        # 吃
        elif cmd == '/chow':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            # 只有下家能吃
            if pos != room.current_turn:
                return "只有下家才能吃牌"
            
            last_tile = room.last_discard
            if not last_tile:
                return "没有可以吃的牌"
            
            actions = room.check_actions(pos, last_tile)
            if 'chow' not in actions:
                return f"你没有能和 [{last_tile}] 组成顺子的牌"
            
            chow_options = actions['chow'].get('options', [])
            
            # 选择吃的方式
            choice = 0
            if args:
                try:
                    choice = int(args) - 1
                except:
                    pass
            
            if choice < 0 or choice >= len(chow_options):
                if len(chow_options) > 1:
                    opts = ", ".join([f"{i+1}: {' '.join(opt)}" for i, opt in enumerate(chow_options)])
                    return f"请选择吃法: {opts}\n输入 /chow 编号"
                choice = 0
            
            selected = chow_options[choice]
            if room.do_chow(pos, last_tile, selected):
                tenpai_analysis = room.get_tenpai_analysis(pos)
                return {
                    'action': 'mahjong_chow',
                    'message': f"吃 [{' '.join(selected)}]，请出牌",
                    'hand': room.hands[pos],
                    'need_discard': True,  # 吃后需要出牌
                    'tenpai_analysis': tenpai_analysis,
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f"{player_name} 吃 [{' '.join(selected)}]",
                        'room_data': room.get_table_data()
                    }
                }
            return "吃失败"
        
        # 过（放弃吃碰杠）
        elif cmd == '/pass':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            # 检查该玩家是否在可操作列表中
            if pos not in room.action_players:
                return "当前无需操作"
            
            # 如果该玩家可以荣和，标记放弃荣和
            actions = room.check_actions(pos, room.last_discard) if room.last_discard else {}
            if 'win' in actions:
                room.pass_ron(pos)
            
            # 标记该玩家放弃操作
            room.player_pass(pos)
            
            # 如果所有人都pass了，下家摸牌，游戏继续
            if not room.waiting_for_action:
                next_pos = room.current_turn
                drawn = room.draw_tile(next_pos)
                
                # 检查是否荒牌流局
                if drawn is None:
                    ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                    room.state = 'finished'
                    
                    tenpai_names = [room.players[i] for i in ryuukyoku_result['tenpai']]
                    noten_names = [room.players[i] for i in ryuukyoku_result['noten']]
                    
                    msg_lines = ["过", "荒牌流局！牌山已摸完"]
                    if tenpai_names:
                        msg_lines.append(f"📗 听牌: {', '.join(tenpai_names)}")
                    if noten_names:
                        msg_lines.append(f"📕 未听: {', '.join(noten_names)}")
                    
                    for i in range(4):
                        change = ryuukyoku_result['score_changes'][i]
                        if change != 0:
                            sign = '+' if change > 0 else ''
                            msg_lines.append(f"  {room.players[i]}: {sign}{change}")
                    
                    if ryuukyoku_result.get('renchan'):
                        msg_lines.append(f"🔄 {room.players[room.dealer]} 连庄")
                    else:
                        msg_lines.append(f"➡️ 轮庄")
                    
                    msg_lines.append("")
                    msg_lines.append("输入 /next 开始下一局")
                    
                    return {
                        'action': 'mahjong_ryuukyoku',
                        'message': '\n'.join(msg_lines),
                        'room_data': room.get_table_data(),
                        'ryuukyoku_result': ryuukyoku_result,
                        'notify_room': {
                            'room_id': room.room_id,
                            'message': '\n'.join(msg_lines[1:]),  # 不包含"过"
                            'room_data': room.get_table_data()
                        }
                    }
                
                next_player = room.players[next_pos]
                
                return {
                    'action': 'mahjong_pass_complete',
                    'message': f"过，轮到 {next_player}",
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f"等待操作(0)，轮到 {next_player}",
                        'discard_info': {
                            'player': None,
                            'tile': None,
                            'next_player': next_player,
                            'drawn_tile': drawn
                        },
                        'room_data': room.get_table_data()
                    }
                }
            
            # 还有人没操作，通知其他人剩余人数
            remaining = len(room.action_players)
            next_pos = room.current_turn
            next_player = room.players[next_pos]
            return {
                'action': 'mahjong_pass',
                'message': f"过 [等待操作({remaining})]",
                'notify_room': {
                    'room_id': room.room_id,
                    'message': f"[等待操作({remaining})]，轮到 {next_player}",
                    'room_data': room.get_table_data()
                }
            }
        
        # 九种九牌流局
        elif cmd == '/kyuushu' or cmd == '/9':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            if room.current_turn != pos:
                return "还没轮到你"
            
            if not room.check_kyuushu_kyuuhai(pos):
                return "不满足九种九牌条件（需要第一巡、手牌有9种以上幺九牌、无人鸣牌）"
            
            # 执行九种九牌流局
            room.state = 'finished'
            
            return {
                'action': 'mahjong_ryuukyoku',
                'message': f"九种九牌！流局",
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'message': f"{player_name} 宣告九种九牌！流局",
                    'room_data': room.get_table_data()
                }
            }
        
        # 查看听牌
        elif cmd == '/tenpai' or cmd == '/t':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            hand = room.hands[pos]
            
            # 如果手牌是14张（刚摸牌），需要检查打掉每张牌后的听牌情况
            if len(hand) == 14 or (len(hand) - 1) % 3 == 0:
                # 手牌多一张，检查每张牌打掉后的听牌情况
                results = []
                checked = set()
                for tile in hand:
                    if tile in checked:
                        continue
                    checked.add(tile)
                    
                    temp_hand = hand.copy()
                    temp_hand.remove(tile)
                    
                    original = room.hands[pos]
                    room.hands[pos] = temp_hand
                    waiting = room.get_tenpai_tiles(pos)
                    room.hands[pos] = original
                    
                    if waiting:
                        results.append(f"打 [{tile}] → 听 {', '.join([f'[{w}]' for w in waiting])}")
                
                if results:
                    return "听牌分析:\n" + "\n".join(results)
                else:
                    return "当前无法听牌"
            else:
                # 正常13张牌，直接检查听牌
                waiting = room.get_tenpai_tiles(pos)
                if waiting:
                    return f"你正在听: {', '.join([f'[{w}]' for w in waiting])}"
                else:
                    return "你还没有听牌"
        
        # 胡牌（荣和）
        elif cmd == '/hu' or cmd == '/ron':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            last_tile = room.last_discard
            
            if not last_tile:
                return "没有可以胡的牌"
            
            # 检查振听
            if room.check_furiten(pos):
                return "振听状态，不能荣和（只能自摸）"
            
            # 检查是否可以胡
            actions = room.check_actions(pos, last_tile)
            if 'win' not in actions:
                return "你不能和这张牌"
            
            # 声明荣和
            ron_result = room.declare_ron(pos)
            
            if ron_result == 'waiting':
                # 等待其他玩家决定
                return {
                    'action': 'mahjong_ron_waiting',
                    'message': f"荣和宣言！等待其他玩家...",
                    'room_data': room.get_table_data()
                }
            
            if ron_result == 'triple_ron':
                # 三家和了流局
                room.state = 'finished'
                room.waiting_for_action = False
                room.action_players = []
                room.clear_ron_state()
                
                return {
                    'action': 'mahjong_ryuukyoku',
                    'message': f"三家和了！流局\n\n三人同时宣告荣和，本局流局。",
                    'room_data': room.get_table_data(),
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': f"三家和了！流局\n\n三人同时宣告荣和，本局流局。\n\n输入 /next 开始下一局",
                        'room_data': room.get_table_data()
                    }
                }
            
            # 处理荣和（单人或双人）
            winners = room.get_ron_winners()
            discarder_pos = room.last_discarder
            discarder_name = room.players[discarder_pos] if discarder_pos is not None else "?"
            
            all_results = []
            all_win_animations = []
            
            for winner_pos, tile in winners:
                result = room.process_win(winner_pos, tile, is_tsumo=False, loser_pos=discarder_pos)
                
                if result.get('success'):
                    all_results.append(result)
                    winner_name = room.players[winner_pos]
                    all_win_animations.append({
                        'winner': winner_name,
                        'win_type': 'ron',
                        'tile': tile,
                        'loser': discarder_name,
                        'yakus': result['yakus'],
                        'han': result['han'],
                        'fu': result['fu'],
                        'score': result['score'],
                        'is_yakuman': result['is_yakuman']
                    })
            
            room.clear_ron_state()
            
            if not all_results:
                return f"无役"
            
            # 游戏结束
            room.state = 'finished'
            room.waiting_for_action = False
            room.action_players = []
            
            # 从弃牌堆移除
            if discarder_pos is not None and room.discards[discarder_pos]:
                if room.discards[discarder_pos][-1] == last_tile:
                    room.discards[discarder_pos].pop()
            
            return {
                'action': 'mahjong_win',
                'win_animation': all_win_animations[0] if len(all_win_animations) == 1 else all_win_animations,
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'win_animation': all_win_animations[0] if len(all_win_animations) == 1 else all_win_animations,
                    'room_data': room.get_table_data()
                }
            }
        
        # 自摸
        elif cmd == '/tsumo':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            # 检查是否轮到自己
            if room.current_turn != pos:
                return "还没轮到你"
            
            # 检查是否刚摸牌
            if not room.just_drew:
                return "需要先摸牌才能自摸"
            
            hand = room.hands[pos]
            if not hand:
                return "无法自摸"
            
            # 最后摸到的牌
            tsumo_tile = hand[-1]
            
            # 检查是否能胡
            if not room.can_win(hand[:-1], tsumo_tile):
                return "你不能自摸"
            
            # 执行自摸结算
            result = room.process_win(pos, tsumo_tile, is_tsumo=True)
            
            if not result.get('success'):
                return f"{result.get('error', '无役')}"
            
            room.state = 'finished'
            room.waiting_for_action = False
            
            return {
                'action': 'mahjong_win',
                'win_animation': {
                    'winner': player_name,
                    'win_type': 'tsumo',
                    'tile': tsumo_tile,
                    'yakus': result['yakus'],
                    'han': result['han'],
                    'fu': result['fu'],
                    'score': result['score'],
                    'is_yakuman': result['is_yakuman']
                },
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'win_animation': {
                        'winner': player_name,
                        'win_type': 'tsumo',
                        'tile': tsumo_tile,
                        'yakus': result['yakus'],
                        'han': result['han'],
                        'fu': result['fu'],
                        'score': result['score'],
                        'is_yakuman': result['is_yakuman']
                    },
                    'room_data': room.get_table_data()
                }
            }
        
        # 立直
        elif cmd == '/riichi':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            if room.current_turn != pos:
                return "还没轮到你"
            
            if not args:
                return "用法: /riichi <要打的牌编号>\n例如: /riichi 1"
            
            # 获取要打的牌
            arg = args.strip()
            hand = room.hands[pos]
            
            if arg.isdigit():
                idx = int(arg) - 1
                if idx < 0 or idx >= len(hand):
                    return f"无效编号，手牌共 {len(hand)} 张"
                discard_tile = hand[idx]
            else:
                discard_tile = arg
                if discard_tile not in hand:
                    return f"你没有这张牌: {discard_tile}"
            
            # 宣告立直
            success, error = room.declare_riichi(pos, discard_tile)
            if not success:
                return f"{error}"
            
            # 打出立直宣言牌
            room.discard_tile(pos, discard_tile)
            
            next_pos = room.current_turn
            next_player = room.players[next_pos]
            
            # 立直后检查是否有人可以吃碰杠胡
            if room.waiting_for_action:
                action_count = len(room.action_players)
                action_hint = f" [等待操作({action_count})]" if action_count > 0 else ""
                return {
                    'action': 'mahjong_discard',  # 使用discard以复用后续流程
                    'message': f"立直！打出 [{discard_tile}]{action_hint}",
                    'hand': room.hands[pos],
                    'room_data': room.get_table_data(),
                    'is_riichi': True,
                    'notify_room': {
                        'room_id': room.room_id,
                        'discard_info': {
                            'player': player_name,
                            'tile': discard_tile,
                            'next_player': next_player,
                            'drawn_tile': None,
                            'waiting_action': True,
                            'is_riichi': True
                        },
                        'room_data': room.get_table_data()
                    }
                }
            
            # 没人操作，下家摸牌
            drawn = room.draw_tile(next_pos)
            
            # 检查是否荒牌流局
            if drawn is None:
                ryuukyoku_result = room.process_ryuukyoku('exhaustive')
                tenpai_names = [room.players[i] for i in ryuukyoku_result['tenpai']]
                noten_names = [room.players[i] for i in ryuukyoku_result['noten']]
                renchan = ryuukyoku_result.get('renchan', False)
                
                return {
                    'action': 'mahjong_ryuukyoku',
                    'message': f"立直！打出 [{discard_tile}]",
                    'hand': room.hands[pos],
                    'room_data': room.get_table_data(),
                    'ryuukyoku': ryuukyoku_result,
                    'notify_room': {
                        'room_id': room.room_id,
                        'message': '',
                        'room_data': room.get_table_data(),
                        'tenpai_names': tenpai_names,
                        'noten_names': noten_names,
                        'renchan': renchan,
                        'score_changes': ryuukyoku_result['score_changes']
                    }
                }
            
            return {
                'action': 'mahjong_discard',  # 使用discard以复用后续流程
                'message': f"立直！打出 [{discard_tile}]",
                'hand': room.hands[pos],
                'room_data': room.get_table_data(),
                'is_riichi': True,
                'notify_room': {
                    'room_id': room.room_id,
                    'discard_info': {
                        'player': player_name,
                        'tile': discard_tile,
                        'next_player': next_player,
                        'drawn_tile': drawn,
                        'waiting_action': False,
                        'is_riichi': True
                    },
                    'room_data': room.get_table_data()
                }
            }
        
        # 暗杠
        elif cmd == '/ankan':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            if room.current_turn != pos:
                return "还没轮到你"
            
            # 检查可以暗杠的牌
            kong_options = room.check_self_kong(pos)
            concealed_kongs = [k for k in kong_options if k['type'] == 'concealed']
            
            if not concealed_kongs:
                return "没有可以暗杠的牌"
            
            # 选择要杠的牌
            choice = 0
            if args:
                try:
                    choice = int(args) - 1
                except:
                    # 可能是牌名
                    for i, k in enumerate(concealed_kongs):
                        if k['tile'] == args.strip():
                            choice = i
                            break
            
            if choice < 0 or choice >= len(concealed_kongs):
                if len(concealed_kongs) > 1:
                    opts = ", ".join([f"{i+1}: {k['tile']}" for i, k in enumerate(concealed_kongs)])
                    return f"请选择暗杠: {opts}\n输入 /ankan 编号"
                choice = 0
            
            tile = concealed_kongs[choice]['tile']
            success, need_draw = room.do_concealed_kong(pos, tile)
            
            if not success:
                return "暗杠失败"
            
            # 岭上摸牌
            drawn = None
            if need_draw:
                drawn = room.draw_tile(pos, from_dead_wall=True)
            
            tenpai_analysis = room.get_tenpai_analysis(pos)
            return {
                'action': 'mahjong_ankan',
                'message': f"暗杠！[{tile}]\n" + (f"岭上牌: [{drawn}]" if drawn else "") + "\n请出牌",
                'hand': room.hands[pos],
                'drawn': drawn,
                'tenpai_analysis': tenpai_analysis,
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'message': f"{player_name} 暗杠！",
                    'room_data': room.get_table_data()
                }
            }
        
        # 加杠
        elif cmd == '/kakan':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            
            if room.current_turn != pos:
                return "还没轮到你"
            
            # 检查可以加杠的牌
            kong_options = room.check_self_kong(pos)
            added_kongs = [k for k in kong_options if k['type'] == 'added']
            
            if not added_kongs:
                return "没有可以加杠的牌"
            
            # 选择要杠的牌
            choice = 0
            if args:
                try:
                    choice = int(args) - 1
                except:
                    for i, k in enumerate(added_kongs):
                        if k['tile'] == args.strip():
                            choice = i
                            break
            
            if choice < 0 or choice >= len(added_kongs):
                if len(added_kongs) > 1:
                    opts = ", ".join([f"{i+1}: {k['tile']}" for i, k in enumerate(added_kongs)])
                    return f"请选择加杠: {opts}\n输入 /kakan 编号"
                choice = 0
            
            tile = added_kongs[choice]['tile']
            success, can_chankan, need_draw = room.do_added_kong(pos, tile)
            
            if not success:
                return "加杠失败"
            
            # 检查是否有人可以抢杠
            if can_chankan:
                room.waiting_for_action = True
                room.action_players = []
                for i in range(4):
                    if i != pos and room.can_win(room.hands[i], tile):
                        room.action_players.append(i)
                
                if room.action_players:
                    return {
                        'action': 'mahjong_kakan',
                        'message': f"加杠！[{tile}]\n⚠ 可能被抢杠...",
                        'hand': room.hands[pos],
                        'room_data': room.get_table_data(),
                        'notify_room': {
                            'room_id': room.room_id,
                            'message': f"{player_name} 加杠 [{tile}]\n⚠ 可抢杠！",
                            'chankan_tile': tile,
                            'room_data': room.get_table_data()
                        }
                    }
            
            # 无人抢杠，岭上摸牌
            drawn = None
            if need_draw:
                drawn = room.draw_tile(pos, from_dead_wall=True)
            
            room.chankan_tile = None
            
            tenpai_analysis = room.get_tenpai_analysis(pos)
            return {
                'action': 'mahjong_kakan',
                'message': f"加杠！[{tile}]\n" + (f"岭上牌: [{drawn}]" if drawn else "") + "\n请出牌",
                'hand': room.hands[pos],
                'drawn': drawn,
                'tenpai_analysis': tenpai_analysis,
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'message': f"{player_name} 加杠 [{tile}]",
                    'room_data': room.get_table_data()
                }
            }
        
        # 抢杠
        elif cmd == '/chankan':
            room = engine.get_player_room(player_name)
            if not room or room.state != 'playing':
                return "游戏未开始"
            
            pos = room.get_position(player_name)
            tile = room.chankan_tile
            
            if not tile:
                return "没有可以抢杠的牌"
            
            if pos not in room.action_players:
                return "你不能抢杠"
            
            # 检查是否能胡
            if not room.can_win(room.hands[pos], tile):
                return "你不能和这张牌"
            
            # 执行抢杠胡
            # 找到加杠的人
            kakan_pos = room.current_turn
            result = room.process_win(pos, tile, is_tsumo=False, loser_pos=kakan_pos)
            
            if not result.get('success'):
                return f"{result.get('error', '无役')}"
            
            yaku_text = "\n".join([f"  {y[0]} ({y[1]}番)" if not y[2] else f"  ★{y[0]} (役满)" for y in result['yakus']])
            
            room.state = 'finished'
            room.waiting_for_action = False
            room.chankan_tile = None
            
            score_text = f"{result['han']}番{result['fu']}符 {result['score']}点" if not result['is_yakuman'] else f"役满 {result['score']}点"
            
            return {
                'action': 'mahjong_win',
                'message': f"抢杠和！[{tile}]\n\n【役种】\n{yaku_text}\n\n【点数计算】\n{score_text}",
                'result': result,
                'room_data': room.get_table_data(),
                'notify_room': {
                    'room_id': room.room_id,
                    'message': f"{player_name} 抢杠和！[{tile}]\n\n【役种】\n{yaku_text}\n\n【点数计算】\n{score_text}",
                    'result': result,
                    'room_data': room.get_table_data()
                }
            }
        
        return None
    
    def _do_back(self, player_name):
        """返回上一级"""
        location = self.get_player_location(player_name)
        
        if location == 'lobby':
            return "你已经在大厅了。"
        
        # 麻将对局中 -> 离开对局（需确认）
        if location == 'mahjong_playing':
            engine = self.game_engines.get('mahjong')
            if engine:
                room = engine.get_player_room(player_name)
                if room and room.state == 'playing':
                    # 设置待确认状态
                    self.pending_confirms[player_name] = 'back'
                    return {
                        'action': 'confirm_prompt',
                        'message': "⚠️ 游戏进行中！确定要退出吗？（会被记为逃跑）\n输入 /y 确认，其他任意键取消。"
                    }
            # 游戏已结束，直接回房间
            self.set_player_location(player_name, 'mahjong_room')
            return {
                'action': 'location_update',
                'location': 'mahjong_room',
                'message': "已返回房间。"
            }
        
        # 麻将房间 -> 离开房间
        if location == 'mahjong_room':
            engine = self.game_engines.get('mahjong')
            if engine:
                room, error = engine.leave_room(player_name)
            self.set_player_location(player_name, 'mahjong')
            result = {
                'action': 'back_to_game',
                'location': 'mahjong',
                'message': "已离开房间"
            }
            if room:
                result['notify_room'] = {
                    'room_id': room.room_id,
                    'message': f"{player_name} 离开了房间",
                    'room_data': room.get_table_data()
                }
            return result
        
        # 麻将游戏 -> 大厅
        if location == 'mahjong':
            self.set_player_location(player_name, 'lobby')
            return {
                'action': 'location_update',
                'location': 'lobby',
                'message': "已返回游戏大厅。\n输入 /games 查看可用游戏。"
            }
        
        # JRPG -> 大厅
        if location == 'jrpg':
            self.set_player_location(player_name, 'lobby')
            return {
                'action': 'location_update',
                'location': 'lobby',
                'message': "已返回游戏大厅。\n输入 /games 查看可用游戏。"
            }
        
        # 默认返回父位置
        parent = self.get_parent_location(location)
        if parent:
            self.set_player_location(player_name, parent)
            return {
                'action': 'location_update',
                'location': parent,
                'message': f"已返回{LOCATION_HIERARCHY.get(parent, ('', None))[0]}。"
            }
        
        return "无法返回上一级。"
    
    def _do_back_confirm(self, player_name):
        """确认退出对局"""
        location = self.get_player_location(player_name)
        
        if location != 'mahjong_playing':
            return "无需确认。"
        
        engine = self.game_engines.get('mahjong')
        if engine:
            room = engine.get_player_room(player_name)
            if room:
                # 处理逃跑逻辑（这里简化处理，直接离开）
                engine.leave_room(player_name)
        
        self.set_player_location(player_name, 'mahjong')
        return {
            'action': 'back_to_game',
            'location': 'mahjong',
            'message': "已退出对局，返回麻将游戏。"
        }
    
    def _do_home(self, player_name):
        """直接返回大厅"""
        location = self.get_player_location(player_name)
        
        if location == 'lobby':
            return "你已经在大厅了。"
        
        # 如果在麻将相关位置，需要清理
        if location.startswith('mahjong'):
            engine = self.game_engines.get('mahjong')
            if engine:
                room = engine.get_player_room(player_name)
                if room and room.state == 'playing':
                    return "⚠️ 游戏进行中！请先输入 /back 退出对局。"
                engine.leave_room(player_name)
        
        self.set_player_location(player_name, 'lobby')
        return {
            'action': 'location_update',
            'location': 'lobby',
            'message': "已返回游戏大厅。\n输入 /games 查看可用游戏。"
        }
    
    def get_player_room_data(self, player_name):
        """获取玩家所在房间的数据（用于UI更新）"""
        location = self.get_player_location(player_name)
        if location in ('mahjong_room', 'mahjong_playing') and 'mahjong' in self.game_engines:
            engine = self.game_engines['mahjong']
            room = engine.get_player_room(player_name)
            if room:
                return {
                    'game': 'mahjong',
                    'room_data': room.get_table_data()
                }
        return None
    
    def _do_rename(self, player_name, player_data, new_name):
        """执行改名"""
        from .player_manager import PlayerManager
        
        # 再次检查用户名是否可用
        if PlayerManager.player_exists(new_name):
            return f"用户名 '{new_name}' 已被使用。"
        
        old_name = player_name
        rename_cards = player_data.get('rename_cards', 2)
        
        # 执行改名
        success = PlayerManager.rename_player(old_name, new_name)
        if not success:
            return "改名失败，请稍后重试。"
        
        # 更新玩家数据
        player_data['name'] = new_name
        player_data['rename_cards'] = rename_cards - 1
        
        # 更新引擎中的引用
        if old_name in self.online_players:
            del self.online_players[old_name]
            self.online_players[new_name] = player_data
        if old_name in self.player_locations:
            location = self.player_locations[old_name]
            del self.player_locations[old_name]
            self.player_locations[new_name] = location
        if old_name in self.pending_confirms:
            del self.pending_confirms[old_name]
        
        return {
            'action': 'rename_success',
            'old_name': old_name,
            'new_name': new_name,
            'message': f"用户名已改为 '{new_name}'！\n剩余改名卡: {rename_cards - 1}张"
        }
    
    def _do_change_password(self, player_name, new_password):
        """执行修改密码"""
        from .player_manager import PlayerManager
        
        success = PlayerManager.change_password(player_name, new_password)
        if success:
            return "密码修改成功！"
        else:
            return "密码修改失败，请稍后重试。"
    
    def _do_delete_account(self, player_name, password):
        """执行删除账号"""
        from .player_manager import PlayerManager
        
        # 验证密码
        if not PlayerManager.verify_password(player_name, password):
            return "密码错误。账号删除已取消。"
        
        # 从游戏中清理
        location = self.get_player_location(player_name)
        if location.startswith('mahjong') and 'mahjong' in self.game_engines:
            self.game_engines['mahjong'].leave_room(player_name)
        
        # 删除账号
        success = PlayerManager.delete_player(player_name)
        if success:
            # 清理引擎状态
            if player_name in self.online_players:
                del self.online_players[player_name]
            if player_name in self.player_locations:
                del self.player_locations[player_name]
            if player_name in self.pending_confirms:
                del self.pending_confirms[player_name]
            
            return {'action': 'account_deleted', 'message': "账号已删除。再见！"}
        else:
            return "删除账号失败，请稍后重试。"
