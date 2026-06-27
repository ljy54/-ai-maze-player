import os
import json
from fastapi import APIRouter, HTTPException
from collections import deque
from ..models.schemas import SolveResponse
from ..services.ai_engine import AIEngine
from ..services.maze_parser import MazeParser

router = APIRouter()

# data 目录路径
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _convert_grid_to_maze(grid: list) -> list:
    """将 case-maze 的 grid 格式转换为内部 maze 格式。
    P → S（起点），G → G（金币），T → T（陷阱），E → E（出口），. → ' '（空地）。
    """
    return [
        [
            'S' if ch == 'P' else
            ' ' if ch == '.' else
            ch
            for ch in row
        ]
        for row in grid
    ]


@router.get("/mazes")
async def list_mazes():
    """返回 data/ 目录下所有迷宫文件列表，兼容 maze 和 grid 两种格式"""
    mazes = []
    if os.path.isdir(_DATA_DIR):
        for fname in sorted(os.listdir(_DATA_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(_DATA_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 兼容两种格式
                    if "grid" in data:
                        # case-maze 的 grid 格式
                        grid = data["grid"]
                        rows = len(grid)
                        cols = len(grid[0]) if rows > 0 else 0
                        gold_count = sum(1 for r in grid for c in r if c == "G")
                        trap_count = sum(1 for r in grid for c in r if c == "T")
                    elif "maze" in data:
                        rows = len(data["maze"])
                        cols = len(data["maze"][0]) if rows > 0 else 0
                        gold_count = sum(1 for r in data["maze"] for c in r if c == "G")
                        trap_count = sum(1 for r in data["maze"] for c in r if c == "T")
                    else:
                        continue  # 不认识的格式，跳过

                    mazes.append({
                        "name": fname.replace(".json", ""),
                        "file": fname,
                        "size": f"{rows}×{cols}",
                        "goldCount": gold_count,
                        "trapCount": trap_count,
                    })
                except Exception:
                    pass
    return {"mazes": mazes}


@router.get("/data/{filename}")
async def get_maze_file(filename: str):
    """获取单个迷宫 JSON 文件"""
    fpath = os.path.join(_DATA_DIR, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_request(data: dict) -> dict:
    """统一解析请求参数，兼容 maze 格式和 case-maze 的 grid 格式"""
    # 检测 grid 格式（case-maze系列）
    if "grid" in data:
        maze = _convert_grid_to_maze(data["grid"])
        return {
            "maze": maze,
            "boss_hps": data.get("B", []),
            "player_skills": data.get("PlayerSkills", []),
            "min_rounds": data.get("minRouds", data.get("minRounds", 20)),
            "coin_consumption": data.get("CoinConsumption", data.get("coinConsumption", 5)),
            "vision_range": 1,
        }

    # 标准 maze 格式
    maze = data["maze"]
    bosses = data.get("B", [])
    skills = data.get("PlayerSkills", [])
    min_rounds = data.get("minRouds", data.get("minRounds", 20))
    coin_consumption = data.get("CoinConsumption", data.get("coinConsumption", 5))
    # 任务一视野强制 3×3 九宫格（半径1），忽略前端传值
    vision = 1
    return {
        "maze": maze,
        "boss_hps": bosses,
        "player_skills": skills,
        "min_rounds": min_rounds,
        "coin_consumption": coin_consumption,
        "vision_range": vision,
    }


@router.post("/solve/greedy", response_model=SolveResponse)
async def solve_greedy(data: dict):
    """
    任务一：贪心实时资源拾取
    评价指标：平均拾取资源价值
    """
    try:
        args = _parse_request(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"输入格式错误: {str(e)}")

    engine = AIEngine()
    result = engine.solve_greedy(
        maze=args["maze"],
        boss_hps=args["boss_hps"],
        player_skills=args["player_skills"],
        min_rounds=args["min_rounds"],
        coin_consumption=args["coin_consumption"],
        vision_range=args["vision_range"],
    )

    return SolveResponse(
        success=True,
        path=result["path"],
        skillSequence=result["skillSequence"],
        stats=result["stats"],
        stepScores=result.get("stepScores", []),
        message=f"贪心策略完成 | 评价指标: {result['evaluation']['primaryMetric']}",
    )


@router.post("/solve/global", response_model=SolveResponse)
async def solve_global(data: dict):
    """
    任务二：全局最优探索
    评价指标：抵终点时剩余资源价值
    """
    try:
        args = _parse_request(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"输入格式错误: {str(e)}")

    engine = AIEngine()
    result = engine.solve_global(
        maze=args["maze"],
        boss_hps=args["boss_hps"],
        player_skills=args["player_skills"],
        min_rounds=args["min_rounds"],
        coin_consumption=args["coin_consumption"],
    )

    return SolveResponse(
        success=True,
        path=result["path"],
        skillSequence=result["skillSequence"],
        stats=result["stats"],
        stepScores=result.get("stepScores", []),
        message=f"局部最优完成 | 评价指标: {result['evaluation']['primaryMetric']}",
    )


@router.post("/compare")
async def compare_both(data: dict):
    """
    同时运行两个AI玩家，对比结果
    """
    try:
        args = _parse_request(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"输入格式错误: {str(e)}")

    engine = AIEngine()
    greedy = engine.solve_greedy(
        maze=args["maze"],
        boss_hps=args["boss_hps"],
        player_skills=args["player_skills"],
        min_rounds=args["min_rounds"],
        coin_consumption=args["coin_consumption"],
        vision_range=args["vision_range"],
    )
    global_ = engine.solve_global(
        maze=args["maze"],
        boss_hps=args["boss_hps"],
        player_skills=args["player_skills"],
        min_rounds=args["min_rounds"],
        coin_consumption=args["coin_consumption"],
    )

    return {
        "success": True,
        "greedy": {
            "stats": greedy["stats"],
            "evaluation": greedy["evaluation"],
        },
        "global": {
            "stats": global_["stats"],
            "evaluation": global_["evaluation"],
        },
        "comparison": {
            "netCoinsDiff": global_["stats"]["netCoins"] - greedy["stats"]["netCoins"],
            "pathLengthDiff": global_["stats"]["pathLength"] - greedy["stats"]["pathLength"],
            "betterStrategy": "global" if global_["stats"]["netCoins"] > greedy["stats"]["netCoins"] else "greedy",
        },
    }
