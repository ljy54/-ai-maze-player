from typing import List, Tuple, Optional, Dict


class BossSimulator:
    """Boss战斗模拟器：逐个遭遇Boss + BFS/DFS 规划技能 + 复活重打机制

    核心算法借鉴 puzzle-project 的 BFS 状态空间搜索：
    - BFS + 状态去重（按 boss_idx, current_hp, cooldowns 去重保留最优）
    - 大伤害优先技能排序
    """

    # 超过此回合数，DFS 改用 BFS/贪心代替（防止指数爆炸）
    MAX_DFS_ROUNDS = 14
    MAX_DFS_NODES = 200_000        # DFS 节点上限
    MAX_DFS_NODES_GLOBAL = 800_000 # 全局穷举搜索节点上限
    MAX_DFS_ROUNDS_GLOBAL = 20     # 全局穷举搜索DFS回合上限
    BFS_MAX_STATES = 80_000        # BFS 每轮状态数上限（防内存爆炸）

    def __init__(self, boss_hps: List[int], skills: List[Tuple[int, int]], max_rounds: int):
        self.boss_hps = boss_hps                          # 所有Boss完整血量（仅用于初始化）
        self.n_bosses = len(boss_hps)
        self.skills = skills                               # [(damage, cooldown), ...]
        self.n_skills = len(skills)
        self.max_rounds = max_rounds                       # 每次尝试的回合上限

        # 技能优先级（小伤害优先）：节省大技能给后面的Boss
        self._skill_order = sorted(range(self.n_skills),
                                   key=lambda i: (self.skills[i][0], self.skills[i][1]))
        # 技能优先级（大伤害优先）：用于 BFS 全局搜索
        self._skill_order_large = sorted(range(self.n_skills),
                                         key=lambda i: (-self.skills[i][0], -self.skills[i][1]))

        # 追踪 DFS 过程中的最佳部分进度
        self._best_partial_bosses = -1
        self._best_partial_damage = -1
        self._best_partial_seq: List[Tuple[int, int, int]] = []

        # DFS 节点计数器（防超时）
        self._dfs_nodes = 0
        self._max_dfs_nodes = self.MAX_DFS_NODES  # 可动态调整

    # ============================================================
    #  原始 solve（单次尝试，保留兼容任务二）
    # ============================================================

    def solve(self) -> Tuple[bool, int, List[Tuple[int, int, int]]]:
        """搜索最小击败回合数（全知全能，一次性打完）。保留兼容任务二。"""
        initial_cooldowns = tuple([0] * self.n_skills)
        initial_hps = tuple(self.boss_hps)

        # 优先用 BFS（保证最优解）
        can_beat, rounds_used, seq, _ = self._bfs_beat(
            list(self.boss_hps), self.n_bosses, self.max_rounds, initial_cooldowns
        )
        if can_beat:
            return True, rounds_used, seq

        # BFS 失败 → 尝试更大回合数
        for limit in range(self.max_rounds + 1, self.max_rounds * 2):
            can_beat, rounds_used, seq, _ = self._bfs_beat(
                list(self.boss_hps), self.n_bosses, limit, initial_cooldowns
            )
            if can_beat:
                return False, rounds_used, seq

        # 兜底：DFS
        for limit in range(1, self.max_rounds + 1):
            self._dfs_nodes = 0
            self._max_dfs_nodes = self.MAX_DFS_NODES
            result, seq = self._dfs(0, 0, initial_hps, initial_cooldowns, limit, [],
                                    self.n_bosses)
            if result:
                return True, limit, seq

        return False, self._greedy_rounds(initial_hps), []

    # ============================================================
    #  BFS 状态空间搜索
    # ============================================================

    def _bfs_beat(self, hps: List[int], revealed_count: int,
                  round_limit: int,
                  start_cooldowns: Tuple[int, ...] = None,
                  skill_order: List[int] = None,
                  max_states: int = None
                  ) -> Tuple[bool, int, List[Tuple[int, int, int]], int]:
        """
        BFS 状态空间搜索：逐轮扩展，状态去重，保证最优（最短序列）。

        相比 DFS 的优势：
        1. 状态去重：相同 (boss_idx, hp, cooldowns) 只保留最优候选
        2. BFS 天然保证找到最短序列

        返回: (成功, 使用回合数, 序列, 实际击败到的Boss索引+1)
        """
        if max_states is None:
            max_states = self.BFS_MAX_STATES

        order = skill_order if skill_order is not None else self._skill_order_large
        initial_cds = (tuple(start_cooldowns) if start_cooldowns is not None
                       else tuple([0] * self.n_skills))

        # 跳到第一个存活的Boss
        start_boss = 0
        while start_boss < revealed_count and start_boss < self.n_bosses:
            if hps[start_boss] <= 0:
                start_boss += 1
            else:
                break
        start_hp = hps[start_boss] if start_boss < self.n_bosses else 0

        # 状态键: (boss_idx, current_hp, cooldowns_tuple)
        # 值: (sequence, damage_sum)
        def make_key(boss: int, hp: int, cd: Tuple[int, ...]) -> tuple:
            return (boss, hp, cd)

        current: Dict[tuple, Tuple[List[Tuple[int, int, int]], int]] = {}
        current[make_key(start_boss, start_hp, initial_cds)] = ([], 0)

        for round_num in range(round_limit):
            next_states: Dict[tuple, Tuple[List[Tuple[int, int, int]], int]] = {}
            best_final_seq = None  # 本轮找到的最优完整解

            for (boss_idx, hp, cd), (seq, dmg_sum) in current.items():
                # 跳过已死Boss（防御性处理）
                while boss_idx < revealed_count and hp <= 0:
                    boss_idx += 1
                    hp = hps[boss_idx] if boss_idx < revealed_count else 0

                if boss_idx >= revealed_count:
                    # 已击败所有已知Boss → 候选解
                    if best_final_seq is None or len(seq) < len(best_final_seq):
                        best_final_seq = seq
                    continue

                # 收集可用技能
                any_skill_available = False
                for si in order:
                    if cd[si] > 0:
                        continue
                    any_skill_available = True

                    dmg = self.skills[si][0]
                    skill_cd = self.skills[si][1]

                    # 冷却减1
                    new_cd = list(cd)
                    for j in range(self.n_skills):
                        if new_cd[j] > 0:
                            new_cd[j] -= 1
                    new_cd[si] = skill_cd

                    # 伤害只打在目标Boss上（无溢出）
                    new_hp = hp - dmg
                    new_boss = boss_idx
                    if new_hp <= 0:
                        # 当前Boss死亡 → 切换到下一个存活的Boss
                        new_boss = boss_idx + 1
                        while new_boss < revealed_count and new_boss < self.n_bosses:
                            if hps[new_boss] <= 0:
                                new_boss += 1
                            else:
                                break
                        new_hp = hps[new_boss] if new_boss < revealed_count else 0

                    new_seq = seq + [(round_num, si, boss_idx)]
                    new_dmg_sum = dmg_sum + dmg

                    vk = make_key(new_boss, new_hp, tuple(new_cd))
                    old = next_states.get(vk)
                    # 保留更优的候选：伤害更大，或同伤害序列更短
                    if old is None:
                        next_states[vk] = (new_seq, new_dmg_sum)
                    elif (new_dmg_sum > old[1] or
                          (new_dmg_sum == old[1] and len(new_seq) < len(old[0]))):
                        next_states[vk] = (new_seq, new_dmg_sum)

                # 全部冷却中 → 等待冷却（不消耗技能，只减少冷却）
                if not any_skill_available and any(c > 0 for c in cd):
                    new_cd = tuple(max(0, c - 1) for c in cd)
                    new_hp_wait = hp
                    new_boss_wait = boss_idx
                    # 如果当前Boss已死，跳到下一个
                    if new_hp_wait <= 0:
                        while new_boss_wait < revealed_count and new_boss_wait < self.n_bosses:
                            if hps[new_boss_wait] <= 0:
                                new_boss_wait += 1
                            else:
                                break
                        new_hp_wait = hps[new_boss_wait] if new_boss_wait < revealed_count else 0
                    vk = make_key(new_boss_wait, new_hp_wait, new_cd)
                    if vk not in next_states:
                        next_states[vk] = (seq, dmg_sum)

                # 防止状态爆炸
                if len(next_states) > max_states:
                    break

            # BFS 找到的第一个解就是最短序列
            # 先检查当前轮已有的终结状态
            if best_final_seq is None:
                for (boss_idx, hp, cd), (seq, dmg_sum) in next_states.items():
                    if boss_idx >= revealed_count:
                        best_final_seq = seq
                        break

            if best_final_seq is not None:
                # 计算实际击败的Boss数
                temp_hps = list(hps)
                for _, si, bi in best_final_seq:
                    dmg = self.skills[si][0]
                    if bi < len(temp_hps):
                        temp_hps[bi] -= dmg
                        if temp_hps[bi] <= 0:
                            temp_hps[bi] = 0
                killed = 0
                for i in range(len(temp_hps)):
                    if temp_hps[i] <= 0:
                        killed = i + 1
                    else:
                        break
                new_revealed = max(revealed_count, killed)
                return True, round_num + 1, best_final_seq, new_revealed

            # 状态数超限 → 截断保留最优的
            if len(next_states) > max_states:
                # 按击败Boss数降序、伤害降序排序，保留前 max_states
                sorted_states = sorted(
                    next_states.items(),
                    key=lambda item: (
                        -item[0][0],  # boss_idx 大优先
                        -(hps[item[0][0]] - item[0][1]) if item[0][0] < len(hps) else 999,  # 伤害大优先
                    )
                )
                next_states = dict(sorted_states[:max_states])

            current = next_states
            if not current:
                break

        return False, round_limit, [], revealed_count

    # ============================================================
    #  全局穷举搜索（已知全部Boss时使用）
    # ============================================================

    def _global_exhaustive_search(self, hps: List[int],
                                   round_limit: int,
                                   start_cooldowns: Tuple[int, ...] = None
                                   ) -> Tuple[bool, int, List[Tuple[int, int, int]]]:
        """
        已知全部Boss血量时的穷举搜索：尝试多种策略确保找到解。

        策略优先级：
        1. BFS 大伤害优先 + 高状态上限
        2. BFS 小伤害优先 + 高状态上限
        3. 束搜索 大伤害优先 × 多束宽
        4. 束搜索 小伤害优先 × 多束宽
        5. DFS 全回合 + 高节点上限
        """
        n_bosses = self.n_bosses
        initial_cds = (tuple(start_cooldowns) if start_cooldowns is not None
                       else tuple([0] * self.n_skills))

        # 策略1: BFS 大伤害优先（状态效率高）
        can_beat, r_used, seq, _ = self._bfs_beat(
            hps, n_bosses, round_limit, initial_cds,
            skill_order=self._skill_order_large,
            max_states=self.BFS_MAX_STATES * 2
        )
        if can_beat:
            return True, r_used, seq

        # 策略2: BFS 小伤害优先（节省大技能给后面Boss）
        can_beat, r_used, seq, _ = self._bfs_beat(
            hps, n_bosses, round_limit, initial_cds,
            skill_order=self._skill_order,
            max_states=self.BFS_MAX_STATES * 2
        )
        if can_beat:
            return True, r_used, seq

        # 策略3: 束搜索 × 多配置
        for bw in [200, 500, 1000]:
            for order in [self._skill_order_large, self._skill_order]:
                greedy_seq = self._greedy_sequence(
                    hps, n_bosses, round_limit, initial_cds,
                    beam_width=bw, skill_order=order
                )
                if greedy_seq:
                    temp_hps = list(hps)
                    for _, si, bi in greedy_seq:
                        dmg = self.skills[si][0]
                        if bi < len(temp_hps):
                            temp_hps[bi] -= dmg
                            if temp_hps[bi] <= 0:
                                temp_hps[bi] = 0
                    killed = sum(1 for hp in temp_hps if hp <= 0)
                    if killed >= n_bosses:
                        return True, len(greedy_seq), greedy_seq

        # 策略4: DFS 穷举（全回合 + 高节点上限）
        self._max_dfs_nodes = self.MAX_DFS_NODES_GLOBAL
        dfs_limit = min(round_limit, self.MAX_DFS_ROUNDS_GLOBAL)
        initial_hps = tuple(hps)

        for limit in range(1, dfs_limit + 1):
            self._dfs_nodes = 0
            result, seq = self._dfs(0, 0, initial_hps, initial_cds,
                                    limit, [], n_bosses)
            if result:
                return True, limit, seq

        return False, 0, []

    # ============================================================
    #  带复活机制的战斗模拟
    # ============================================================

    def solve_with_revival(self, total_coins: int, coin_consumption: int
                           ) -> Tuple[bool, List[List[Tuple[int, int, int]]],
                                      int, int, int]:
        """
        复活机制（改进版）：
        阶段一：顺序遭遇Boss揭露血量，使用 BFS 尽可能击败。
                打不过也打最大伤害收集信息。
        阶段二：复活后若已知全部Boss血量，使用全局穷举搜索一次性规划。
                找不到解则尝试不同策略，不轻易放弃。

        返回:
            can_beat:       是否最终击败全部Boss
            all_sequences:  每次尝试的技能序列 [[seq1], [seq2], ...]
            revival_count:  复活次数
            total_coin_cost:复活总金币消耗
            total_rounds:   总回合数
        """
        revealed_count = 1           # 已遭遇（知道血量）的Boss数
        revival_count = 0
        total_coin_cost = 0
        all_sequences = []
        total_rounds = 0
        prev_revealed = 0            # 上一次复活时的揭露数（检测无进展）

        while True:
            # === 一次新的尝试：Boss全部回满血 ===
            current_hps = list(self.boss_hps)
            round_offset = total_rounds
            attempt_rounds_left = self.max_rounds

            # === 阶段二：复活后已知全部Boss血量 → 全局穷举搜索 ===
            if revival_count > 0 and revealed_count >= self.n_bosses:
                attempt_cooldowns = tuple([0] * self.n_skills)
                can_beat, r_used, seq = self._global_exhaustive_search(
                    current_hps, attempt_rounds_left, attempt_cooldowns
                )
                if can_beat:
                    offset_seq = [(round_offset + r, si, bi) for r, si, bi in seq]
                    all_sequences.append(offset_seq)
                    total_rounds += r_used
                    return True, all_sequences, revival_count, total_coin_cost, total_rounds
                else:
                    # 所有策略都失败 → 确定无法击败
                    return False, all_sequences, revival_count, \
                        total_coin_cost, total_rounds

            # === 阶段一：内层循环，顺序遭遇/击败Boss ===
            attempt_cooldowns = tuple([0] * self.n_skills)
            while attempt_rounds_left > 0 and revealed_count <= self.n_bosses:
                # 使用 BFS 尝试击败已知Boss（BFS保证最短序列，对后续Boss更友好）
                can_beat, r_used, seq, new_rev = self._try_beat(
                    current_hps, revealed_count,
                    attempt_rounds_left, attempt_cooldowns
                )

                if can_beat and new_rev >= revealed_count:
                    # 击败了当前已知的所有Boss
                    offset_seq = [(round_offset + r, si, bi) for r, si, bi in seq]
                    all_sequences.append(offset_seq)
                    total_rounds += r_used
                    round_offset += r_used
                    attempt_rounds_left -= r_used
                    current_hps = self._apply_damage(current_hps, seq)
                    revealed_count = max(revealed_count, new_rev)
                    attempt_cooldowns = self._end_cooldowns(seq)

                    if revealed_count >= self.n_bosses:
                        return True, all_sequences, revival_count, total_coin_cost, total_rounds

                    # 揭露下一个Boss
                    revealed_count += 1

                    # 揭露最后一个Boss后 → 先尝试用剩余回合全局规划
                    if revealed_count >= self.n_bosses:
                        if attempt_rounds_left > 0:
                            can_beat, r_used, seq = self._global_exhaustive_search(
                                current_hps, attempt_rounds_left, attempt_cooldowns
                            )
                            if can_beat:
                                offset_seq = [(round_offset + r, si, bi) for r, si, bi in seq]
                                all_sequences.append(offset_seq)
                                total_rounds += r_used
                                return True, all_sequences, revival_count, total_coin_cost, total_rounds

                        # 当前状态打不过 → 检查满血满回合能不能打过（自动复活）
                        can_beat, r_used, seq = self._global_exhaustive_search(
                            list(self.boss_hps), self.max_rounds, tuple([0] * self.n_skills)
                        )
                        if can_beat:
                            # 自动复活（允许透支：金币不够也复活，最终净收益可能为负）
                            revival_count += 1
                            total_coin_cost += coin_consumption
                            offset_seq = [(total_rounds + r, si, bi) for r, si, bi in seq]
                            all_sequences.append(offset_seq)
                            total_rounds += r_used
                            return True, all_sequences, revival_count, total_coin_cost, total_rounds
                        # 满血也打不过 → 继续循环
                else:
                    # 打不死 → 全部Boss已知时尝试全局搜索（不需要等复活）
                    if revealed_count >= self.n_bosses:
                        can_beat, r_used, seq = self._global_exhaustive_search(
                            current_hps, attempt_rounds_left, attempt_cooldowns
                        )
                        if can_beat:
                            offset_seq = [(round_offset + r, si, bi) for r, si, bi in seq]
                            all_sequences.append(offset_seq)
                            total_rounds += r_used
                            if revival_count == 0:
                                # 全局规划一次性成功，无需复活
                                return True, all_sequences, 0, 0, total_rounds
                            return True, all_sequences, revival_count, total_coin_cost, total_rounds
                        elif revival_count > 0:
                            # 已复活过还失败 → 确定无法击败
                            return False, all_sequences, revival_count, \
                                total_coin_cost, total_rounds
                        # 还没复活过 → 继续信息收集，准备复活后再试

                    # 打出最大伤害以揭露更多Boss血量（信息收集）
                    best_seq = self._find_best_partial(
                        current_hps, revealed_count,
                        attempt_rounds_left, attempt_cooldowns
                    )
                    if best_seq:
                        offset_seq = [(round_offset + r, si, bi) for r, si, bi in best_seq]
                        all_sequences.append(offset_seq)
                        total_rounds += len(best_seq)
                        max_bi = max((s[2] for s in best_seq), default=0)
                        revealed_count = max(revealed_count, max_bi + 1)
                        revealed_count = min(revealed_count, self.n_bosses)
                    break  # 本次尝试结束

            # === 复活 ===
            if revival_count > 0 and revealed_count <= prev_revealed:
                # 已复活但无进展 → 无法击败
                return False, all_sequences, revival_count, total_coin_cost, total_rounds

            prev_revealed = revealed_count
            revival_count += 1
            total_coin_cost += coin_consumption
            if total_coin_cost > total_coins:
                return False, all_sequences, revival_count - 1, \
                    total_coin_cost - coin_consumption, total_rounds

    # ============================================================
    #  束搜索（支持多策略参数）
    # ============================================================

    def _greedy_sequence(self, hps: List[int], revealed_count: int,
                          round_limit: int,
                          start_cooldowns: Tuple[int, ...] = None,
                          beam_width: int = 100,
                          skill_order: List[int] = None
                          ) -> List[Tuple[int, int, int]]:
        """束搜索：每步保留 beam_width 个最优候选。
        支持自定义技能排序和束宽度，用于多策略尝试。"""
        initial_hps = tuple(hps)
        initial_cds = (tuple(start_cooldowns) if start_cooldowns is not None
                       else tuple([0] * self.n_skills))
        # 跳过初始已死Boss
        start_boss = 0
        while start_boss < revealed_count and start_boss < self.n_bosses:
            if hps[start_boss] <= 0:
                start_boss += 1
            else:
                break
        beam = [(initial_hps, initial_cds, start_boss, [])]

        # 使用自定义技能排序或默认排序
        order = skill_order if skill_order is not None else self._skill_order

        for r in range(round_limit):
            next_beam = []
            for hps_t, cds_t, boss_idx, seq in beam:
                # 跳过已死Boss（不消耗回合）
                while boss_idx < revealed_count and boss_idx < self.n_bosses:
                    if hps_t[boss_idx] <= 0:
                        boss_idx += 1
                    else:
                        break

                if boss_idx >= revealed_count or boss_idx >= self.n_bosses:
                    next_beam.append((hps_t, cds_t, boss_idx, seq))
                    continue

                # 冷却减1
                new_cds_base = tuple(max(0, c - 1) for c in cds_t)

                # 收集可用技能，计算效率分
                avail = []
                for si in order:
                    if cds_t[si] == 0:
                        dmg, cd = self.skills[si]
                        need = hps_t[boss_idx]
                        overkill_penalty = max(0, dmg - need) * 0.3
                        efficiency = (dmg - overkill_penalty) / max(1, cd + 1)
                        avail.append((si, dmg, cd, efficiency))

                if not avail:
                    # 全部冷却中，跳过本回合（冷却自动减1）
                    next_beam.append((hps_t, new_cds_base, boss_idx, seq))
                    continue

                # 效率优先，同效率时按传入排序的优先级
                avail.sort(key=lambda x: (-x[3], order.index(x[0])))
                avail = avail[: min(5, len(avail))]

                for si, dmg, cd, _ in avail:
                    new_hps = list(hps_t)
                    new_hps[boss_idx] -= dmg
                    next_bi = boss_idx
                    if new_hps[boss_idx] <= 0:
                        new_hps[boss_idx] = 0
                        next_bi = boss_idx + 1

                    new_cds = list(new_cds_base)
                    new_cds[si] = cd

                    new_seq = seq + [(r, si, boss_idx)]
                    next_beam.append((tuple(new_hps), tuple(new_cds), next_bi, new_seq))

            # 排序并保留 top beam_width
            def rank(state):
                _, _, bi, _ = state
                return bi
            next_beam.sort(key=rank, reverse=True)
            beam = next_beam[:beam_width]

            if not beam:
                break

        best = beam[0]
        return best[3]  # seq

    # ============================================================
    #  _reserve_big_skills：后面还有未知Boss时，避免大招收尾
    # ============================================================

    def _reserve_big_skills(self, seq: List[Tuple[int, int, int]],
                            rounds_used: int,
                            hps: List[int], revealed_count: int,
                            round_limit: int,
                            start_cooldowns: Tuple[int, ...]
                            ) -> List[Tuple[int, int, int]]:
        """
        如果当前最优序列的最后一击用了高伤害大招，且后面还有未知Boss，
        尝试不用该大招的替代方案。若替代方案回合数相同则替换。
        """
        if not seq:
            return seq

        # 最后一击使用的技能
        last_skill = seq[-1][1]

        # 找出最大的两个技能（按伤害排序）
        top_skills = sorted(range(self.n_skills),
                            key=lambda i: -self.skills[i][0])[:2]

        # 只有当最后一击是最大技能之一时才尝试保留
        if last_skill not in top_skills:
            return seq

        # 计算替代方案：将最后一击用的大招排到最后（BFS会优先用前面的技能）
        reserved = last_skill
        alt_order = [i for i in self._skill_order_large if i != reserved] + [reserved]

        can_beat, _, alt_seq, _ = self._bfs_beat(
            hps, revealed_count, round_limit, start_cooldowns,
            skill_order=alt_order
        )

        if can_beat and len(alt_seq) <= rounds_used:
            # 同回合数或更少 → 采用保留大招的方案
            return alt_seq

        # 如果同回合数不行，也尝试用束搜索找替代
        alt_seq2 = self._greedy_sequence(
            hps, revealed_count, round_limit, start_cooldowns,
            beam_width=200, skill_order=alt_order
        )
        if alt_seq2 and len(alt_seq2) <= rounds_used:
            # 验证确实能击败
            killed = self._count_killed(hps, alt_seq2)
            if killed >= revealed_count:
                return alt_seq2

        return seq

    # ============================================================
    #  _try_beat：优先 BFS，回退 DFS/贪心
    # ============================================================

    def _try_beat(self, hps: List[int], revealed_count: int,
                  round_limit: int = None,
                  start_cooldowns: Tuple[int, ...] = None
                  ) -> Tuple[bool, int, List[Tuple[int, int, int]], int]:
        """
        尝试在 round_limit 回合内击败已揭露的Boss。
        优先使用 BFS（保证最优），回退到 DFS/贪心。
        当后面还有未知Boss时，尽量保留大招不用于最后一击。
        返回 (成功, 使用回合数, 序列, 实际击败到的Boss索引+1)
        """
        if round_limit is None:
            round_limit = self.max_rounds

        initial_cooldowns = (tuple(start_cooldowns) if start_cooldowns is not None
                             else tuple([0] * self.n_skills))

        has_unknown_bosses = revealed_count < self.n_bosses
        bfs_limit = min(round_limit, self.MAX_DFS_ROUNDS_GLOBAL)

        # 策略1: BFS 大伤害优先（状态效率高，搜索快）
        can_beat, r_used, seq, new_rev = self._bfs_beat(
            hps, revealed_count, bfs_limit, initial_cooldowns
        )
        if can_beat:
            # 后面还有未知Boss → 尝试保留大招，避免最后一击用最大技能
            if has_unknown_bosses:
                seq = self._reserve_big_skills(
                    seq, r_used, hps, revealed_count, bfs_limit, initial_cooldowns
                )
            return True, r_used, seq, new_rev

        # 策略2: BFS 小伤害优先（节省大技能给后面Boss）
        can_beat, r_used, seq, new_rev = self._bfs_beat(
            hps, revealed_count, bfs_limit, initial_cooldowns,
            skill_order=self._skill_order
        )
        if can_beat:
            if has_unknown_bosses:
                seq = self._reserve_big_skills(
                    seq, r_used, hps, revealed_count, bfs_limit, initial_cooldowns
                )
            return True, r_used, seq, new_rev

        # 策略3: DFS（小规模精确搜索）
        dfs_limit = min(round_limit, self.MAX_DFS_ROUNDS)
        initial_hps = tuple(hps)
        self._max_dfs_nodes = self.MAX_DFS_NODES
        for limit in range(1, dfs_limit + 1):
            self._dfs_nodes = 0
            result, dfs_seq = self._dfs(0, 0, initial_hps, initial_cooldowns,
                                        limit, [], revealed_count)
            if result:
                killed = self._count_killed(hps, dfs_seq)
                new_revealed = max(revealed_count, killed)
                return True, limit, dfs_seq, new_revealed

        # 策略4: 束搜索（大回合数兜底）
        for bw in [100, 200]:
            for order in [self._skill_order_large, self._skill_order]:
                greedy_seq = self._greedy_sequence(
                    hps, revealed_count, round_limit, initial_cooldowns,
                    beam_width=bw, skill_order=order
                )
                if greedy_seq:
                    killed = self._count_killed(hps, greedy_seq)
                    new_revealed = max(revealed_count, killed)
                    if killed >= revealed_count:
                        return True, len(greedy_seq), greedy_seq, new_revealed

        return False, round_limit, [], revealed_count

    def _count_killed(self, hps: List[int], seq: List[Tuple[int, int, int]]) -> int:
        """统计序列击败的Boss数"""
        temp_hps = list(hps)
        for _, si, bi in seq:
            dmg = self.skills[si][0]
            if bi < len(temp_hps):
                temp_hps[bi] -= dmg
                if temp_hps[bi] <= 0:
                    temp_hps[bi] = 0
        killed = 0
        for hp in temp_hps:
            if hp <= 0:
                killed += 1
            else:
                break
        return killed

    # ============================================================
    #  _find_best_partial：信息收集
    # ============================================================

    def _find_best_partial(self, hps: List[int], revealed_count: int,
                           round_limit: int = None,
                           start_cooldowns: Tuple[int, ...] = None
                           ) -> List[Tuple[int, int, int]]:
        """搜索 round_limit 回合内的最佳部分进度（用于信息收集阶段）。"""
        if round_limit is None:
            round_limit = self.max_rounds

        initial_cds = (tuple(start_cooldowns) if start_cooldowns is not None
                       else tuple([0] * self.n_skills))

        # 优先用 BFS 找部分进度（状态去重，覆盖面更广）
        bfs_seq = self._bfs_partial(hps, revealed_count, round_limit, initial_cds)
        if bfs_seq:
            return bfs_seq

        # 回退到束搜索
        if round_limit > self.MAX_DFS_ROUNDS:
            return self._greedy_sequence(hps, revealed_count, round_limit, initial_cds)

        # 回退到 DFS 部分搜索
        self._best_partial_bosses = -1
        self._best_partial_damage = -1
        self._best_partial_seq = []

        initial_hps = tuple(hps)
        self._dfs_nodes = 0
        self._dfs_partial(0, 0, initial_hps, initial_cds,
                          round_limit, [], initial_hps, revealed_count)

        return self._best_partial_seq

    def _bfs_partial(self, hps: List[int], revealed_count: int,
                     round_limit: int,
                     start_cooldowns: Tuple[int, ...]
                     ) -> List[Tuple[int, int, int]]:
        """BFS 搜索最佳部分进度：找到能击败最多Boss + 对下个Boss伤害最大的序列"""
        best_seq = []
        best_killed = -1
        best_dmg = -1

        def make_key(boss, hp, cd):
            return (boss, hp, cd)

        start_boss = 0
        while start_boss < revealed_count and hps[start_boss] <= 0:
            start_boss += 1
        start_hp = hps[start_boss] if start_boss < self.n_bosses else 0

        current = {make_key(start_boss, start_hp, start_cooldowns): ([], 0)}

        for _ in range(round_limit):
            next_states = {}
            for (boss_idx, hp, cd), (seq, dmg_sum) in current.items():
                # 评估当前状态
                killed = boss_idx
                dmg_to_cur = (hps[boss_idx] - hp) if boss_idx < len(hps) else 0

                if (killed > best_killed or
                    (killed == best_killed and dmg_to_cur > best_dmg)):
                    best_killed = killed
                    best_dmg = dmg_to_cur
                    best_seq = seq

                if boss_idx >= revealed_count:
                    continue

                any_avail = False
                for si in self._skill_order_large:
                    if cd[si] > 0:
                        continue
                    any_avail = True

                    dmg = self.skills[si][0]
                    skill_cd = self.skills[si][1]

                    new_cd = list(cd)
                    for j in range(self.n_skills):
                        if new_cd[j] > 0:
                            new_cd[j] -= 1
                    new_cd[si] = skill_cd

                    # 伤害只打在目标Boss上（无溢出）
                    new_hp = hp - dmg
                    new_boss = boss_idx
                    if new_hp <= 0:
                        new_boss = boss_idx + 1
                        while new_boss < revealed_count and new_boss < self.n_bosses:
                            if hps[new_boss] <= 0:
                                new_boss += 1
                            else:
                                break
                        new_hp = hps[new_boss] if new_boss < revealed_count else 0

                    new_seq = seq + [(len(seq), si, boss_idx)]
                    vk = make_key(new_boss, new_hp, tuple(new_cd))
                    if vk not in next_states:
                        next_states[vk] = (new_seq, dmg_sum + dmg)

                if not any_avail and any(c > 0 for c in cd):
                    new_cd = tuple(max(0, c - 1) for c in cd)
                    vk = make_key(boss_idx, hp, new_cd)
                    if vk not in next_states:
                        next_states[vk] = (seq, dmg_sum)

                if len(next_states) > 30000:
                    break

            current = next_states
            if not current:
                break

        return best_seq

    # ============================================================
    #  DFS 搜索（保留作为小规模精确搜索的兜底）
    # ============================================================

    def _dfs_partial(self, boss_idx: int, round_num: int,
                     hps: Tuple[int, ...], cooldowns: Tuple[int, ...],
                     limit: int, seq: List[Tuple[int, int, int]],
                     initial_hps: Tuple[int, ...], revealed_count: int):
        """DFS 变体：追踪所有状态，记录最佳部分进度"""
        max_nodes = getattr(self, '_max_dfs_nodes', self.MAX_DFS_NODES)
        self._dfs_nodes += 1
        if self._dfs_nodes > max_nodes:
            return

        while boss_idx < revealed_count and boss_idx < self.n_bosses:
            if hps[boss_idx] <= 0:
                boss_idx += 1
            else:
                break

        current_damage = (initial_hps[boss_idx] - hps[boss_idx]
                          if boss_idx < self.n_bosses else 999)

        if (boss_idx > self._best_partial_bosses or
            (boss_idx == self._best_partial_bosses and
             current_damage > self._best_partial_damage)):
            self._best_partial_bosses = boss_idx
            self._best_partial_damage = current_damage
            self._best_partial_seq = seq[:]

        if boss_idx >= revealed_count or boss_idx >= self.n_bosses:
            return

        if round_num >= limit:
            return

        for si in range(self.n_skills):
            if cooldowns[si] > 0:
                continue

            dmg = self.skills[si][0]
            cd = self.skills[si][1]

            new_hps = list(hps)
            new_hps[boss_idx] -= dmg

            next_boss_idx = boss_idx
            if new_hps[boss_idx] <= 0:
                next_boss_idx = boss_idx + 1
                new_hps[boss_idx] = 0

            new_cooldowns = list(cooldowns)
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            new_cooldowns[si] = cd

            self._dfs_partial(
                next_boss_idx, round_num + 1,
                tuple(new_hps), tuple(new_cooldowns), limit,
                seq + [(round_num, si, boss_idx)], initial_hps, revealed_count
            )

        if any(cd > 0 for cd in cooldowns):
            new_cooldowns = list(cooldowns)
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            self._dfs_partial(
                boss_idx, round_num + 1,
                hps, tuple(new_cooldowns), limit,
                seq, initial_hps, revealed_count
            )

    def _end_cooldowns(self, seq: List[Tuple[int, int, int]]
                        ) -> Tuple[int, ...]:
        """计算序列执行结束时的技能冷却状态。"""
        cds = [0] * self.n_skills
        if not seq:
            return tuple(cds)
        max_round = max(r for r, _, _ in seq)
        for r in range(max_round + 1):
            cds = [max(0, c - 1) for c in cds]
            for rr, si, _ in seq:
                if rr == r:
                    cds[si] = self.skills[si][1]
                    break
        return tuple(cds)

    def _apply_damage(self, hps: List[int], seq: List[Tuple[int, int, int]]
                       ) -> List[int]:
        """根据技能序列模拟伤害，返回剩余的 Boss 血量"""
        remaining = list(hps)
        for _, skill_idx, boss_idx in seq:
            if boss_idx < len(remaining):
                dmg = self.skills[skill_idx][0]
                remaining[boss_idx] -= dmg
                if remaining[boss_idx] <= 0:
                    remaining[boss_idx] = 0
        return remaining

    # ============================================================
    #  DFS（找出能在 limit 回合内击败所有 revealed 范围内 Boss 的序列）
    # ============================================================

    def _dfs(self, boss_idx: int, round_num: int, hps: Tuple[int, ...],
             cooldowns: Tuple[int, ...], limit: int,
             seq: List[Tuple[int, int, int]], revealed_count: int
             ) -> Tuple[bool, List[Tuple[int, int, int]]]:
        """深度优先搜索 + 剪枝（保留作为兜底）。"""
        max_nodes = getattr(self, '_max_dfs_nodes', self.MAX_DFS_NODES)
        self._dfs_nodes += 1
        if self._dfs_nodes > max_nodes:
            return False, []

        while boss_idx < revealed_count and boss_idx < self.n_bosses:
            if hps[boss_idx] <= 0:
                boss_idx += 1
            else:
                break

        if boss_idx >= revealed_count or boss_idx >= self.n_bosses:
            return True, seq[:]

        if round_num >= limit:
            return False, []

        remaining_rounds = limit - round_num

        if not self._can_kill_remaining(boss_idx, hps, remaining_rounds, revealed_count):
            return False, []

        for si in range(self.n_skills):
            if cooldowns[si] > 0:
                continue

            dmg = self.skills[si][0]
            cd = self.skills[si][1]

            new_hps = list(hps)
            new_hps[boss_idx] -= dmg

            next_boss_idx = boss_idx
            if new_hps[boss_idx] <= 0:
                next_boss_idx = boss_idx + 1
                new_hps[boss_idx] = 0

            new_cooldowns = list(cooldowns)
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            new_cooldowns[si] = cd

            new_seq = seq + [(round_num, si, boss_idx)]

            result, final_seq = self._dfs(
                next_boss_idx, round_num + 1,
                tuple(new_hps), tuple(new_cooldowns), limit, new_seq,
                revealed_count
            )
            if result:
                return True, final_seq

        if any(cd > 0 for cd in cooldowns):
            new_cooldowns = list(cooldowns)
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            result, final_seq = self._dfs(
                boss_idx, round_num + 1,
                hps, tuple(new_cooldowns), limit, seq,
                revealed_count
            )
            if result:
                return True, final_seq

        return False, []

    def _can_kill_remaining(self, boss_idx: int, hps: Tuple[int, ...],
                            remaining: int, revealed_count: int) -> bool:
        """剪枝：乐观估算剩余回合的最大伤害。"""
        total_hp = 0
        stop_at = min(revealed_count, self.n_bosses)
        for i in range(boss_idx, stop_at):
            total_hp += max(0, hps[i])

        if total_hp <= 0:
            return True

        max_possible = 0
        for dmg, cd in self.skills:
            casts = (remaining + cd) // (cd + 1)
            max_possible += dmg * casts

        return max_possible >= total_hp

    def _greedy_rounds(self, hps: Tuple[int, ...]) -> int:
        """贪心估算（兜底）"""
        total_hp = sum(hps)
        avg_dmg = sum(d for d, _ in self.skills) / max(1, self.n_skills)
        avg_cd = sum(c for _, c in self.skills) / max(1, self.n_skills)
        dmg_per_round = avg_dmg / (avg_cd + 1)
        return int(total_hp / dmg_per_round) + 1 if dmg_per_round > 0 else 999
