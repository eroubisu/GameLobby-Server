"""
JRPG 游戏引擎 - 处理游戏逻辑和指令
"""

import random


class JRPGEngine:
    """JRPG游戏引擎 - 处理游戏逻辑"""
    
    def __init__(self, game_data):
        self.game_data = game_data
        self.battles = {}  # {player_name: monster}
    
    def get_help_text(self):
        """获取帮助文本"""
        return """
========== 指令列表 ==========
【基础】
  /help - 显示帮助
  /status - 查看状态
  /inventory - 查看背包
  
【战斗】
  /explore - 探索当前区域
  /attack - 攻击怪物
  /flee - 逃跑
  
【移动】
  /areas - 查看所有区域
  /goto <区域> - 前往区域
  
【道具】
  /use <道具名> - 使用道具
  
【其他】
  /heal - 休息回血(消耗10金币)
  /clear - 清屏
  /exit - 退出游戏
==============================
"""
    
    def process_command(self, player_data, command):
        """处理玩家指令"""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 指令映射表
        commands = {
            '/help': lambda: self.get_help_text(),
            '/status': lambda: self.cmd_status(player_data),
            '/inventory': lambda: self.cmd_inventory(player_data),
            '/explore': lambda: self.cmd_explore(player_data),
            '/attack': lambda: self.cmd_attack(player_data),
            '/flee': lambda: self.cmd_flee(player_data),
            '/areas': lambda: self.cmd_areas(player_data),
            '/goto': lambda: self.cmd_goto(player_data, args),
            '/use': lambda: self.cmd_use(player_data, args),
            '/heal': lambda: self.cmd_heal(player_data),
            '/clear': lambda: {'action': 'clear'},
            '/exit': lambda: {'action': 'exit_confirm'},
            '/exit_yes': lambda: {'action': 'exit'},
        }
        
        if cmd in commands:
            return commands[cmd]()
        return None
    
    def cmd_status(self, player):
        """查看状态"""
        area = self.game_data.get_area(player['current_area'])
        area_name = area['name'] if area else '未知'
        
        equip_weapon = player['equipment'].get('weapon') or '无'
        equip_armor = player['equipment'].get('armor') or '无'
        
        return f"""
【{player['name']}的状态】
等级: {player['level']}  经验: {player['exp']}/{player['exp_to_next']}
HP: {player['hp']}/{player['max_hp']}
攻击: {player['attack']}  防御: {player['defense']}
金币: {player['gold']}
当前区域: {area_name}
装备-武器: {equip_weapon}
装备-防具: {equip_armor}
"""
    
    def cmd_inventory(self, player):
        """查看背包"""
        if not player['inventory']:
            return "【背包】空空如也"
        
        items = {}
        for item in player['inventory']:
            items[item] = items.get(item, 0) + 1
        
        text = "【背包】\n"
        for item, count in items.items():
            text += f"  {item} x{count}\n"
        return text
    
    def cmd_explore(self, player):
        """探索"""
        name = player['name']
        
        if name in self.battles:
            return "你正在战斗中！请先击败怪物或逃跑。"
        
        monster = self.game_data.get_random_monster_for_area(player['current_area'])
        if not monster:
            return "这个区域没有怪物。"
        
        monster['hp'] = int(monster['hp'] * random.uniform(0.9, 1.1))
        monster['current_hp'] = monster['hp']
        
        self.battles[name] = monster
        
        return f"""
⚔️ 你遇到了 {monster['name']}(Lv.{monster['level']})!
HP: {monster['current_hp']}/{monster['hp']}
攻击: {monster['attack']} 防御: {monster['defense']}

输入 /attack 攻击，/flee 逃跑
"""
    
    def cmd_attack(self, player):
        """攻击"""
        name = player['name']
        
        if name not in self.battles:
            return "你没有在战斗中。使用 /explore 探索。"
        
        monster = self.battles[name]
        result = ""
        
        # 玩家攻击
        player_dmg = max(1, player['attack'] - monster['defense'] + random.randint(-3, 3))
        monster['current_hp'] -= player_dmg
        result += f"你对 {monster['name']} 造成了 {player_dmg} 点伤害！\n"
        
        # 怪物死亡
        if monster['current_hp'] <= 0:
            del self.battles[name]
            
            exp_gain = monster['exp']
            gold_gain = monster['gold']
            player['exp'] += exp_gain
            player['gold'] += gold_gain
            
            result += f"\n🎉 你击败了 {monster['name']}!\n"
            result += f"获得 {exp_gain} 经验, {gold_gain} 金币\n"
            
            for drop in monster.get('drops', []):
                if random.random() < drop['chance']:
                    player['inventory'].append(drop['item'])
                    result += f"获得道具: {drop['item']}\n"
            
            level_up_msg = self.check_level_up(player)
            if level_up_msg:
                result += level_up_msg
            
            return result
        
        # 怪物攻击
        monster_dmg = max(1, monster['attack'] - player['defense'] + random.randint(-2, 2))
        player['hp'] -= monster_dmg
        result += f"{monster['name']} 对你造成了 {monster_dmg} 点伤害！\n"
        result += f"\n你的HP: {player['hp']}/{player['max_hp']}\n"
        result += f"{monster['name']}的HP: {monster['current_hp']}/{monster['hp']}"
        
        if player['hp'] <= 0:
            del self.battles[name]
            player['hp'] = player['max_hp'] // 2
            gold_lost = player['gold'] // 4
            player['gold'] -= gold_lost
            result += f"\n\n💀 你被击败了...失去了 {gold_lost} 金币，在城镇复活。"
            player['current_area'] = 'forest'
        
        return result
    
    def cmd_flee(self, player):
        """逃跑"""
        name = player['name']
        
        if name not in self.battles:
            return "你没有在战斗中。"
        
        if random.random() < 0.6:
            del self.battles[name]
            return "你成功逃跑了！"
        else:
            monster = self.battles[name]
            dmg = max(1, monster['attack'] - player['defense'])
            player['hp'] -= dmg
            
            if player['hp'] <= 0:
                del self.battles[name]
                player['hp'] = player['max_hp'] // 2
                player['current_area'] = 'forest'
                return f"逃跑失败！受到 {dmg} 伤害，你被击败了..."
            
            return f"逃跑失败！受到 {dmg} 伤害。HP: {player['hp']}/{player['max_hp']}"
    
    def cmd_areas(self, player):
        """查看区域"""
        text = "【可探索区域】\n"
        for area in self.game_data.get_all_areas():
            status = "✓" if player['level'] >= area['level_req'] else f"(需要Lv.{area['level_req']})"
            current = " ← 当前" if area['id'] == player['current_area'] else ""
            text += f"  {area['name']} {status}{current}\n"
        text += "\n使用 /goto <区域名> 前往"
        return text
    
    def cmd_goto(self, player, area_name):
        """前往区域"""
        if player['name'] in self.battles:
            return "战斗中无法移动！"
        
        for area in self.game_data.get_all_areas():
            if area['name'] == area_name or area['id'] == area_name:
                if player['level'] < area['level_req']:
                    return f"等级不足！需要 Lv.{area['level_req']}"
                player['current_area'] = area['id']
                return f"你来到了 {area['name']}。"
        
        return "找不到该区域。使用 /areas 查看所有区域。"
    
    def cmd_use(self, player, item_name):
        """使用道具"""
        if not item_name:
            return "请指定道具名。用法: /use <道具名>"
        
        if item_name not in player['inventory']:
            return f"背包中没有 {item_name}"
        
        if '药水' in item_name or '生命' in item_name:
            player['inventory'].remove(item_name)
            heal = 50
            player['hp'] = min(player['max_hp'], player['hp'] + heal)
            return f"使用了 {item_name}，恢复 {heal} HP。当前HP: {player['hp']}/{player['max_hp']}"
        
        return f"{item_name} 无法使用。"
    
    def cmd_heal(self, player):
        """休息回血"""
        if player['name'] in self.battles:
            return "战斗中无法休息！"
        
        cost = 10
        if player['gold'] < cost:
            return f"金币不足！需要 {cost} 金币"
        
        player['gold'] -= cost
        player['hp'] = player['max_hp']
        return f"你休息了一会，HP完全恢复！花费 {cost} 金币。"
    
    def check_level_up(self, player):
        """检查升级"""
        result = ""
        while player['exp'] >= player['exp_to_next']:
            player['exp'] -= player['exp_to_next']
            player['level'] += 1
            player['exp_to_next'] = int(player['exp_to_next'] * 1.5)
            
            player['max_hp'] += 20
            player['hp'] = player['max_hp']
            player['attack'] += 3
            player['defense'] += 2
            
            result += f"\n🎊 升级了！当前 Lv.{player['level']}\n"
            result += f"HP+20 攻击+3 防御+2\n"
        
        return result
