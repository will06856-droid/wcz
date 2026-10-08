# A星迷宫寻路可视化系统

这是一个基于 Flask、Gunicorn、Docker Compose 和 Nginx 的迷宫寻路演示项目。页面提供 20×20 网格地图，支持手动编辑障碍物、随机迷宫、A星算法和广度优先搜索，并动态播放搜索过程和最终路径。

## 功能列表

- 设置起点和终点，默认分别位于左上角和右下角；
- 鼠标点击或拖动绘制、擦除障碍物；
- 随机生成约 20%～25% 障碍物；
- 选择 A星算法或广度优先搜索；
- 调节搜索动画速度；
- 查看已搜索节点、最终路径和寻路统计；
- 保留 /health、/api/status 和容器健康检查；
- 保留 app1、app2 双实例与 Nginx upstream 负载均衡。

## A星算法原理

A星算法使用优先队列，每次优先扩展估计总成本最小的节点：

`f(n) = g(n) + h(n)`

- g(n)：从起点走到当前节点的实际代价；
- h(n)：从当前节点到终点的估计代价；
- 每移动一格代价为 1；
- 只允许上下左右四个方向移动；
- 使用 heapq 实现优先队列；
- 使用曼哈顿距离作为启发函数：当前行与终点行的差的绝对值，加上当前列与终点列的差的绝对值。

在只能上下左右移动、每步代价相同的地图中，曼哈顿距离不会高估剩余成本，因此可以帮助 A星优先搜索更接近终点的区域，同时保持最短路径结果。

## A星和广度优先搜索的区别

广度优先搜索使用 collections.deque，按距离起点的层级逐圈搜索。在每一步代价相同的情况下，BFS 也能找到最短路径，但通常会访问更多无关节点。

A星使用曼哈顿距离引导搜索方向，通常访问节点更少；BFS 的逻辑更简单，不需要启发函数。页面中的搜索动画可以直观看到两种算法的访问范围差异。

## 项目架构

``text
浏览器
  ↓
Nginx:80（宿主机端口可通过 HTTP_PORT 配置）
  ↓
backend_pool（轮询）
  ├── app1:8000 → Flask / Gunicorn
  └── app2:8000 → Flask / Gunicorn
``

两个 Flask 实例共用同一个 Dockerfile，通过 INSTANCE_ID 区分。8000 端口只在 Compose 内部网络可见，Nginx 是唯一对外入口。

## API

### POST /api/solve

请求示例：

``json
{
  "grid": [
    [0, 0, 1],
    [1, 0, 0],
    [0, 0, 0]
  ],
  "start": [0, 0],
  "end": [2, 2],
  "algorithm": "astar"
}
``

grid 中 0 表示可通行，1 表示障碍；algorithm 只能是 astar 或 bfs。接口会校验非空二维数组、行长度、40×40 最大尺寸、起终点范围和障碍状态。

### GET /health

返回：

``json
{"status":"healthy"}
``

### GET /api/status

保留原有部署状态接口，用于查看实例 ID、容器主机名、请求 ID 和服务器时间。

## 本地启动

在 deploy-demo 目录执行：

``bash
python3 -m py_compile app.py
docker compose config
docker compose up -d --build
docker compose ps
``

浏览器访问：

http://127.0.0.1/

基础接口验证：

``bash
curl -i http://127.0.0.1/health
curl -i http://127.0.0.1/
``

测试有效迷宫：

``bash
curl -sS -X POST http://127.0.0.1/api/solve   -H 'Content-Type: application/json'   -d '{"grid":[[0,0,1],[1,0,0],[0,0,0]],"start":[0,0],"end":[2,2],"algorithm":"astar"}'
``

测试不可达地图：

``bash
curl -sS -X POST http://127.0.0.1/api/solve   -H 'Content-Type: application/json'   -d '{"grid":[[0,1,0],[1,1,1],[0,1,0]],"start":[0,0],"end":[2,2],"algorithm":"bfs"}'
``

## 查看日志和停止项目

``bash
docker compose logs --tail=100 app1 app2
docker compose logs --tail=100 nginx
docker compose logs -f
docker compose stop
docker compose down
``

不要使用会影响其他项目的全局 Docker 清理命令。

## 云服务器使用 10020 端口

本次只完成本地验证。未来部署到云服务器时，在服务器项目目录执行：

``bash
export HTTP_PORT=10020
docker compose config
docker compose up -d --build
docker compose ps
curl -i http://127.0.0.1:10020/health
``

浏览器访问：

http://服务器公网IP:10020/

云安全组和系统防火墙需要开放 TCP 22 和 10020，不需要开放 8000。

## 三分钟演示步骤

1. 打开 http://127.0.0.1/，确认默认起点是左上角、终点是右下角。
2. 点击“绘制障碍”，拖动鼠标画出一条简单障碍带。
3. 选择 A星算法，点击“开始寻路”，观察浅蓝色搜索节点和黄色最终路径。
4. 点击“清空地图”，选择广度优先搜索，再运行一次，对比搜索范围。
5. 点击“随机迷宫”，再次运行；如果没有路径，页面会显示明确提示。
6. 如需检查后端，查看 docker compose logs --tail=100 app1 app2。
