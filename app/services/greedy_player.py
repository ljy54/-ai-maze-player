"""
AI玩家任务一：基于局部贪心算法的实时资源拾取
- 视野严格限制为 3×3 九宫格
- 每步决策仅基于 3×3 视野 + 已访问记忆
- 不对全图跑 BFS/DFS/DP/穷举（符合验收要求）
- 评价指标：平均拾取资源价值
"""
from typing import List, Tuple, Set, Optional

# 资源价值常量
GOLD_VALUE = 50
TRAP_COST = 30


class GreedyPlayer:
    """局部贪心AI玩家：严格3×3视野 + 局部步进决策，无全局搜索"""

    def __init__(self, maze: List[List[str]], vision_range: int = 1):
        self.maze = [list(row) for row in maze]
        self.rows = len(maze)
        self.cols = len(maze[0]) if self.rows > 0 else 0
        self.vision = vision_range

        # 关键位置（仅用于知道终点的大致方位，不用来做全局寻路）
        self.start = self._find('S')
        self.end = self._find('E')
        self.boss_pos = self._find('B')

        # 当前状态
        self.pos = self.start
        self.collected_gold = 0
        self.traps_hit = 0
        self.path: List[Tuple[int, int]] = [self.start]
        self.visited: Set[Tuple[int, int]] = {self.start}
        self.collected_positions: Set[Tuple[int, int]] = set()

        # 视野记忆：已发现但未收集的资源
        self.known_golds: Set[Tuple[int, int]] = set()
        self.known_traps: Set[Tuple[int, int]] = set()

        # 循环检测与死胡同记忆
        self._recent_pos: List[Tuple[int, int]] = []  # 最近位置
        self._dead_ends: Set[Tuple[int, int]] = set()  # 已确认的死胡同
        self._visit_count: dict = {}  # 每格访问次数（防震荡）
        self._step_scores: list = []  # 每步方向评分（前端可视化用）

    # ============================================================
    #  基础工具方法
    # ============================================================

    def _find(self, ch: str) -> Tuple[int, int]:
        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r][c] == ch:
                    return (r, c)
        return (-1, -1)

    def is_passable(self, r: int, c: int) -> bool:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return False
        return self.maze[r][c] != '#'

    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """获取四个方向的可通行邻居（纯局部，只看相邻格）"""
        r, c = pos
        nb = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_passable(nr, nc):
                nb.append((nr, nc))
        return nb

    def _manhattan(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _is_safe(self, pos: Tuple[int, int]) -> bool:
        """是否安全通过：不是已知且未收集的陷阱，或已收集过"""
        if pos in self.known_traps and pos not in self.collected_positions:
            return False
        return True

    # ============================================================
    #  有限深度前沿搜索（仅在必经陷阱时使用，非全局BFS）
    # ============================================================

    def _count_accessible_frontier(self, from_pos: Tuple[int, int] = None,
                                     max_depth: int = None) -> int:
        """统计指定位置 3×3 视野内"未访问、安全、非死胡同"的格子数。

        严格限制在 vision_range=1 的 3×3 九宫格内，不沿已访问路径向外延伸。
        用于判断"当前/下一步位置附近是否还有备选路线"。

        max_depth 参数保留以兼容旧调用，实际不再使用。
        """
        pos = from_pos if from_pos is not None else self.pos
        r0, c0 = pos
        count = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r0 + dr, c0 + dc
            if not self.is_passable(nr, nc):
                continue
            if (nr, nc) in self.visited:
                continue
            if not self._is_safe((nr, nc)):
                continue
            if (nr, nc) in self._dead_ends:
                continue
            count += 1
        return count

    # ============================================================
    #  视野扫描
    # ============================================================

    def scan_visible(self) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
        """扫描3×3视野内的金币和陷阱，更新记忆"""
        r0, c0 = self.pos
        golds = []
        traps = []
        for r in range(max(0, r0 - self.vision), min(self.rows, r0 + self.vision + 1)):
            for c in range(max(0, c0 - self.vision), min(self.cols, c0 + self.vision + 1)):
                pt = (r, c)
                if pt in self.collected_positions:
                    continue
                ch = self.maze[r][c]
                if ch == 'G':
                    golds.append(pt)
                    self.known_golds.add(pt)
                elif ch == 'T':
                    traps.append(pt)
                    self.known_traps.add(pt)
        return golds, traps

    # ============================================================
    #  方向评估（核心：基于3×3视野+记忆，直接给4个方向打分）
    # ============================================================

    def _best_direction(self, visible_golds: List[Tuple[int, int]],
                         verbose: bool = False) -> tuple:
        """
        评估4个可通行邻居，选综合收益最高的方向走一步。
        """
        r0, c0 = self.pos
        prev_pos = self.path[-2] if len(self.path) >= 2 else None

        # ============================================================
        #  动态陷阱接受度（替换二元必经判断）
        #  核心思想：不只问"是否必经"，而问"附近还有多少备选路线"
        # ============================================================
        STEP_COST = 1.5          # 每步基础成本，鼓励短路径
        FRONTIER_THRESHOLD = 3   # 多少个前沿格子算"备选充足"（3×3视野最多4方向）

        all_nb = self.get_neighbors(self.pos)
        new_safe = [n for n in all_nb
                    if n not in self.visited and self._is_safe(n) and n not in self._dead_ends]
        new_any = [n for n in all_nb
                   if n not in self.visited and n not in self._dead_ends]
        trap_is_only_way = len(new_any) > 0 and len(new_safe) == 0

        # 仅在"所有未访问邻居都是陷阱"时统计备选路线
        if trap_is_only_way:
            n_frontier = self._count_accessible_frontier()
        else:
            n_frontier = FRONTIER_THRESHOLD  # 有安全邻居 → 视为备选充足

        # trap_acceptance ∈ [0, 1]: 0=强烈回避陷阱, 1=完全接受陷阱
        trap_acceptance = 1.0 - min(1.0, n_frontier / FRONTIER_THRESHOLD)

        # 被困信号：在同一格子反复徘徊 → 逐渐接受陷阱（防止无限徘徊）
        stuck_visits = max(0, self._visit_count.get(self.pos, 1) - 1)
        if stuck_visits >= 2:
            trap_acceptance = min(1.0, trap_acceptance + 0.20 * stuck_visits)

        best_score = -999999.0
        best_nb = None
        scores = {}  # 用于调试

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r0 + dr, c0 + dc
            if not self.is_passable(nr, nc):
                # 墙也记录（前端可视化用）
                scores[(dr, dc)] = (-999, [f"墙({nr},{nc})"])
                continue

            score = 0.0
            parts = []  # 评分明细（调试用）

            # 0. 步数成本（每步都有代价，鼓励短路径，避免绕远路避陷阱）
            score -= STEP_COST

            # 1. 探索奖励（未访问格子优先）
            #    陷阱格子：探索奖励随接受度缩放 → 有备选时不鼓励探陷阱
            if (nr, nc) not in self.visited:
                cell_ch = self.maze[nr][nc]
                if cell_ch == 'T':
                    explore_bonus = 15.0 * trap_acceptance
                    score += explore_bonus
                    if explore_bonus > 0.01:
                        parts.append(f"探陷+{explore_bonus:.1f}")
                else:
                    score += 15.0
                    parts.append(f"探索+15")

            # 2. 死胡同惩罚：已知走不通的死路
            if (nr, nc) in self._dead_ends:
                score -= 50.0
                parts.append(f"死胡同-50")

            # 3. 重复访问惩罚：每多走一次扣3分
            #    有备选路线时打折 → 鼓励"探索性回溯"寻找安全出口
            visits = self._visit_count.get((nr, nc), 0)
            if visits > 0:
                base_penalty = visits * 3.0
                revisit_discount = 0.0
                if trap_is_only_way:
                    revisit_discount = 0.5 * (1.0 - trap_acceptance)
                penalty = base_penalty * (1.0 - revisit_discount)
                score -= penalty
                if revisit_discount > 0.01:
                    parts.append(f"重访{visits}次-{penalty:.0f}(折{revisit_discount:.0%})")
                else:
                    parts.append(f"重访{visits}次-{penalty:.0f}")

            # 4. 回退惩罚：最近几步走过的格子
            #    有备选路线时打折 → 降低"回头找安全路"的门槛
            recent = set(self.path[-min(len(self.path), 4):])
            if (nr, nc) in recent:
                base_backtrack = 15.0
                backtrack_discount = 0.0
                if trap_is_only_way:
                    backtrack_discount = 0.5 * (1.0 - trap_acceptance)
                penalty = base_backtrack * (1.0 - backtrack_discount)
                score -= penalty
                if backtrack_discount > 0.01:
                    parts.append(f"刚走过-{penalty:.0f}(折{backtrack_discount:.0%})")
                else:
                    parts.append(f"刚走过-{penalty:.0f}")

            # 3. 3×3内该方向的资源
            for r in range(max(0, r0 - 1), min(self.rows, r0 + 2)):
                for c in range(max(0, c0 - 1), min(self.cols, c0 + 2)):
                    if (r, c) == self.pos or (r, c) in self.collected_positions:
                        continue
                    in_dir = False
                    if dr == -1 and r < r0: in_dir = True
                    elif dr == 1 and r > r0: in_dir = True
                    elif dc == -1 and c < c0: in_dir = True
                    elif dc == 1 and c > c0: in_dir = True
                    if not in_dir:
                        continue
                    dist = abs(r - r0) + abs(c - c0)
                    ch = self.maze[r][c]
                    if ch == 'G':
                        val = GOLD_VALUE / dist
                        score += val
                        parts.append(f"G({r},{c})+{val:.1f}")
                    elif ch == 'T':
                        # 动态陷阱成本：trap_acceptance 越高 → 扣分越少
                        effective_cost = TRAP_COST * (1.0 - trap_acceptance)
                        if effective_cost > 0.01:
                            val = effective_cost / dist
                            score -= val
                            parts.append(f"T({r},{c})-{val:.1f}(接{trap_acceptance:.0%})")
                        else:
                            parts.append(f"T({r},{c})必经")

            # 4. 记忆中该方向的金币
            for g in list(self.known_golds):
                if g in self.collected_positions:
                    continue
                gr, gc = g
                in_dir = False
                if dr == -1 and gr <= r0: in_dir = True
                elif dr == 1 and gr >= r0: in_dir = True
                elif dc == -1 and gc <= c0: in_dir = True
                elif dc == 1 and gc >= c0: in_dir = True
                if in_dir:
                    dist = max(abs(gr - r0) + abs(gc - c0), 1)
                    val = GOLD_VALUE / dist  # 已知未收金币与视野内同等权重
                    score += val
                    parts.append(f"忆G({gr},{gc})+{val:.1f}")

            # 5. 前沿引力：不看终点坐标，追踪未探索区域的"势能"
            #    陷阱格需要足够大的前沿才值得进入（防止为小死胡同踩陷阱）
            n_frontier_dir = self._count_accessible_frontier(
                from_pos=(nr, nc)
            )
            dir_ch = self.maze[nr][nc]
            MIN_FRONTIER_FOR_TRAP = 2  # 陷阱格至少需要2个前沿格子才值得进入（3×3视野）
            if n_frontier_dir > 0:
                frontier_score = 3.0 * min(1.0, n_frontier_dir / 3.0)
                if dir_ch == 'T':
                    frontier_score *= trap_acceptance
                    # 前沿不足的陷阱死胡同 → 额外惩罚
                    if n_frontier_dir < MIN_FRONTIER_FOR_TRAP:
                        penalty = 8.0 * (1.0 - n_frontier_dir / MIN_FRONTIER_FOR_TRAP)
                        frontier_score -= penalty
                        parts.append(f"T窄{n_frontier_dir}-{penalty:.1f}")
                score += frontier_score
                if dir_ch != 'T' or n_frontier_dir >= MIN_FRONTIER_FOR_TRAP:
                    parts.append(f"前沿{n_frontier_dir}+{frontier_score:.1f}")
            else:
                # 无前沿 → 死路，轻微惩罚
                score -= 2.0
                parts.append(f"死路-2")

            scores[(dr, dc)] = (score, parts)

            if score > best_score:
                best_score = score
                best_nb = (nr, nc)

        if verbose:
            print(f"  [评分] pos=({r0},{c0}) prev={prev_pos}")
            ch_list = []
            for (dr, dc), (sc, parts) in sorted(scores.items(), key=lambda x: -x[1][0]):
                nr, nc = r0+dr, c0+dc
                ch = self.maze[nr][nc]
                vst = "新" if (nr, nc) not in self.visited else "访"
                arrow = "←" if best_nb == (nr, nc) else " "
                ch_list.append(f"  {arrow} ({dr:+d},{dc:+d})→({nr},{nc}) ch={ch} {vst} 得分={sc:.2f} [{', '.join(parts)}]")
            for line in ch_list:
                print(line)

        # 构建前端用的评分数据
        score_data = {}
        for (dr, dc), (sc, parts) in scores.items():
            nr, nc = r0+dr, c0+dc
            ch = self.maze[nr][nc] if (0 <= nr < self.rows and 0 <= nc < self.cols) else '#'
            score_data[f"({dr:+d},{dc:+d})"] = {
                "pos": [nr, nc],
                "ch": ch,
                "score": round(sc, 2),
                "details": parts,
                "chosen": best_nb == (nr, nc)
            }
        return best_nb, score_data

    # ============================================================
    #  资源收集
    # ============================================================

    def collect_at(self, pos: Tuple[int, int]):
        """在当前位置收集资源"""
        if pos in self.collected_positions:
            return
        ch = self.maze[pos[0]][pos[1]]
        if ch == 'G':
            self.collected_gold += GOLD_VALUE
            self.collected_positions.add(pos)
            self.known_golds.discard(pos)
        elif ch == 'T':
            self.traps_hit += 1
            self.collected_positions.add(pos)
            self.known_traps.discard(pos)

    # ============================================================
    #  主循环
    # ============================================================

    def _walk_to(self, goal: Tuple[int, int], debug: bool = False) -> Tuple[List, List]:
        """核心步进循环：从当前位置走到goal，复用 _best_direction 所有评分逻辑。
        返回 (新增的路径点列表, 新增的stepScores列表)"""
        new_steps = []
        new_scores = []
        step = 0
        max_steps = self.rows * self.cols * 3
        start_pos = self.pos  # 记录起始位置

        while self.pos != goal and step < max_steps:
            step += 1

            # 1. 扫描3×3视野
            visible_golds, visible_traps = self.scan_visible()

            # 2. 四方向评分
            next_pos, step_score = self._best_direction(visible_golds, verbose=debug)
            self._step_scores.append({"pos": list(self.pos), "scores": step_score})

            # 3. 循环检测
            self._recent_pos.append(self.pos)
            if len(self._recent_pos) > 8:
                self._recent_pos = self._recent_pos[-8:]

            if len(self._recent_pos) >= 8 and next_pos is not None:
                last4 = self._recent_pos[-4:]
                prev4 = self._recent_pos[-8:-4]
                if last4 == prev4:
                    prev_pos = self.path[-2] if len(self.path) >= 2 else None
                    alt = [n for n in self.get_neighbors(self.pos) if n != prev_pos]
                    if alt:
                        next_pos = alt[0]
                        if debug:
                            print(f"  ⚠ 检测到循环! 强制走 {next_pos}")

            if next_pos is None or next_pos == self.pos:
                if debug:
                    print(f"  ❌ 卡住了! pos={self.pos}")
                break

            if debug:
                print(f"  → 移动: {self.pos} → {next_pos}")
                if self.maze[next_pos[0]][next_pos[1]] in ('G', 'T'):
                    print(f"  💰 收集: {self.maze[next_pos[0]][next_pos[1]]}")

            # 4. 移动并收集
            self.pos = next_pos
            self.path.append(self.pos)
            self.visited.add(self.pos)
            self._visit_count[self.pos] = self._visit_count.get(self.pos, 0) + 1
            self.collect_at(self.pos)

            # 记录Boss之后的步
            if self.pos != start_pos:
                new_steps.append(self.pos)
                new_scores.append({"pos": list(self.pos), "scores": step_score})

            # 5. 死胡同检测
            nb_now = self.get_neighbors(self.pos)
            if len(nb_now) == 1 and all(n in self.visited for n in nb_now):
                self._dead_ends.add(self.pos)
                if debug:
                    print(f"  🔒 标记死胡同: {self.pos}")

        return new_steps, new_scores

    def run(self, debug: bool = False) -> dict:
        """运行局部贪心AI：3×3视野 + 四方向评分决策"""
        # 终点：有Boss就到Boss停下，没Boss直接到E
        _goal = self.boss_pos if self.boss_pos != (-1, -1) else self.end
        self._walk_to(_goal, debug=debug)

        # 统计
        trap_loss = self.traps_hit * TRAP_COST
        net_gold = self.collected_gold - trap_loss

        return {
            "path": self.path,
            "totalGold": self.collected_gold,
            "trapDamage": trap_loss,
            "trapsHit": self.traps_hit,
            "netGold": net_gold,
            "pathLength": len(self.path),
            "reachedBoss": self.pos == self.boss_pos,
            "reachedEnd": False,  # 由 ai_engine 在Boss战后判定
            "visionRange": self.vision,
            "strategy": "greedy_local",
            "stepScores": self._step_scores,
        }
