"""
游戏大厅指令引擎

职责:
- 全局指令处理（帮助、资料、头衔、背包等）
- 游戏引擎的注册和路由
- 玩家位置管理
- 大厅级待确认状态（exit/rename/password/delete）

游戏内指令一律委托给对应引擎的标准接口处理。
"""

from .config import LOCATION_HIERARCHY, SERVER_VERSION
from games import get_game, get_all_games, GAMES


class LobbyEngine:
    """游戏大厅指令引擎"""

    def __init__(self):
        self.game_engines = {}  # 各游戏的引擎实例
        self.player_locations = {}  # {player_name: location}
        self.online_players = {}  # {player_name: player_data}
        self.invite_callback = None  # 邀请回调函数
        self.pending_confirms = {}  # 大厅级待确认 {player_name: {'type':..., 'data':...}}

    def set_invite_callback(self, callback):
        """设置邀请通知回调"""
        self.invite_callback = callback

    def register_player(self, player_name, player_data):
        """注册在线玩家"""
        self.online_players[player_name] = player_data
        self.player_locations[player_name] = 'lobby'
        self.pending_confirms.pop(player_name, None)

    def unregister_player(self, player_name):
        """注销玩家，返回需要通知的房间信息列表"""
        notifications = []

        # 委托引擎处理断线
        game_id = self._get_game_for_location(
            self.get_player_location(player_name))
        if game_id:
            engine = self._get_engine(game_id, player_name)
            if engine and hasattr(engine, 'handle_disconnect'):
                notifications = engine.handle_disconnect(self, player_name)
            # per_player 引擎断线后清除实例
            info = self._get_game_info(game_id)
            if info.get('per_player'):
                self.game_engines.pop(f'{game_id}_{player_name}', None)

        self.pending_confirms.pop(player_name, None)
        self.player_locations.pop(player_name, None)
        self.online_players.pop(player_name, None)
        return notifications

    def get_player_location(self, player_name):
        """获取玩家当前位置"""
        return self.player_locations.get(player_name, 'lobby')

    def set_player_location(self, player_name, location):
        """设置玩家位置"""
        self.player_locations[player_name] = location

    # ── 布局校验 ──

    def _validate_layout(self, data, depth=0):
        """白名单校验布局 JSON，防止注入"""
        if depth > 10:
            return False
        if not isinstance(data, dict):
            return False
        t = data.get('type')
        if t == 'pane':
            mod = data.get('module')
            pid = data.get('id')
            if mod is not None and not isinstance(mod, str):
                return False
            if pid is not None and not isinstance(pid, str):
                return False
            return True
        children = data.get('children')
        weights = data.get('weights')
        if not isinstance(children, list):
            return False
        if weights is not None and not isinstance(weights, list):
            return False
        return all(self._validate_layout(c, depth + 1) for c in children)

    # ── 位置工具 ──

    def get_location_path(self, location):
        """获取位置的完整路径（面包屑导航）"""
        path = []
        current = location
        while current:
            info = LOCATION_HIERARCHY.get(current)
            if info:
                path.append(info[0])
                current = info[1]
            else:
                path.append(current)
                break
        path.reverse()
        if not path:
            return '游戏大厅'
        return ' > '.join(path)

    def get_parent_location(self, location):
        """获取父位置"""
        info = LOCATION_HIERARCHY.get(location)
        if info:
            return info[1] or 'lobby'
        return 'lobby'

    def get_online_player_names(self):
        """获取在线玩家名列表"""
        return list(self.online_players.keys())

    # ── 游戏路由 helpers ──

    def _get_game_for_location(self, location):
        """根据位置确定玩家在哪个游戏中"""
        if location in ('lobby', 'profile'):
            return None
        for game_id, module in GAMES.items():
            info = getattr(module, 'GAME_INFO', {})
            if location in info.get('locations', {}):
                return game_id
        # 后备: 根据前缀
        for game_id in GAMES:
            if location.startswith(game_id):
                return game_id
        return None

    def _get_game_info(self, game_id):
        """获取游戏的GAME_INFO"""
        module = GAMES.get(game_id)
        if module:
            return getattr(module, 'GAME_INFO', {})
        return {}

    def _get_engine(self, game_id, player_name=None):
        """获取游戏引擎实例（per_player 用带玩家名的 key）"""
        info = self._get_game_info(game_id)
        if info.get('per_player'):
            return self.game_engines.get(f'{game_id}_{player_name}')
        return self.game_engines.get(game_id)

    def _ensure_engine(self, game_id, player_name=None):
        """确保引擎存在，不存在则创建"""
        info = self._get_game_info(game_id)
        if info.get('per_player'):
            key = f'{game_id}_{player_name}'
        else:
            key = game_id

        if key not in self.game_engines:
            create = info.get('create_engine')
            if create:
                self.game_engines[key] = create()

        return self.game_engines.get(key)

    # ── 帮助 / 列表 ──

    def get_main_help(self):
        """获取主帮助文本"""
        from .text_utils import pad_left
        games = get_all_games()
        game_list = ""
        for game in games:
            icon = game.get('icon', '🎮')
            name = game.get('name', game.get('id', '???'))
            game_id = game.get('id', '???')
            game_list += f"  {icon} {pad_left(name, 12)} /play {game_id}\n"

        return (
            "\n========== 游戏大厅 ==========\n\n"
            "【基础指令】\n"
            "  /help           - 显示此帮助\n"
            "  /help <游戏>    - 查看游戏说明书\n"
            "  /games          - 查看游戏列表\n"
            "  /play <游戏>    - 进入游戏\n\n"
            "【导航指令】\n"
            "  /back           - 返回上一级\n"
            "  /quit           - 离开当前游戏\n"
            "  /home           - 直接返回大厅\n\n"
            "【可用游戏】\n"
            f"{game_list}"
            "\n【个人中心】\n"
            "  /profile        - 查看个人资料\n"
            "  /mytitle        - 查看我的头衔\n"
            "  /alltitle       - 查看头衔图鉴\n"
            "  /title <编号>   - 切换显示的头衔\n\n"
            "【其他指令】\n"
            "  /version        - 查看版本信息\n"
            "  /clear          - 清屏\n"
            "  /exit           - 关闭程序\n\n"
            "==============================\n"
        )

    def get_game_help(self, game_id, page=None):
        """获取游戏帮助文本（通用）"""
        game_module = get_game(game_id)
        if not game_module:
            return f"未找到游戏: {game_id}\n使用 /games 查看可用游戏列表。"

        # 优先: 模块提供的 get_help_text(page)
        get_help = getattr(game_module, 'get_help_text', None)
        if get_help:
            return get_help(page)

        info = getattr(game_module, 'GAME_INFO', {})

        # 尝试从帮助文件读取
        import os
        for filename in ('help.md', 'help.txt'):
            try:
                help_path = os.path.join(
                    os.path.dirname(game_module.__file__), filename)
                with open(help_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except (OSError, AttributeError):
                pass

        # 回退到基本信息
        name = info.get('name', game_id)
        desc = info.get('description', '暂无描述')
        min_p = info.get('min_players', '?')
        max_p = info.get('max_players', '?')
        return (f"{name}\n{desc}\n\n玩家人数: {min_p}-{max_p}人\n\n"
                f"使用 /play {game_id} 开始游戏\n")

    def get_games_list(self):
        """获取游戏列表"""
        games = get_all_games()
        text = "【游戏列表】\n\n"
        for game in games:
            icon = game.get('icon', '🎮')
            name = game.get('name', game.get('id', '???'))
            game_id = game.get('id', '???')
            min_p = game.get('min_players', '?')
            max_p = game.get('max_players', '?')
            desc = game.get('description', '')
            text += f"  {icon} {name}\n"
            text += f"     ID: {game_id}\n"
            text += f"     人数: {min_p}-{max_p}人\n"
            if desc:
                text += f"     {desc}\n"
            text += "\n"
        text += "使用 /play <游戏ID> 进入游戏"
        return text

    # ── 个人资料 ──

    def get_profile(self, player_data):
        """获取个人资料并进入profile页面"""
        player_name = player_data['name']
        inventory = player_data.get('inventory', {})
        rename_cards = inventory.get('rename_card', 0)

        self.set_player_location(player_name, 'profile')

        from .user_schema import get_title_name
        titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
        displayed = titles.get('displayed', [])
        displayed_names = ' | '.join(get_title_name(t) for t in displayed) if displayed else '(无)'

        # 从各游戏引擎收集资料附加行
        profile_extras = []
        for game_id in GAMES:
            engine = self._get_engine(game_id, player_name)
            if engine and hasattr(engine, 'get_profile_extras'):
                line = engine.get_profile_extras(player_data)
                if line:
                    profile_extras.append(line)
        extras_text = '\n'.join(f"{line}" for line in profile_extras)
        if extras_text:
            extras_text += '\n'

        return {
            'action': 'location_update',
            'message': (
                f"\n========== 个人资料 ==========\n"
                f"昵称: {player_data['name']}\n"
                f"等级: Lv.{player_data.get('level', 1)}\n"
                f"金币: {player_data.get('gold', 0)}G\n"
                f"{extras_text}"
                f"头衔: 【{displayed_names}】\n"
                f"饰品: {player_data.get('accessory', '无')}\n"
                f"改名卡: {rename_cards}张\n"
                f"注册时间: {player_data.get('created_at', '未知')}\n"
                f"\n==============================\n\n"
                "【可用操作】\n"
                "  /avatar        - 修改头像\n"
                "  /mytitle       - 查看我的头衔\n"
                "  /alltitle      - 查看头衔图鉴\n"
                "  /rename <新名> - 修改用户名\n"
                "  /password      - 修改密码\n"
                "  /delete        - 删除账号\n"
                "  /back          - 返回大厅\n"
                "  /home          - 返回大厅\n"
            )
        }

    def _handle_profile_command(self, player_name, player_data, cmd, args):
        """处理个人资料页面的指令"""
        if cmd == '/avatar':
            return {'action': 'request_avatar'}

        if cmd == '/rename':
            if not args:
                return "用法: /rename <新用户名>"
            new_name = args
            rename_cards = player_data.get('inventory', {}).get('rename_card', 0)
            if rename_cards <= 0:
                return "你没有改名卡了。"
            if len(new_name) < 2 or len(new_name) > 12:
                return "用户名长度需要在2-12个字符之间。"
            from .player_manager import PlayerManager
            if PlayerManager.player_exists(new_name):
                return f"用户名 '{new_name}' 已被使用。"
            self.pending_confirms[player_name] = {
                'type': 'rename',
                'data': new_name
            }
            return f"确定要将用户名改为 '{new_name}' 吗？（消耗1张改名卡）\n输入 /y 确认，其他任意键取消。"

        if cmd == '/password':
            self.pending_confirms[player_name] = {'type': 'password_start'}
            return "请输入新密码（6-20个字符）："

        if cmd == '/delete':
            self.pending_confirms[player_name] = {'type': 'delete_start'}
            return "警告：删除账号不可恢复！\n请输入你的用户名以确认："

        return None

    # ══════════════════════════════════════════════════
    #  核心指令处理
    # ══════════════════════════════════════════════════

    def process_command(self, player_data, command):
        """处理指令"""
        player_name = player_data['name']
        parts = command.strip().split(None, 1)
        cmd = parts[0].lower() if parts else ''
        args = parts[1] if len(parts) > 1 else ''
        location = self.get_player_location(player_name)

        # ── 1. 大厅级待确认状态 ──
        pending = self.pending_confirms.get(player_name)
        if pending:
            result = self._handle_lobby_pending(
                player_name, player_data, cmd, command, pending)
            if result is not None:
                return result

        # ── 2. 全局指令（任何位置有效）──
        if cmd == '/help':
            if args:
                help_parts = args.split(None, 1)
                game_id = help_parts[0].lower()
                page = help_parts[1] if len(help_parts) > 1 else None
                return self.get_game_help(game_id, page)
            # 在游戏中 /help 无参数 → 显示游戏帮助
            game_id = self._get_game_for_location(location)
            if game_id:
                return self.get_game_help(game_id)
            return self.get_main_help()

        if cmd == '/games':
            return self.get_games_list()

        if cmd == '/clear':
            return {'action': 'clear'}

        if cmd == '/version':
            return {'action': 'version', 'message': f"服务器版本: v{SERVER_VERSION}"}

        if cmd == '/exit':
            self.pending_confirms[player_name] = {'type': 'exit'}
            return ('⚠️ /exit 会关闭整个程序！确定要退出吗？输入 /y 确认。\n'
                    '提示: 如果只是想离开当前游戏，请使用 /quit 或 /back')

        if cmd == '/profile':
            return self.get_profile(player_data)

        # ── 3. 背包/头衔指令（任何位置有效）──
        if cmd == '/item':
            return self._cmd_item(player_data, args)

        if cmd == '/mytitle':
            return self._cmd_mytitle(player_data)

        if cmd == '/alltitle':
            return self._cmd_alltitle(player_data, args)

        if cmd == '/title':
            return self._cmd_title(player_name, player_data, args)

        # ── 4. 个人资料页面 ──
        if location == 'profile':
            result = self._handle_profile_command(
                player_name, player_data, cmd, args)
            if result is not None:
                return result
            if cmd in ('/back', '/quit', '/home'):
                self.set_player_location(player_name, 'lobby')
                return {
                    'action': 'location_update',
                    'message': '已返回游戏大厅。\n输入 /games 查看可用游戏。'
                }

        # ── 5. 进入游戏 ──
        if cmd == '/play':
            if location not in ('lobby', 'profile'):
                return '请先返回大厅再进入其他游戏。输入 /home 返回大厅。'
            if not args:
                return '用法: /play <游戏ID>\n使用 /games 查看可用游戏列表。'
            return self._enter_game(player_name, player_data, args.lower().strip())

        # ── 6. 游戏内指令路由 ──
        game_id = self._get_game_for_location(location)
        if game_id:
            engine = self._get_engine(game_id, player_name)
            if engine:
                # /back, /quit, /home 委托引擎
                if cmd == '/back':
                    return engine.handle_back(self, player_name, player_data)
                if cmd in ('/quit', '/home'):
                    return engine.handle_quit(self, player_name, player_data)
                # 其他游戏指令
                result = engine.handle_command(
                    self, player_name, player_data, cmd, args)
                if result is not None:
                    return result
            return f"未知指令。输入 /help {game_id} 查看帮助。"

        # ── 7. 大厅 /back, /quit, /home ──
        if cmd in ('/back', '/quit', '/home'):
            if location == 'lobby':
                return '你已经在大厅了。'
            parent = self.get_parent_location(location)
            self.set_player_location(player_name, parent)
            return {
                'action': 'location_update',
                'message': f"已返回{self.get_location_path(parent)}。"
            }

        if not cmd.startswith('/'):
            if location == 'profile':
                return '请输入头衔编号。使用 /mytitle 查看列表。'
            return None

        return '未知指令。输入 /help 查看帮助。'

    # ── 进入游戏 ──

    def _enter_game(self, player_name, player_data, game_id):
        """通用进入游戏"""
        game_module = get_game(game_id)
        if not game_module:
            return f"未找到游戏: {game_id}"

        engine = self._ensure_engine(game_id, player_name)
        if not engine:
            return f"游戏引擎初始化失败: {game_id}"

        info = self._get_game_info(game_id)

        # 设置位置 — 用游戏根位置
        locations = info.get('locations', {})
        root_location = game_id  # 默认
        for loc_key in locations:
            parent = locations[loc_key][1]
            if parent == 'lobby':
                root_location = loc_key
                break
        self.set_player_location(player_name, root_location)

        # 获取欢迎信息
        if hasattr(engine, 'get_welcome_message'):
            return engine.get_welcome_message(player_data)

        return {
            'action': 'location_update',
            'message': (f"{info.get('icon', '🎮')} 进入 {info.get('name', game_id)}\n\n"
                        f"输入 /help {game_id} 查看游戏说明\n"
                        f"输入 /quit 或 /back 离开游戏\n")
        }

    # ── 大厅级待确认处理 ──

    def _handle_lobby_pending(self, player_name, player_data, cmd, command, pending):
        """处理大厅级待确认状态（exit/rename/password/delete）"""
        pending_type = pending.get('type') if isinstance(pending, dict) else pending
        pending_data = pending.get('data') if isinstance(pending, dict) else None

        # 退出确认
        if pending_type == 'exit':
            self.pending_confirms.pop(player_name, None)
            if cmd == '/y':
                return {'action': 'exit'}
            return '已取消。'

        # 改名确认
        if pending_type == 'rename':
            self.pending_confirms.pop(player_name, None)
            if cmd == '/y':
                return self._do_rename(player_name, player_data, pending_data)
            return '已取消改名。'

        # 修改密码 - 输入新密码
        if pending_type == 'password_start':
            self.pending_confirms.pop(player_name, None)
            new_password = command.strip()
            if len(new_password) < 6 or len(new_password) > 20:
                return '密码长度需要在6-20个字符之间。已取消。'
            self.pending_confirms[player_name] = {
                'type': 'password_confirm',
                'data': new_password
            }
            return '请再次输入新密码确认：'

        # 修改密码 - 确认密码
        if pending_type == 'password_confirm':
            self.pending_confirms.pop(player_name, None)
            if command.strip() != pending_data:
                return '两次输入的密码不一致。已取消。'
            return self._do_change_password(player_name, pending_data)

        # 删除账号 - 确认用户名
        if pending_type == 'delete_start':
            self.pending_confirms.pop(player_name, None)
            input_name = command.strip()
            if input_name != player_name:
                return '用户名不匹配。已取消。'
            self.pending_confirms[player_name] = {'type': 'delete_password'}
            return '请输入你的密码：'

        # 删除账号 - 确认密码
        if pending_type == 'delete_password':
            self.pending_confirms.pop(player_name, None)
            input_password = command.strip()
            return self._do_delete_account(player_name, input_password)

        return None

    # ── 背包/头衔指令 ──

    def _cmd_item(self, player_data, args):
        """背包指令"""
        from .user_schema import ITEM_LIBRARY, ITEM_SOURCES
        inventory = player_data.get('inventory', {})
        gold = player_data.get('gold', 0)
        text = "【背包】\n\n"
        text += f"金币: {gold}\n\n"

        filter_source = args.strip() if args else None
        has_items = False
        for source_id, source_name in ITEM_SOURCES.items():
            if filter_source and filter_source != source_id:
                continue
            items_in_source = []
            for item_id, count in inventory.items():
                if count <= 0:
                    continue
                item_info = ITEM_LIBRARY.get(item_id, {})
                if item_info.get('source') == source_id:
                    items_in_source.append((item_id, count, item_info))
            if items_in_source:
                has_items = True
                text += f"【{source_name}】\n"
                for item_id, count, info in items_in_source:
                    text += f"  {info.get('name', item_id)} x{count} - {info.get('desc', '')}\n"
                text += "\n"

        if not has_items:
            text += "(背包空空如也)\n"
        return text

    def _cmd_mytitle(self, player_data):
        """查看我的头衔"""
        from .user_schema import get_title_name, TITLE_LIBRARY
        titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
        owned = titles.get('owned', [])
        displayed = titles.get('displayed', [])

        text = "【我的头衔库】\n\n"
        if displayed:
            displayed_names = ' | '.join(get_title_name(t) for t in displayed)
            text += f"当前显示: {displayed_names}\n\n"
        else:
            text += "当前显示: (无)\n\n"

        text += "已拥有的头衔:\n"
        for i, title_id in enumerate(owned, 1):
            mark = ' [显示中]' if title_id in displayed else ''
            title_info = TITLE_LIBRARY.get(title_id, {})
            name = title_info.get('name', title_id)
            desc = title_info.get('desc', '')
            text += f"  {i}. {name}{mark} - {desc}\n"

        total_titles = len(TITLE_LIBRARY)
        text += f"\n已收集: {len(owned)}/{total_titles}"
        text += "\n\n/title <编号> - 切换显示（最多3个）"
        text += "\n/title clear - 清除所有显示"
        text += "\n/alltitle - 查看头衔图鉴"
        return text

    def _cmd_alltitle(self, player_data, args):
        """查看头衔图鉴"""
        from .user_schema import TITLE_LIBRARY, TITLE_SOURCES, get_title_name
        titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
        owned = titles.get('owned', [])

        filter_source = args.strip() if args else None
        if filter_source and filter_source not in TITLE_SOURCES:
            text = "可用的筛选类别:\n"
            for src, name in TITLE_SOURCES.items():
                count = sum(1 for t in TITLE_LIBRARY.values() if t.get('source') == src)
                text += f"  /alltitle {src}  {name} ({count}个头衔)\n"
            return text

        text = "【头衔图鉴】\n"
        if filter_source:
            text += f"(筛选: {TITLE_SOURCES.get(filter_source, filter_source)})\n"

        current_source = None
        for tid, info in TITLE_LIBRARY.items():
            source = info.get('source', '')
            if filter_source and source != filter_source:
                continue
            if source != current_source:
                if current_source is not None:
                    text += "\n"
                current_source = source
                text += f"\n--- {TITLE_SOURCES.get(source, source)} ---\n"
            is_owned = tid in owned
            status = '[已获得]' if is_owned else '[未获得]'
            text += f"  {status} {info.get('name', tid)}"
            text += f"       {info.get('desc', '')}\n"
            if not is_owned:
                text += f"       条件: {info.get('condition', '')}\n"
        return text

    def _cmd_title(self, player_name, player_data, args):
        """切换头衔显示"""
        from .user_schema import TITLE_LIBRARY, get_title_name
        from .player_manager import PlayerManager
        titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
        owned = titles.get('owned', [])
        displayed = titles.get('displayed', [])

        if not args:
            return "用法: /title <编号> 或 /title clear"

        if args.strip() == 'clear':
            titles['displayed'] = []
            player_data['titles'] = titles
            PlayerManager.save_player_data(player_name, player_data)
            return '已清除所有显示的头衔。'

        try:
            idx = int(args.strip())
        except ValueError:
            return "用法: /title <编号> 或 /title clear"

        if idx < 1 or idx > len(owned):
            return f"无效的编号。你有 {len(owned)} 个头衔。"

        title_id = owned[idx - 1]
        if title_id in displayed:
            displayed.remove(title_id)
            player_data['titles'] = titles
            PlayerManager.save_player_data(player_name, player_data)
            return f"已取消显示头衔: {get_title_name(title_id)}"

        if len(displayed) >= 3:
            return "最多只能显示3个头衔。请先取消其他头衔。"

        displayed.append(title_id)
        player_data['titles'] = titles
        PlayerManager.save_player_data(player_name, player_data)
        title_display = ' | '.join(get_title_name(t) for t in displayed)
        return f"已添加显示头衔: {get_title_name(title_id)}\n当前显示: {title_display}"

    # ── 通用服务 ──

    def _track_invite(self, player_name, player_data):
        """记录邀请统计并检查friendly头衔"""
        from .player_manager import PlayerManager

        social_stats = player_data.get('social_stats', {})
        social_stats['invites_sent'] = social_stats.get('invites_sent', 0) + 1
        player_data['social_stats'] = social_stats

        if social_stats['invites_sent'] >= 10:
            titles = player_data.get('titles', {'owned': ['newcomer'], 'displayed': ['newcomer']})
            if 'friendly' not in titles['owned']:
                titles['owned'].append('friendly')
                player_data['titles'] = titles

        PlayerManager.save_player_data(player_name, player_data)

    def get_player_room_data(self, player_name):
        """获取玩家所在房间的数据（用于UI更新）— 通用"""
        location = self.get_player_location(player_name)
        game_id = self._get_game_for_location(location)
        if game_id:
            engine = self._get_engine(game_id, player_name)
            if engine and hasattr(engine, 'get_player_room_data'):
                return engine.get_player_room_data(player_name)
        return None

    # ── 账号操作 ──

    def _do_rename(self, player_name, player_data, new_name):
        """执行改名"""
        from .player_manager import PlayerManager

        if PlayerManager.player_exists(new_name):
            return f"用户名 '{new_name}' 已被使用。"

        inventory = player_data.get('inventory', {})
        rename_cards = inventory.get('rename_card', 0)

        old_name = player_name
        success = PlayerManager.rename_player(old_name, new_name)
        if not success:
            return '改名失败，请稍后重试。'

        inventory['rename_card'] = rename_cards - 1
        player_data['inventory'] = inventory
        player_data['name'] = new_name

        if old_name in self.online_players:
            self.online_players[new_name] = self.online_players.pop(old_name)
        location = self.player_locations.pop(old_name, 'lobby')
        self.player_locations[new_name] = location

        PlayerManager.save_player_data(new_name, player_data)

        return {
            'action': 'rename_success',
            'message': f"用户名已改为 '{new_name}'！\n剩余改名卡: {rename_cards - 1}张"
        }

    def _do_change_password(self, player_name, new_password):
        """执行修改密码"""
        from .player_manager import PlayerManager
        success = PlayerManager.change_password(player_name, new_password)
        if success:
            return '密码修改成功！'
        return '密码修改失败，请稍后重试。'

    def _do_delete_account(self, player_name, password):
        """执行删除账号"""
        from .player_manager import PlayerManager

        if not PlayerManager.verify_password(player_name, password):
            return '密码错误。账号删除已取消。'

        for game_id, engine in self.game_engines.items():
            if hasattr(engine, 'leave_room') and hasattr(engine, 'get_player_room'):
                if engine.get_player_room(player_name):
                    engine.leave_room(player_name)

        success = PlayerManager.delete_player(player_name)
        if success:
            self.online_players.pop(player_name, None)
            self.player_locations.pop(player_name, None)
            return {'action': 'account_deleted', 'message': '账号已删除。再见！'}
        return '删除账号失败，请稍后重试。'
