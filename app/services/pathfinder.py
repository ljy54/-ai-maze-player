from typing import List, Tuple, Dict
from itertools import combinations
from .maze_parser import MazeParser

GOLD_VALUE = 50
TRAP_PENALTY = 30


class PathFinder:
    """路径规划引擎：在迷宫中寻找最优路径"""

    def __init__(self, parser: MazeParser):
        self.parser = parser
        self.key_points = parser.get_all_key_points()
        self.start = parser.start
        self.end = parser.end
        self.boss_pos = parser.boss_pos
        self.golds = parser.golds
        self.traps = parser.traps
        self.n_golds = len(self.golds)

        # 预计算所有关键点之间的最短距离
        self.dist_cache: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}
        for pt in self.key_points:
            self.dist_cache[pt] = parser.bfs_distance(pt)

    def distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        """两点间最短距离（BFS缓存）"""
        return self.dist_cache.get(a, {}).get(b, 999999)

    def is_reachable(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        return b in self.dist_cache.get(a, {})

    def find_best_path(self) -> Tuple[List[Tuple[int, int]], int, List[Tuple[int, int]]]:
        """
        状态压缩DP：枚举收集哪些金币，决定最优路径。
        返回 (完整路径, 净金币收益, 收集的金币列表)
        """
        if self.n_golds == 0:
            path = self._reconstruct_path_bfs(self.start, self.end)
            return path, 0, []

        best_net = -999999
        best_path = []
        best_collected = []

        # DP[mask][i]: mask表示已收集的金币子集，i表示最后停留在第i个金币
        # 值: (最小步数, 经过的陷阱惩罚总和, 路径前驱)
        INF = 999999
        dp = {}
        parent = {}

        # 初始化：从起点到每个金币
        for i in range(self.n_golds):
            d = self.distance(self.start, self.golds[i])
            if d < INF:
                # 计算从起点到该金币路上经过的陷阱
                path_points = self._reconstruct_path_bfs(self.start, self.golds[i])
                trap_hits = self._count_traps_on_path(path_points)
                dp[(1 << i, i)] = (d, trap_hits * TRAP_PENALTY)

        # DP
        for mask in range(1 << self.n_golds):
            for last in range(self.n_golds):
                if not (mask & (1 << last)):
                    continue
                state = (mask, last)
                if state not in dp:
                    continue
                cur_dist, cur_penalty = dp[state]

                # 尝试去下一个未收集的金币
                for nxt in range(self.n_golds):
                    if mask & (1 << nxt):
                        continue
                    d = self.distance(self.golds[last], self.golds[nxt])
                    if d >= INF:
                        continue
                    path_points = self._reconstruct_path_bfs(self.golds[last], self.golds[nxt])
                    trap_hits = self._count_traps_on_path(path_points)
                    new_mask = mask | (1 << nxt)
                    new_dist = cur_dist + d
                    new_penalty = cur_penalty + trap_hits * TRAP_PENALTY
                    new_state = (new_mask, nxt)
                    if new_state not in dp or dp[new_state][0] > new_dist:
                        dp[new_state] = (new_dist, new_penalty)
                        parent[new_state] = state

        # 评估每种收集方案：从最后金币到Boss再到终点
        for mask in range(1 << self.n_golds):
            for last in range(self.n_golds):
                if not (mask & (1 << last)):
                    continue
                state = (mask, last)
                if state not in dp:
                    continue
                cur_dist, cur_penalty = dp[state]

                # 去Boss
                to_boss = self.distance(self.golds[last], self.boss_pos)
                if to_boss >= INF:
                    continue
                path_to_boss = self._reconstruct_path_bfs(self.golds[last], self.boss_pos)
                trap_to_boss = self._count_traps_on_path(path_to_boss) * TRAP_PENALTY

                # 从Boss到终点
                to_end = self.distance(self.boss_pos, self.end)
                if to_end >= INF:
                    continue
                path_to_end = self._reconstruct_path_bfs(self.boss_pos, self.end)
                trap_to_end = self._count_traps_on_path(path_to_end) * TRAP_PENALTY

                collected = mask.bit_count()
                net = collected * GOLD_VALUE - cur_penalty - trap_to_boss - trap_to_end

                if net > best_net:
                    best_net = net
                    # 重建路径
                    best_collected = [self.golds[i] for i in range(self.n_golds) if mask & (1 << i)]
                    best_path = self._build_full_path(mask, last, parent)

        return best_path, best_net, best_collected

    def _reconstruct_path_bfs(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """BFS重建两点间最短路径"""
        prev = {start: None}
        q = [start]
        q_idx = 0
        while q_idx < len(q):
            cur = q[q_idx]
            q_idx += 1
            if cur == end:
                break
            for nb in self.parser.get_neighbors(cur):
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)

        if end not in prev:
            return []

        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    def _count_traps_on_path(self, path: List[Tuple[int, int]]) -> int:
        """统计路径上经过的陷阱数量（不包含起点和Boss点）"""
        count = 0
        for pt in path:
            r, c = pt
            if self.parser.maze[r][c] == "T":
                count += 1
        return count

    def _build_full_path(self, mask: int, last: int, parent: dict) -> List[Tuple[int, int]]:
        """根据DP结果重建完整路径：S → golds → Boss → E"""
        # 重建金币收集顺序
        order = []
        cur_mask = mask
        cur_last = last
        while cur_mask:
            order.append(cur_last)
            prev_state = parent.get((cur_mask, cur_last))
            if prev_state is None:
                break
            cur_mask, cur_last = prev_state
        order.reverse()

        full_path = []

        # S → 第一个金币
        if order:
            seg = self._reconstruct_path_bfs(self.start, self.golds[order[0]])
            full_path.extend(seg)
        else:
            seg = self._reconstruct_path_bfs(self.start, self.boss_pos)
            full_path.extend(seg)

        # 金币之间
        for i in range(len(order) - 1):
            seg = self._reconstruct_path_bfs(self.golds[order[i]], self.golds[order[i + 1]])
            if full_path:
                full_path.pop()  # 去掉重复的起点
            full_path.extend(seg)

        # 最后一个金币 → Boss
        if full_path:
            full_path.pop()
        if order:
            seg = self._reconstruct_path_bfs(self.golds[order[-1]], self.boss_pos)
        else:
            seg = self._reconstruct_path_bfs(self.start, self.boss_pos)
        full_path.extend(seg)

        # Boss → 终点
        full_path.pop()
        seg = self._reconstruct_path_bfs(self.boss_pos, self.end)
        full_path.extend(seg)

        return full_path
