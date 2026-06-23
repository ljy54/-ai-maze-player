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


@router.get("/mazes")
async def list_mazes():
    """返回 data/ 目录下所有迷宫文件列表"""
    mazes = []
    if os.path.isdir(_DATA_DIR):
        for fname in sorted(os.listdir(_DATA_DIR)):
            if fname.endswith(".json"):
                fpath = os.path.join(_DATA_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    rows = len(data.get("maze", []))
                    cols = len(data["maze"][0]) if rows > 0 else 0
                    mazes.append({
                        "name": fname.replace(".json", ""),
                        "file": fname,
                        "size": f"{rows}×{cols}",
                        "goldCount": sum(1 for r in data["maze"] for c in r if c == "G"),
                        "trapCount": sum(1 for r in data["maze"] for c in r if c == "T"),
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
    """统一解析请求参数，兼容拼写错误"""
    maze = data["maze"]
    bosses = data["B"]
    skills = data["PlayerSkills"]
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
        message=f"全局最优完成 | 评价指标: {result['evaluation']['primaryMetric']}",
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
