"""
AI玩家任务一：基于局部贪心算法的实时资源拾取
- 视野严格限制为 3×3 九宫格
- 每步决策仅基于 3×3 视野 + 已访问记忆
- 不对全图跑 BFS/DFS/DP/穷举（符合验收要求）
- 评价指标：平均拾取资源价值
"""
from typing import List, Tuple, Set, Optional
from collections import deque

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

        # 路口记忆（用于必经陷阱时的回溯决策）
        self._junctions: Set[Tuple[int, int]] = set()  # 已发现的路口位置
        self._last_junction: Optional[Tuple[int, int]] = None  # 最近的路口
        self._steps_since_junction: int = 0  # 距离最近路口多少步
        self._backtrack_cooldown: int = 0  # 回溯冷却计数器（防震荡）
        self._backtrack_path: Optional[List[Tuple[int, int]]] = None  # 回溯执行的完整路径

        # 必经陷阱记忆：回溯时记住陷阱位置，用于后续方向平局时打破僵局
        self._remembered_mandatory_trap: Optional[Tuple[int, int]] = None

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

    def _bfs_in_visited(self, target: Tuple[int, int]
                         ) -> Optional[List[Tuple[int, int]]]:
        """在已访问区域内BFS寻路到目标。只走 self.visited 中的格子。
        返回路径（含起点终点），不可达返回 None。"""
        start = self.pos
        if start == target:
            return [start]
        if target not in self.visited:
            return None

        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == target:
                break
            for nb in self.get_neighbors(cur):
                # 只能走已访问过的格子
                if nb not in prev and nb in self.visited:
                    prev[nb] = cur
                    q.append(nb)

        if target not in prev:
            return None

        path = []
        cur = target
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    def _is_junction(self, pos: Tuple[int, int]) -> bool:
        """判断一个位置是否为路口：有2个以上未访问的安全可通行邻居"""
        nb = self.get_neighbors(pos)
        unvisited_safe = [n for n in nb
                          if n not in self.visited
                          and self._is_safe(n)
                          and n not in self._dead_ends]
        return len(unvisited_safe) >= 2

    def _update_junction_tracking(self):
        """更新路口记忆、距离计数和回溯冷却"""
        self._steps_since_junction += 1
        if self._backtrack_cooldown > 0:
            self._backtrack_cooldown -= 1
        if self._is_junction(self.pos):
            self._junctions.add(self.pos)
            self._last_junction = self.pos
            self._steps_since_junction = 0

    def _build_score_data(self, scores: dict, best_nb: Tuple[int, int]) -> dict:
        """将 tuple 格式的 scores 转为前端需要的 dict 格式。"""
        r0, c0 = self.pos
        score_data = {}
        for (dr, dc), (sc, parts) in scores.items():
            nr, nc = r0 + dr, c0 + dc
            ch = self.maze[nr][nc] if (0 <= nr < self.rows and 0 <= nc < self.cols) else '#'
            score_data[f"({dr:+d},{dc:+d})"] = {
                "pos": [nr, nc],
                "ch": ch,
                "score": round(sc, 2),
                "details": parts,
                "chosen": best_nb == (nr, nc)
            }
        return score_data

    def _is_safe(self, pos: Tuple[int, int]) -> bool:
        """是否安全通过：不是已知且未收集的陷阱，或已收集过"""
        if pos in self.known_traps and pos not in self.collected_positions:
            return False
        return True

    # ============================================================
    #  有限深度前沿搜索（仅在必经陷阱时使用，非全局BFS）
    # ============================================================

    def _count_accessible_frontier(self, from_pos: Tuple[int, int] = None) -> int:
        """统计AI九宫格内与目标格相邻的"未访问、安全、非死胡同"格子数。

        只统计AI当前位置的3×3九宫格范围内的格子——AI看不到九宫格外，
        所以九宫格外的邻居不算前沿。
        """
        tgt = from_pos if from_pos is not None else self.pos
        r_ai, c_ai = self.pos       # AI位置（九宫格中心）
        r_tgt, c_tgt = tgt           # 目标格
        count = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r_tgt + dr, c_tgt + dc
            # 只统计AI九宫格内的格子（看不见的不算）
            if abs(nr - r_ai) > 1 or abs(nc - c_ai) > 1:
                continue
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
        FRONTIER_THRESHOLD = 2   # 多少个前沿格子算"备选充足"（每方向九宫格内最多2个）

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

        # ============================================================
        #  路口回溯：必经陷阱时BFS规划完整路径，逐步走完
        # ============================================================
        JUNCTION_BACKTRACK_LIMIT = 7
        has_visible_reward = len(visible_golds) > 0

        # 正在执行回溯路径：视野出现金币则中断，否则继续沿路走
        if self._backtrack_path is not None:
            if has_visible_reward:
                self._backtrack_path = None  # 看到金币，中断回溯
            else:
                # 弹出已到达的位置，取下一步
                while self._backtrack_path and self._backtrack_path[0] == self.pos:
                    self._backtrack_path.pop(0)
                if not self._backtrack_path:
                    self._backtrack_path = None  # 已到达目标
                else:
                    next_step = self._backtrack_path[0]
                    scores = {}
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = self.pos[0] + dr, self.pos[1] + dc
                        if not self.is_passable(nr, nc):
                            scores[(dr, dc)] = (-999, ["墙"])
                        elif (nr, nc) == next_step:
                            scores[(dr, dc)] = (999, ["回溯路径"])
                        else:
                            scores[(dr, dc)] = (-99, ["回溯中"])
                    return next_step, self._build_score_data(scores, next_step)

        # 发起新回溯：必经陷阱 + 无可见金币 + 不在冷却
        in_cooldown = self._backtrack_cooldown > 0
        need_backtrack = trap_is_only_way and not has_visible_reward and not in_cooldown

        if need_backtrack:
            # 找最近的有效回溯目标（旁边有未访安全邻居的已访问位置）
            goal = None
            if self._last_junction is not None and self._is_junction(self._last_junction):
                goal = self._last_junction
            else:
                # 从当前位置BFS遍历已访问区域，找第一个旁边有未访安全格的位置
                frontier = deque([self.pos])
                bfs_prev = {self.pos: None}
                while frontier:
                    cur = frontier.popleft()
                    if cur != self.pos:
                        # 检查该位置旁边是否有未访问的安全邻居
                        for nb in self.get_neighbors(cur):
                            if nb not in self.visited and self._is_safe(nb) and nb not in self._dead_ends:
                                goal = cur
                                break
                    if goal is not None:
                        break
                    for nb in self.get_neighbors(cur):
                        if nb in self.visited and nb not in bfs_prev:
                            bfs_prev[nb] = cur
                            frontier.append(nb)
            if goal is not None and goal != self.pos:
                jpath = self._bfs_in_visited(goal)
                if jpath and len(jpath) >= 2:
                    # 目标就是最近路口 → 用实际步数；否则用BFS距离
                    if goal == self._last_junction:
                        branch_len = self._steps_since_junction
                    else:
                        branch_len = len(jpath) - 1
                    if branch_len <= JUNCTION_BACKTRACK_LIMIT:
                        # 去掉起点(当前pos)，只保留要走的路径
                        self._backtrack_path = jpath[1:]
                        self._backtrack_cooldown = 8
                        # 记忆必经陷阱位置（用于后续方向平局时打破僵局）
                        if new_any:
                            self._remembered_mandatory_trap = new_any[0]
                        if verbose:
                            print(f"  [回溯] 必经陷阱，分支长{branch_len}步"
                                  f"，沿BFS走{len(self._backtrack_path)}步到{goal}")
                        # 立即走回溯第一步，不走正常评分
                        next_step = self._backtrack_path[0]
                        scores = {}
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = self.pos[0] + dr, self.pos[1] + dc
                            if not self.is_passable(nr, nc):
                                scores[(dr, dc)] = (-999, ["墙"])
                            elif (nr, nc) == next_step:
                                scores[(dr, dc)] = (999, ["回溯路径"])
                            else:
                                scores[(dr, dc)] = (-99, ["回溯中"])
                        return next_step, self._build_score_data(scores, next_step)

        best_score = -999999.0
        best_nb = None
        scores = {}

        # 记忆金币在3×3视野外的（需要回头去拿的）
        memory_golds_outside = [g for g in self.known_golds
                                if g not in self.collected_positions
                                and (abs(g[0] - r0) > 1 or abs(g[1] - c0) > 1)]

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r0 + dr, c0 + dc
            if not self.is_passable(nr, nc):
                scores[(dr, dc)] = (-999, [f"墙({nr},{nc})"])
                continue

            # 检测该方向是否有记忆金币（在3×3视野外）
            heading_to_memory = False
            for g in memory_golds_outside:
                gr, gc = g
                in_dir = False
                if dr == -1 and gr < r0: in_dir = True
                elif dr == 1 and gr > r0: in_dir = True
                elif dc == -1 and gc < c0: in_dir = True
                elif dc == 1 and gc > c0: in_dir = True
                if in_dir:
                    heading_to_memory = True
                    break

            score = 0.0
            parts = []

            # 0. 步数成本
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
            #    记忆金币导航时打折50% → 鼓励回头拿记忆中的资源
            visits = self._visit_count.get((nr, nc), 0)
            if visits > 0:
                base_penalty = visits * 3.0
                revisit_discount = 0.0
                if heading_to_memory:
                    revisit_discount = 0.5
                elif trap_is_only_way:
                    revisit_discount = 0.5 * (1.0 - trap_acceptance)
                penalty = base_penalty * (1.0 - revisit_discount)
                score -= penalty
                if revisit_discount > 0.01:
                    parts.append(f"重访{visits}次-{penalty:.0f}(折{revisit_discount:.0%})")
                else:
                    parts.append(f"重访{visits}次-{penalty:.0f}")

            # 4. 回退惩罚：最近几步走过的格子
            #    记忆金币导航时打折50% → 降低回头拿记忆资源的门槛
            recent = set(self.path[-min(len(self.path), 4):])
            if (nr, nc) in recent:
                base_backtrack = 10.0
                backtrack_discount = 0.0
                if heading_to_memory:
                    backtrack_discount = 0.5
                elif trap_is_only_way:
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

            # 4. 记忆中该方向的金币（跳过当前3×3视野内的，避免与第3段重复计算）
            for g in list(self.known_golds):
                if g in self.collected_positions:
                    continue
                gr, gc = g
                # 若金币在当前3×3视野内，第3段已经算过了，不重复加
                if abs(gr - r0) <= 1 and abs(gc - c0) <= 1:
                    continue
                in_dir = False
                if dr == -1 and gr < r0: in_dir = True
                elif dr == 1 and gr > r0: in_dir = True
                elif dc == -1 and gc < c0: in_dir = True
                elif dc == 1 and gc > c0: in_dir = True
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
                # 九宫格内前沿=0（可能是走廊看不清，也可能是真死路）
                # 不额外惩罚：探索奖励和重复惩罚自然会引导——
                # 真死路走到底没路自然回头，走廊看不清走进去就看清了
                parts.append(f"前沿0")

            scores[(dr, dc)] = (score, parts)

            if score > best_score:
                best_score = score
                best_nb = (nr, nc)

        # 6. 记忆陷阱平局打破：四周都已访问 + 最高分出现平局时，
        #    用已知陷阱引力引导走向必经陷阱方向
        if best_nb is not None:
            # 检查四个可通行方向是否都已访问过
            all_visited = True
            for dr2, dc2 in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr2, nc2 = r0 + dr2, c0 + dc2
                if self.is_passable(nr2, nc2) and (nr2, nc2) not in self.visited:
                    all_visited = False
                    break

            if all_visited:
                # 找出所有平局的最高分方向
                tied = []
                for (dr, dc), (sc, _) in scores.items():
                    if sc == best_score:
                        tied.append((dr, dc))

                if len(tied) > 1 and self._remembered_mandatory_trap is not None:
                    tr, tc = self._remembered_mandatory_trap
                    # 对每个平局方向，计算到记忆陷阱的引力
                    for dr, dc in tied:
                        nr, nc = r0 + dr, c0 + dc
                        in_dir = False
                        if dr == -1 and tr < r0: in_dir = True
                        elif dr == 1 and tr > r0: in_dir = True
                        elif dc == -1 and tc < c0: in_dir = True
                        elif dc == 1 and tc > c0: in_dir = True
                        if in_dir:
                            dist = max(abs(tr - r0) + abs(tc - c0), 1)
                            bonus = TRAP_COST / dist
                            old_sc, old_parts = scores[(dr, dc)]
                            new_sc = old_sc + bonus
                            old_parts.append(f"忆T({tr},{tc})+{bonus:.1f}")
                            scores[(dr, dc)] = (new_sc, old_parts)

                    # 重新判定最佳方向
                    best_score = -999999.0
                    best_nb = None
                    for (dr, dc), (sc, _) in scores.items():
                        nr, nc = r0 + dr, c0 + dc
                        if sc > best_score:
                            best_score = sc
                            best_nb = (nr, nc)

        if verbose:
            print(f"  [评分] pos=({r0},{c0}) prev={prev_pos}")
            ch_list = []
            for (dr, dc), (sc, parts) in sorted(scores.items(), key=lambda x: -x[1][0]):
                nr, nc = r0+dr, c0+dc
                ch = self.maze[nr][nc] if (0 <= nr < self.rows and 0 <= nc < self.cols) else '#'
                vst = "新" if (nr, nc) not in self.visited else "访"
                arrow = "<-" if best_nb == (nr, nc) else "  "
                ch_list.append(f"  {arrow} ({dr:+d},{dc:+d})->({nr},{nc}) ch={ch} {vst} sc={sc:.2f} [{', '.join(parts)}]")
            for line in ch_list:
                print(line)

        # 构建前端用的评分数据
        return best_nb, self._build_score_data(scores, best_nb)

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
            # 踩到记忆的必经陷阱后清除记忆
            if self._remembered_mandatory_trap == pos:
                self._remembered_mandatory_trap = None

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
            # 1. 扫描3×3视野
            visible_golds, visible_traps = self.scan_visible()

            # 2. 四方向评分
            next_pos, step_score = self._best_direction(visible_golds, verbose=debug)
            cur_move = len(self.path) - 1
            cur_net = self.collected_gold - self.traps_hit * TRAP_COST
            self._step_scores.append({
                "pos": list(self.pos),
                "scores": step_score,
                "stats": {
                    "netGold": cur_net,
                    "moveCount": cur_move,
                    "ratio": round(cur_net / max(cur_move, 1), 2),
                },
            })

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
                            print(f"  [循环] 检测到循环! 强制走 {next_pos}")

            if next_pos is None or next_pos == self.pos:
                if debug:
                    print(f"  [卡住] 无法移动! pos={self.pos}")
                break

            if debug:
                print(f"  [移动] {self.pos} -> {next_pos}")
                if self.maze[next_pos[0]][next_pos[1]] in ('G', 'T'):
                    print(f"  [收集] 资源: {self.maze[next_pos[0]][next_pos[1]]}")

            # 4. 移动并收集
            self.pos = next_pos
            self.path.append(self.pos)
            self.visited.add(self.pos)
            # 回溯路径上的重访不增加计数
            if self._backtrack_path is None:
                self._visit_count[self.pos] = self._visit_count.get(self.pos, 0) + 1
            self.collect_at(self.pos)
            self._update_junction_tracking()

            # 记录Boss之后的步
            if self.pos != start_pos:
                new_steps.append(self.pos)
                new_scores.append({"pos": list(self.pos), "scores": step_score})

            # 5. 死胡同检测
            nb_now = self.get_neighbors(self.pos)
            if len(nb_now) == 1 and all(n in self.visited for n in nb_now):
                self._dead_ends.add(self.pos)
                if debug:
                    print(f"  [死胡同] 标记: {self.pos}")

            step += 1

        return new_steps, new_scores

    def run(self, debug: bool = False) -> dict:
        """运行局部贪心AI：3×3视野 + 四方向评分决策"""
        # 终点：有Boss就到Boss停下，没Boss直接到E
        _goal = self.boss_pos if self.boss_pos != (-1, -1) else self.end
        self._walk_to(_goal, debug=debug)

        # 统计（步数不含起点）
        trap_loss = self.traps_hit * TRAP_COST
        net_gold = self.collected_gold - trap_loss
        move_count = len(self.path) - 1
        ratio = net_gold / max(move_count, 1)

        return {
            "path": self.path,
            "totalGold": self.collected_gold,
            "trapDamage": trap_loss,
            "trapsHit": self.traps_hit,
            "netGold": net_gold,
            "pathLength": move_count,
            "ratio": round(ratio, 3),
            "reachedBoss": self.pos == self.boss_pos,
            "reachedEnd": False,
            "visionRange": self.vision,
            "strategy": "greedy_local",
            "stepScores": self._step_scores,
        }
