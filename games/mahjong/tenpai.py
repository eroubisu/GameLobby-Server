"""
麻将游戏 - 听牌分析模块
"""


class TenpaiMixin:
    """听牌分析相关方法的Mixin类"""
    
    def get_tenpai_tiles(self, position):
        """获取玩家的听牌列表
        
        Args:
            position: 玩家位置
            
        Returns:
            list: 听的牌列表，空列表表示未听牌
        """
        hand = self.hands[position]
        if len(hand) % 3 != 1:  # 手牌数量不对
            return []
        
        # 尝试每张牌，看能否胡牌
        all_tiles = [
            '一万', '二万', '三万', '四万', '五万', '六万', '七万', '八万', '九万',
            '一条', '二条', '三条', '四条', '五条', '六条', '七条', '八条', '九条',
            '一筒', '二筒', '三筒', '四筒', '五筒', '六筒', '七筒', '八筒', '九筒',
            '东', '南', '西', '北', '中', '发', '白'
        ]
        
        waiting_tiles = []
        for tile in all_tiles:
            if self.can_win(hand, tile):
                waiting_tiles.append(tile)
        
        return waiting_tiles
    
    def is_tenpai(self, position):
        """检查玩家是否听牌
        
        Args:
            position: 玩家位置
            
        Returns:
            bool: 是否听牌
        """
        return len(self.get_tenpai_tiles(position)) > 0
    
    def _check_yaku_for_waiting(self, position, hand, win_tile, is_tsumo=False):
        """检查和某张牌时是否有役
        
        Args:
            position: 玩家位置
            hand: 手牌（不含win_tile）
            win_tile: 和的牌
            is_tsumo: 是否自摸
            
        Returns:
            list: 役列表，如果无役则返回空列表
        """
        from .game_data import normalize_tile
        from .yaku import analyze_hand
        
        # 构建完整手牌
        full_hand = hand + [win_tile]
        
        # 获取风
        winds = ['东', '南', '西', '北']
        player_wind = winds[(position - self.dealer) % 4]
        
        # 分析役
        yaku_result = analyze_hand(
            hand_tiles=full_hand,
            melds=self.melds[position],
            win_tile=win_tile,
            is_tsumo=is_tsumo,
            is_riichi=self.riichi[position],
            is_ippatsu=False,  # 简化判断
            is_rinshan=False,
            is_chankan=False,
            is_haitei=False,
            is_houtei=False,
            is_tenhou=False,
            is_chihou=False,
            is_double_riichi=self.double_riichi[position],
            player_wind=player_wind,
            round_wind=self.round_wind,
            dora_count=0,  # 不计宝牌
            ura_dora_count=0,
            red_dora_count=0
        )
        
        return yaku_result.yakus if yaku_result else []
    
    def get_tenpai_analysis(self, position):
        """获取听牌分析（当前听牌 + 打出某牌后的听牌 + 剩余张数）
        
        Args:
            position: 玩家位置
            
        Returns:
            dict: {
                'is_tenpai': bool,  # 当前是否听牌
                'waiting': list,    # 当前听的牌列表 [(牌名, 剩余张数), ...]
                'waiting_count': int,  # 总听牌张数
                'discard_to_tenpai': dict  # {打出的牌: [(听的牌, 剩余张数), ...]}
            }
        """
        hand = self.hands[position]
        result = {
            'is_tenpai': False,
            'waiting': [],
            'waiting_count': 0,
            'has_yaku': False,  # 是否有役
            'yaku_info': {},    # 各听牌的役信息 {牌: [(役名, 番数), ...]}
            'discard_to_tenpai': {}
        }
        
        # 如果手牌是 3n+1 张（13张），检查当前是否听牌
        if len(hand) % 3 == 1:
            waiting_tiles = self.get_tenpai_tiles(position)
            result['waiting'] = [(t, self._count_remaining(t, position)) for t in waiting_tiles]
            result['waiting_count'] = sum(count for _, count in result['waiting'])
            result['is_tenpai'] = len(result['waiting']) > 0
            
            # 检查每个听牌是否有役
            for tile in waiting_tiles:
                yakus = self._check_yaku_for_waiting(position, hand, tile, is_tsumo=False)
                if yakus:
                    result['has_yaku'] = True
                    result['yaku_info'][tile] = [(y[0], y[1]) for y in yakus]
            
            return result
        
        # 如果手牌是 3n+2 张（14张），检查打出哪张牌后能听牌
        if len(hand) % 3 == 2:
            all_tiles = [
                '一万', '二万', '三万', '四万', '五万', '六万', '七万', '八万', '九万',
                '一条', '二条', '三条', '四条', '五条', '六条', '七条', '八条', '九条',
                '一筒', '二筒', '三筒', '四筒', '五筒', '六筒', '七筒', '八筒', '九筒',
                '东', '南', '西', '北', '中', '发', '白'
            ]
            
            from .game_data import normalize_tile
            checked_tiles = set()
            for tile in hand:
                norm_tile = normalize_tile(tile)
                if norm_tile in checked_tiles:
                    continue
                checked_tiles.add(norm_tile)
                
                # 模拟打出这张牌
                temp_hand = hand[:]
                temp_hand.remove(tile)
                
                # 检查打出后能听什么牌
                waiting = []
                tile_has_yaku = False
                for check_tile in all_tiles:
                    if self._can_win_with_hand(temp_hand, check_tile):
                        remaining = self._count_remaining(check_tile, position, exclude_tile=tile)
                        # 检查这个听牌是否有役
                        yakus = self._check_yaku_for_waiting(position, temp_hand, check_tile, is_tsumo=False)
                        has_yaku = len(yakus) > 0
                        if has_yaku:
                            tile_has_yaku = True
                        waiting.append((check_tile, remaining, has_yaku))
                
                if waiting:
                    result['discard_to_tenpai'][tile] = waiting
                    # 如果这张牌打出后任意听牌有役，标记
                    if tile_has_yaku:
                        if 'discard_has_yaku' not in result:
                            result['discard_has_yaku'] = {}
                        result['discard_has_yaku'][tile] = True
        
        return result
    
    def _count_remaining(self, tile, position, exclude_tile=None):
        """计算某张牌在场上还剩多少张
        
        Args:
            tile: 要查询的牌
            position: 当前玩家位置
            exclude_tile: 模拟打出的牌（计算时要考虑）
        
        Returns:
            int: 剩余张数
        """
        from .game_data import normalize_tile
        norm_tile = normalize_tile(tile)
        
        # 每张牌总共4张
        total = 4
        used = 0
        
        # 统计自己手牌中的
        for t in self.hands[position]:
            if normalize_tile(t) == norm_tile:
                used += 1
        
        # 如果有模拟打出的牌，且打出的是同一种牌，要减去
        if exclude_tile and normalize_tile(exclude_tile) == norm_tile:
            used -= 1  # 打出后手里少一张
        
        # 统计所有弃牌堆中的
        for i in range(4):
            for t in self.discards[i]:
                if normalize_tile(t) == norm_tile:
                    used += 1
        
        # 统计副露中的
        for i in range(4):
            for meld in self.melds[i]:
                for t in meld.get('tiles', []):
                    if normalize_tile(t) == norm_tile:
                        used += 1
        
        return max(0, total - used)
    
    def _can_win_with_hand(self, hand, tile):
        """检查给定手牌加上一张牌是否能胡牌（不修改原手牌）"""
        temp_hand = hand + [tile]
        return self._check_win_pattern(temp_hand)
    
    def can_win(self, hand, new_tile):
        """检查是否可以胡牌
        
        Args:
            hand: 当前手牌列表
            new_tile: 新加入的牌（摸到或别人打出的）
            
        Returns:
            bool: 是否可以胡牌
        """
        # 将手牌和新牌组合
        tiles = hand.copy()
        tiles.append(new_tile)
        
        # 胡牌需要 3N+2 的结构（N个面子 + 1个雀头）
        # 考虑副露的情况，手牌可能是 3N+2 - 3*已副露数
        return self._check_win_pattern(tiles)
    
    def _check_win_pattern(self, tiles):
        """检查牌型是否能胡
        
        需要满足以下其中一种：
        1. 标准形：1个雀头 + N个面子（顺子或刻子）
        2. 七对子：7个不同的对子（14张牌）
        3. 国士无双：13种幺九牌各1张 + 任意1张幺九牌（14张牌）
        """
        if len(tiles) < 2:
            return False
        
        # 标准化牌名（赤牌转普通牌）
        from .game_data import normalize_tile, YAOJIU
        normalized_tiles = [normalize_tile(t) for t in tiles]
        
        # 统计每张牌的数量
        tile_count = {}
        for tile in normalized_tiles:
            tile_count[tile] = tile_count.get(tile, 0) + 1
        
        # 检查七对子（14张牌，7种牌各2张）
        if len(tiles) == 14:
            if len(tile_count) == 7 and all(c == 2 for c in tile_count.values()):
                return True
        
        # 检查国士无双（14张牌，13种幺九牌各1张 + 任意1张幺九牌）
        if len(tiles) == 14:
            yaojiu_set = set(YAOJIU)
            # 检查是否只有幺九牌
            all_yaojiu = all(t in yaojiu_set for t in normalized_tiles)
            # 检查是否包含所有13种幺九牌
            has_all_yaojiu = yaojiu_set.issubset(set(normalized_tiles))
            if all_yaojiu and has_all_yaojiu:
                return True
        
        # 尝试每种牌作为雀头（标准形）
        for pair_tile in tile_count:
            if tile_count[pair_tile] >= 2:
                # 移除雀头后检查剩余牌能否组成面子
                remaining = tile_count.copy()
                remaining[pair_tile] -= 2
                if remaining[pair_tile] == 0:
                    del remaining[pair_tile]
                if self._check_melds_pattern(remaining):
                    return True
        return False
    
    def _check_melds_pattern(self, tile_count):
        """检查是否能全部组成面子（顺子或刻子）"""
        if not tile_count:
            return True
        
        # 获取第一张牌
        first_tile = min(tile_count.keys(), key=self._tile_sort_key)
        count = tile_count[first_tile]
        
        # 尝试组成刻子
        if count >= 3:
            remaining = tile_count.copy()
            remaining[first_tile] -= 3
            if remaining[first_tile] == 0:
                del remaining[first_tile]
            if self._check_melds_pattern(remaining):
                return True
        
        # 尝试组成顺子（只有数牌可以）
        next_tiles = self._get_sequence_tiles(first_tile)
        if next_tiles:
            t1, t2 = next_tiles
            if t1 in tile_count and tile_count[t1] >= 1 and t2 in tile_count and tile_count[t2] >= 1:
                remaining = tile_count.copy()
                remaining[first_tile] -= 1
                remaining[t1] -= 1
                remaining[t2] -= 1
                if remaining[first_tile] == 0:
                    del remaining[first_tile]
                if remaining[t1] == 0:
                    del remaining[t1]
                if remaining[t2] == 0:
                    del remaining[t2]
                if self._check_melds_pattern(remaining):
                    return True
        
        return False
    
    def _get_sequence_tiles(self, tile):
        """获取顺子的下两张牌，如果不是数牌返回None"""
        from .game_data import get_tile_suit, get_tile_number, get_tile_by_suit_number
        
        suit = get_tile_suit(tile)
        num = get_tile_number(tile)
        
        if suit == 'zi' or num is None or num > 7:
            return None
        
        t1 = get_tile_by_suit_number(suit, num + 1)
        t2 = get_tile_by_suit_number(suit, num + 2)
        if t1 and t2:
            return (t1, t2)
        return None
    
    def check_yakuman_certain(self, position):
        """检查玩家是否处于役满确定状态
        
        役满确定：听牌状态下，所有待牌和出去都是役满
        
        Args:
            position: 玩家位置
            
        Returns:
            bool: 是否役满确定
        """
        from .yaku import analyze_hand
        
        hand = self.hands[position]
        if len(hand) % 3 != 1:  # 不是听牌状态
            return False
        
        waiting_tiles = self.get_tenpai_tiles(position)
        if not waiting_tiles:
            return False
        
        # 获取风
        winds = ['东', '南', '西', '北']
        player_wind = winds[(position - self.dealer) % 4]
        
        # 检查每个待牌是否都是役满
        for tile in waiting_tiles:
            full_hand = hand + [tile]
            
            # 检查自摸和荣和两种情况
            for is_tsumo in [True, False]:
                yaku_result = analyze_hand(
                    hand_tiles=full_hand,
                    melds=self.melds[position],
                    win_tile=tile,
                    is_tsumo=is_tsumo,
                    is_riichi=self.riichi[position],
                    is_ippatsu=False,
                    is_rinshan=False,
                    is_chankan=False,
                    is_haitei=False,
                    is_houtei=False,
                    is_tenhou=False,
                    is_chihou=False,
                    is_double_riichi=self.double_riichi[position],
                    player_wind=player_wind,
                    round_wind=self.round_wind,
                    dora_count=0,
                    ura_dora_count=0,
                    red_dora_count=0
                )
                
                if not yaku_result or not yaku_result.yakus:
                    return False
                
                # 检查是否有役满
                has_yakuman = any(y[2] for y in yaku_result.yakus)  # y[2] 是 is_yakuman
                if not has_yakuman:
                    return False
        
        return True
