"""测试AI引擎的完整流程"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_engine import AIEngine
from app.services.maze_parser import MazeParser
from app.services.pathfinder import PathFinder
from app.services.boss_simulator import BossSimulator
import json

# 加载测试数据
test_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "maze_15_15.json")
with open(test_data_path, "r") as f:
    data = json.load(f)

maze = data["maze"]
boss_hps = data["B"]
skills_raw = data["PlayerSkills"]
min_rounds = data.get("minRouds", 20)
coin_consumption = data.get("CoinConsumption", 5)

print("=" * 60)
print("AI迷宫玩家 - 算法测试")
print("=" * 60)

# 1. 迷宫解析
print("\n📋 Step 1: 迷宫解析")
parser = MazeParser(maze)
print(f"  迷宫大小: {parser.rows}x{parser.cols}")
print(f"  起点: {parser.start}")
print(f"  终点: {parser.end}")
print(f"  Boss位置: {parser.boss_pos}")
print(f"  金币数: {len(parser.golds)} -> {parser.golds}")
print(f"  陷阱数: {len(parser.traps)} -> {parser.traps}")

# 连通性检查
for name, pt in [("起点", parser.start), ("终点", parser.end), ("Boss", parser.boss_pos)]:
    reachable = pt in parser.bfs_distance(parser.start)
    print(f"  起点->{name}: {'✅ 可达' if reachable else '❌ 不可达'}")

# 2. 路径规划
print("\n📋 Step 2: 路径规划")
pathfinder = PathFinder(parser)
best_path, net_gold, collected = pathfinder.find_best_path()

print(f"  收集金币: {len(collected)} 个 -> {collected}")
print(f"  路径长度: {len(best_path)} 步")

# 统计路径上的收益
gold_on_path = sum(1 for pt in best_path if maze[pt[0]][pt[1]] == "G")
trap_on_path = sum(1 for pt in best_path if maze[pt[0]][pt[1]] == "T")
print(f"  路径经过金币: {gold_on_path} 个 = +{gold_on_path * 50}")
print(f"  路径经过陷阱: {trap_on_path} 个 = -{trap_on_path * 30}")
print(f"  路径净收益: {net_gold}")

# 3. Boss战斗
print("\n📋 Step 3: Boss战斗模拟")
skills = [(s[0], s[1]) for s in skills_raw]
print(f"  Boss血量: {boss_hps} (总HP={sum(boss_hps)})")
print(f"  技能: {skills}")
print(f"  回合限制: {min_rounds}")

simulator = BossSimulator(boss_hps, skills, min_rounds)
can_beat, rounds_needed, skill_seq = simulator.solve()

print(f"  能否在{min_rounds}回合内击败: {'✅ 是' if can_beat else '❌ 否'}")
print(f"  需要回合数: {rounds_needed}")

if skill_seq:
    print(f"  技能序列 ({len(skill_seq)} 步):")
    for r, si, bi in skill_seq[:20]:
        print(f"    回合{r+1}: 技能{si}(伤{skills[si][0]},冷{skills[si][1]}) -> Boss{bi}")
    if len(skill_seq) > 20:
        print(f"    ... 共 {len(skill_seq)} 步")

# 4. 全局AI引擎
print("\n📋 Step 4: 全局AI引擎")
engine = AIEngine()
result = engine.solve_global(maze, boss_hps, skills_raw, min_rounds, coin_consumption)

print(f"  成功: {result['stats']}")
print(f"  路径长度: {result['stats']['pathLength']}")
print(f"  总金币: {result['stats']['totalCoins']}")
print(f"  陷阱伤害: {result['stats']['trapDamage']}")
print(f"  Boss击败: {result['stats']['bossDefeated']}")
print(f"  使用回合: {result['stats']['roundsUsed']}")
print(f"  复活消耗: {result['stats']['revivalCost']}")
print(f"  净收益: {result['stats']['netCoins']}")

print("\n" + "=" * 60)
print("✅ 测试完成!")
print("=" * 60)
