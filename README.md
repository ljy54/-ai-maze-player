# 🧠 AI 迷宫玩家

算法课设项目 — 迷宫路径规划与 Boss 战斗优化。

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 一键启动
python run.py
```

浏览器自动打开 `http://localhost:8000`，按 `Ctrl+C` 停止。

## 项目结构

```
ai-maze-player/
├── run.py              # 一键启动脚本
├── requirements.txt    # Python 依赖
├── docs/               # 文档
│   ├── 任务书.pdf
│   └── 输入格式说明.md
├── data/               # 测试数据
│   └── maze_15_15.json
├── tests/              # 测试
└── app/                # 应用源码
    ├── main.py         # FastAPI 入口
    ├── routes/         # API 路由
    ├── services/       # AI 算法引擎
    ├── models/         # 数据模型
    └── static/         # 前端页面
```

## 任务说明

| 任务 | 算法 | 视野 | 评价指标 |
|------|------|------|----------|
| 任务一 | 贪心实时资源拾取 | 3×3 九宫格 | 平均拾取资源价值 |
| 任务二 | 九宫格视野贪心最优路径 + 记忆 | 3×3 九宫格 | 资源获取/路径步数比值最大 |

## 输入格式

支持两种 JSON 格式：

### 标准 maze 格式
```json
{"maze": [[...]], "B": [...], "PlayerSkills": [[...]], "minRouds": 20, "CoinConsumption": 5}
```

### case-maze 的 grid 格式
```json
{"case_id": 1, "grid": [["G",".","."],["G","P","G"],["G","T","."]]}
```
- `P` = 起点，`G` = 金币(+50)，`T` = 陷阱(-30)，`.` = 空地，`E` = 出口(可选)
- 任务二不考虑出口，九宫格内无资源时自动停止

## 技术栈

- **后端**：Python + FastAPI + Uvicorn
- **前端**：原生 HTML/CSS/JS（单页面应用）
- **算法**：贪心决策、BFS 最短路径、记忆化搜索、状态压缩 DP（Boss战）
