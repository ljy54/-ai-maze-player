from typing import List, Tuple, Optional
from functools import lru_cache


class BossSimulator:
    """Boss战斗模拟器：状态搜索计算最小击败回合数及技能释放序列"""

    def __init__(self, boss_hps: List[int], skills: List[Tuple[int, int]], max_rounds: int):
        self.boss_hps = boss_hps
        self.n_bosses = len(boss_hps)
        self.skills = skills  # [(damage, cooldown), ...]
        self.n_skills = len(skills)
        self.max_rounds = max_rounds
        self.best_sequence: List[Tuple[int, int, int]] = []  # (round, skill_idx, boss_idx)

    def solve(self) -> Tuple[bool, int, List[Tuple[int, int, int]]]:
        """
        搜索最小击败回合数。
        返回 (是否能在maxRounds内击败, 需要回合数, 技能释放序列)
        """
        self.best_sequence = []
        self._best_time = self.max_rounds + 1

        initial_cooldowns = tuple([0] * self.n_skills)
        initial_hps = tuple(self.boss_hps)

        # 迭代加深：尝试逐步放宽回合限制
        for limit in range(1, self.max_rounds + 1):
            result, seq = self._dfs(0, 0, initial_hps, initial_cooldowns, limit, [])
            if result:
                self.best_sequence = seq
                return True, limit, seq

        # 如果maxRounds内无法击败，计算最小需要回合数
        min_needed = self.max_rounds + 1
        for limit in range(self.max_rounds + 1, self.max_rounds * 2):
            result, seq = self._dfs(0, 0, initial_hps, initial_cooldowns, limit, [])
            if result:
                return False, limit, seq

        # 给出一个尽可能好的序列（贪心兜底）
        return False, self._greedy_rounds(initial_hps, initial_cooldowns), []

    def _dfs(self, boss_idx: int, round_num: int, hps: Tuple[int, ...],
             cooldowns: Tuple[int, ...], limit: int, seq: List[Tuple[int, int, int]]
             ) -> Tuple[bool, List[Tuple[int, int, int]]]:
        """深度优先搜索 + 剪枝"""
        # 所有Boss已击败
        if boss_idx >= self.n_bosses:
            return True, seq[:]

        # 超过限制
        if round_num >= limit:
            return False, []

        remaining_rounds = limit - round_num

        # 剪枝1：理论最大DPS不足以击败剩余Boss
        if not self._can_kill_remaining(boss_idx, hps, remaining_rounds):
            return False, []

        # 枚举所有可用技能
        for si in range(self.n_skills):
            if cooldowns[si] > 0:
                continue

            dmg = self.skills[si][0]
            cd = self.skills[si][1]

            # 使用技能攻击当前Boss
            new_hps = list(hps)
            new_hps[boss_idx] -= dmg

            next_boss_idx = boss_idx
            if new_hps[boss_idx] <= 0:
                next_boss_idx = boss_idx + 1
                new_hps[boss_idx] = 0  # 清零

            # 更新冷却
            new_cooldowns = list(cooldowns)
            # 所有冷却减1（至少为0）
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            # 当前技能重新进入冷却
            new_cooldowns[si] = cd

            new_seq = seq + [(round_num, si, boss_idx)]

            result, final_seq = self._dfs(
                next_boss_idx, round_num + 1,
                tuple(new_hps), tuple(new_cooldowns), limit, new_seq
            )
            if result:
                return True, final_seq

        # 也可以选择跳过回合（所有技能都在冷却时或等待更好时机）
        if any(cd > 0 for cd in cooldowns):
            new_cooldowns = list(cooldowns)
            for i in range(self.n_skills):
                if new_cooldowns[i] > 0:
                    new_cooldowns[i] -= 1
            result, final_seq = self._dfs(
                boss_idx, round_num + 1,
                hps, tuple(new_cooldowns), limit, seq
            )
            if result:
                return True, final_seq

        return False, []

    def _can_kill_remaining(self, boss_idx: int, hps: Tuple[int, ...], remaining: int) -> bool:
        """剪枝：检查剩余回合能否输出足够伤害"""
        total_hp = 0
        for i in range(boss_idx, self.n_bosses):
            total_hp += max(0, hps[i])

        # 每回合能造成的最大伤害
        max_dmg_per_round = max(dmg for dmg, _ in self.skills) if self.skills else 0
        # 排除冷却影响：最优情况
        max_possible = 0
        temp_cds = [0] * self.n_skills
        for r in range(remaining):
            best_dmg = 0
            for si in range(self.n_skills):
                if temp_cds[si] == 0:
                    if self.skills[si][0] > best_dmg:
                        best_dmg = self.skills[si][0]
            max_possible += best_dmg
            for si in range(self.n_skills):
                if temp_cds[si] > 0:
                    temp_cds[si] -= 1
            # 用最佳技能
            for si in range(self.n_skills):
                if temp_cds[si] == 0 and self.skills[si][0] == best_dmg:
                    temp_cds[si] = self.skills[si][1]
                    break

        return max_possible >= total_hp

    def _greedy_rounds(self, hps: Tuple[int, ...], cooldowns: Tuple[int, ...]) -> int:
        """贪心估算（兜底）"""
        total_hp = sum(hps)
        avg_dmg = sum(d for d, _ in self.skills) / max(1, self.n_skills)
        avg_cd = sum(c for _, c in self.skills) / max(1, self.n_skills)
        rounds_per_skill = (avg_cd + 1)
        dmg_per_round = avg_dmg / rounds_per_skill
        return int(total_hp / dmg_per_round) + 1 if dmg_per_round > 0 else 999

    def simulate_with_extra_coins(self, extra_rounds: int, total_coins: int,
                                  coin_consumption: int) -> bool:
        """检查用金币复活是否能击败Boss"""
        cost = extra_rounds * coin_consumption
        return cost <= total_coins
