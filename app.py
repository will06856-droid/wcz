import heapq
import os
import socket
import time
import uuid
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
INSTANCE_ID = os.getenv("INSTANCE_ID", "unknown")
MAX_GRID_SIZE = 40
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _validate_point(value, name, rows, columns):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(coordinate) is not int for coordinate in value)
    ):
        raise ValueError(f"{name}必须是包含两个整数的数组")
    row, column = value
    if not (0 <= row < rows and 0 <= column < columns):
        raise ValueError(f"{name}越界")
    return (row, column)


def _validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("请求体必须是JSON对象")

    grid = payload.get("grid")
    if not isinstance(grid, list) or not grid:
        raise ValueError("grid必须是非空二维数组")
    if len(grid) > MAX_GRID_SIZE:
        raise ValueError("地图行数不能超过40")

    if any(not isinstance(row, list) or not row for row in grid):
        raise ValueError("grid的每一行都必须是非空数组")

    columns = len(grid[0])
    if columns > MAX_GRID_SIZE:
        raise ValueError("地图列数不能超过40")
    if any(len(row) != columns for row in grid):
        raise ValueError("grid的每一行长度必须一致")

    for row in grid:
        for cell in row:
            if type(cell) is not int or cell not in (0, 1):
                raise ValueError("grid中的单元格只能是0或1")

    rows = len(grid)
    start = _validate_point(payload.get("start"), "start", rows, columns)
    end = _validate_point(payload.get("end"), "end", rows, columns)

    if grid[start[0]][start[1]] == 1:
        raise ValueError("起点不能位于障碍物")
    if grid[end[0]][end[1]] == 1:
        raise ValueError("终点不能位于障碍物")

    algorithm = payload.get("algorithm")
    if algorithm not in {"astar", "bfs"}:
        raise ValueError("algorithm只能是astar或bfs")

    return grid, start, end, algorithm


def _neighbors(position, grid):
    row, column = position
    rows = len(grid)
    columns = len(grid[0])
    for row_delta, column_delta in DIRECTIONS:
        next_row = row + row_delta
        next_column = column + column_delta
        if (
            0 <= next_row < rows
            and 0 <= next_column < columns
            and grid[next_row][next_column] == 0
        ):
            yield (next_row, next_column)


def _manhattan(first, second):
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def _restore_path(came_from, end):
    path = []
    current = end
    while current is not None:
        path.append(current)
        current = came_from.get(current)
    path.reverse()
    return [list(position) for position in path]


def _solve_astar(grid, start, end):
    frontier = [(_manhattan(start, end), 0, start)]
    came_from = {}
    costs = {start: 0}
    visited = []
    visited_set = set()

    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        if current in visited_set or current_cost != costs.get(current):
            continue

        visited_set.add(current)
        visited.append(list(current))
        if current == end:
            return _restore_path(came_from, end), visited

        for neighbor in _neighbors(current, grid):
            next_cost = current_cost + 1
            if next_cost < costs.get(neighbor, float("inf")):
                costs[neighbor] = next_cost
                came_from[neighbor] = current
                priority = next_cost + _manhattan(neighbor, end)
                heapq.heappush(frontier, (priority, next_cost, neighbor))

    return [], visited


def _solve_bfs(grid, start, end):
    frontier = deque([start])
    came_from = {start: None}
    visited = []

    while frontier:
        current = frontier.popleft()
        visited.append(list(current))
        if current == end:
            return _restore_path(came_from, end), visited

        for neighbor in _neighbors(current, grid):
            if neighbor not in came_from:
                came_from[neighbor] = current
                frontier.append(neighbor)

    return [], visited


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    server_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return jsonify(
        status="ok",
        message="项目部署成功",
        version="1.0",
        instance_id=INSTANCE_ID,
        container_hostname=socket.gethostname(),
        request_id=str(uuid.uuid4()),
        server_time=server_time,
    )


@app.post("/api/solve")
def solve():
    payload = request.get_json(silent=True)
    try:
        grid, start, end, algorithm = _validate_payload(payload)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    started_at = time.perf_counter()
    try:
        if algorithm == "astar":
            path, visited = _solve_astar(grid, start, end)
        else:
            path, visited = _solve_bfs(grid, start, end)
    except Exception:
        app.logger.exception("迷宫寻路计算失败")
        return jsonify(error="服务器内部错误"), 500

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    success = bool(path)
    response = {
        "success": success,
        "algorithm": algorithm,
        "path": path,
        "visited": visited,
        "path_length": max(len(path) - 1, 0) if success else 0,
        "visited_count": len(visited),
        "elapsed_ms": elapsed_ms,
    }
    if not success:
        response["message"] = "未找到可行路径"
    return jsonify(response)


@app.get("/health")
def health():
    return jsonify(status="healthy")


@app.errorhandler(500)
def handle_internal_error(error):
    app.logger.error("未处理的服务器错误: %s", error)
    return jsonify(error="服务器内部错误"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
