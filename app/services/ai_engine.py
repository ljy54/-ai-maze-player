"""
AI玩家引擎：统一入口，包含两个独立任务
- 任务一 (greedy)：贪心实时资源拾取 — 评价指标：平均拾取资源价值
- 任务二 (local_optimal)：九宫格视野贪心最优 — 评价指标：资源获取/路径比值最大
"""
from typing import List, Tuple
from .maze_parser import MazeParser
from .pathfinder import PathFinder
from .boss_simulator import BossSimulator
from .greedy_player import GreedyPlayer
from .local_optimal_player import LocalOptimalPlayer


class AIEngine:
    """AI决策引擎：整合路径规划与Boss战斗优化"""

    # ============================================================
    #  任务一：贪心实时资源拾取
    #  评价指标：平均拾取资源价值（多迷宫取均值）
    #  算法：有限视野 + 贪心性价比选择
    # ============================================================
    def solve_greedy(self, maze: List[List[str]], boss_hps: List[int],
                     player_skills: List[List[int]], min_rounds: int,
                     coin_consumption: int, vision_range: int = 1) -> dict:
        """任务一：贪心AI求解"""
        skills = [(s[0], s[1]) for s in player_skills]

        # Step 1: 运行贪心玩家 S→Boss
        player = GreedyPlayer(maze, vision_range=vision_range)
        greedy_result = player.run(debug=True)

        # Step 2: 检查是否到达Boss
        reached_boss = greedy_result["reachedBoss"]

        # Step 3: Boss战斗
        can_beat = False
        rounds_needed = 0
        skill_seq = []
        boss_defeated = False
        revival_cost = 0

        if reached_boss:
            current_net = player.collected_gold - player.traps_hit * 30
            simulator = BossSimulator(boss_hps, skills, min_rounds)
            # 使用复活机制：限定回合打不死则从第一个Boss重新打
            can_beat, all_sequences, revival_count, revival_cost, rounds_needed = \
                simulator.solve_with_revival(current_net, coin_consumption)

            # 展平多段序列为单一 skill_seq
            skill_seq = []
            for seg in all_sequences:
                skill_seq.extend(seg)

            # 记录Boss战结果
            boss_defeated = can_beat

            # 找E位置
            end_pos = (-1, -1)
            for r in range(len(maze)):
                for c in range(len(maze[0])):
                    if maze[r][c] == 'E': end_pos = (r, c)

            # 无论Boss战结果如何，都继续走向终点（打不过也不卡在Boss）
            if end_pos != (-1, -1):
                player._walk_to(end_pos)

        # 最终路径和评分
        path = player.path
        all_step_scores = player._step_scores

        TRAP_COST = 30
        total_gold = player.collected_gold
        traps_hit = player.traps_hit
        trap_damage = traps_hit * TRAP_COST
        net_from_path = total_gold - trap_damage
        final_net = net_from_path - revival_cost
        reached_end = len(path) > 0 and maze[path[-1][0]][path[-1][1]] == 'E'

        return {
            "path": path,
            "skillSequence": [
                {"round": s[0] + 1, "skillIndex": s[1], "targetBoss": s[2]}
                for s in skill_seq
            ],
            "stats": {
                "totalCoins": total_gold,
                "collectedGolds": total_gold // 50,
                "trapDamage": trap_damage,
                "trapsHit": traps_hit,
                "bossDefeated": boss_defeated,
                "roundsUsed": rounds_needed,
                "minRounds": min_rounds,
                "revivalCost": revival_cost,
                "revivalCount": revival_count,
                "netCoins": final_net,
                "pathLength": len(path) - 1,  # 最终路径步数（不含起点）
                "ratio": round(final_net / max(len(path) - 1, 1), 3),
                "reachedEnd": reached_end,
            },
            # 任务一特有评价字段
            "evaluation": {
                "strategy": "greedy",
                "visionRange": vision_range,
                "primaryMetric": "averageCollectedResourceValue",
                "description": "评价指标：平均拾取资源价值。需要在多个不同迷宫上运行取均值",
                "collectedValue": total_gold,
                "trapPenalty": trap_damage,
                "netValue": net_from_path,
            },
            "stepScores": all_step_scores,
        }

    def build_task1_result_json(self, result: dict, args: dict) -> dict:
        """将 solve_greedy 的内部结果转为任务一输出 JSON 格式。
        参照 maze_7_7_0_result.json 的字段结构。"""
        stats = result["stats"]
        path = result["path"]
        move_steps = len(path) - 1
        final_coin = stats["netCoins"]

        # Boss 技能序列拆分（按复活次数分段）
        skill_seq = result["skillSequence"]  # [{round, skillIndex, targetBoss}, ...]
        min_rounds = args["min_rounds"]
        revival_cost = stats["revivalCost"]
        coin_consumption = args.get("coin_consumption", 10)

        # 每 min_rounds 回合为一次挑战，按回合号分段
        sequences = []
        for sk in skill_seq:
            r = sk["round"] - 1  # 1-base → 0-base
            seg = r // max(min_rounds, 1)
            while len(sequences) <= seg:
                sequences.append([])
            sequences[seg].append(sk["skillIndex"])

        # 若没有技能序列，填充空数组
        if not sequences:
            sequences = [[]]

        return {
            "success": stats["bossDefeated"] or stats.get("reachedEnd", False),
            "path": path,
            "path_length": len(path),
            "move_steps": move_steps,
            "final_coin": final_coin,
            "coin_step_ratio": round(final_coin / max(move_steps, 1), 10),
            "boss_success": stats["bossDefeated"],
            "boss_total_turns": stats["roundsUsed"],
            "boss_revive_count": revival_cost // coin_consumption if revival_cost > 0 else 0,
            "boss_coin_cost": revival_cost,
            "boss_skill_sequence_lengths": [len(s) for s in sequences],
            "boss_skill_sequences": sequences,
        }

    # ============================================================
    #  任务二：九宫格视野贪心最优路径
    #  评价指标：资源获取与路径步数的比值最大化
    #  算法：3×3视野 + 记忆 + 贪心选择可见最佳金币
    #  停止条件：九宫格内无未收集资源
    # ============================================================
    def solve_global(self, maze: List[List[str]], boss_hps: List[int],
                     player_skills: List[List[int]], min_rounds: int,
                     coin_consumption: int) -> dict:
        """任务二：九宫格视野贪心最优AI求解"""
        skills = [(s[0], s[1]) for s in player_skills]

        # Step 1: 运行局部贪心最优玩家（3×3视野，记忆机制）
        player = LocalOptimalPlayer(maze, vision_range=1)
        result = player.run(debug=True)

        # Step 2: 检查迷宫是否有Boss，决定是否需要Boss战
        boss_pos = player._find('B')
        reached_boss = boss_pos != (-1, -1) and player.pos == boss_pos

        can_beat = False
        rounds_needed = 0
        skill_seq = []
        boss_defeated = False
        revival_cost = 0

        # 只有当迷宫有Boss且玩家走到了Boss位置时才模拟战斗
        if reached_boss and boss_hps:
            simulator = BossSimulator(boss_hps, skills, min_rounds)
            can_beat, rounds_needed, skill_seq = simulator.solve()

            if can_beat:
                boss_defeated = True
            else:
                extra = max(0, rounds_needed - min_rounds)
                num_revivals = (extra + min_rounds - 1) // min_rounds
                revival_cost = num_revivals * coin_consumption
                if result["netGold"] >= revival_cost:
                    boss_defeated = True
                else:
                    revival_cost = 0

        # Step 3: 计算评价指标
        ratio = result["netGold"] / max(result["pathLength"], 1)

        return {
            "path": result["path"],
            "skillSequence": [
                {"round": s[0] + 1, "skillIndex": s[1], "targetBoss": s[2]}
                for s in skill_seq
            ],
            "stats": {
                "totalCoins": result["totalGold"],
                "collectedGolds": result["totalGold"] // 50,
                "trapDamage": result["trapDamage"],
                "trapsHit": result["trapsHit"],
                "bossDefeated": boss_defeated,
                "roundsUsed": rounds_needed,
                "minRounds": min_rounds,
                "revivalCost": revival_cost,
                "netCoins": result["netGold"] - revival_cost,
                "pathLength": result["pathLength"],
                "ratio": round(ratio, 3),
            },
            # 任务二特有评价字段
            "evaluation": {
                "strategy": "local_optimal_greedy",
                "visionRange": 1,
                "primaryMetric": "resourcePathRatio",
                "description": f"评价指标：资源获取/路径步数比值 = {round(ratio, 3)}。比值越大越好。停止原因：{result['stopReason']}",
                "resourceValue": result["totalGold"],
                "trapPenalty": result["trapDamage"],
                "netValue": result["netGold"],
                "pathSteps": result["pathLength"],
                "ratio": round(ratio, 3),
            },
            "stepScores": result.get("stepScores", []),
        }
