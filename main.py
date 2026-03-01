import pygame
import random
import math
from queue import PriorityQueue
import time
import threading

pygame.init()

BG_COLOR       = "#1e1e2e"
WALL_COLOR     = "#b0b0b0"
EXPLORED_COLOR = "#f38ba8"
START_COLOR    = "#fde047"
GOAL_COLOR     = "#22c55e"
PATH_COLOR     = "#a855f7"
GRID_COLOR     = "#525252"
FLASH_COLOR    = "#ffffff"

ALGORITHM = "A_STAR"
HEURISTIC = "MANHATTAN"


class Node:
    def __init__(self, row, col, width, total_rows):
        self.row        = row
        self.col        = col
        self.x          = row * width
        self.y          = col * width
        self.color      = BG_COLOR
        self.neighbors  = []
        self.width      = width
        self.total_rows = total_rows

    def get_pos(self):      return self.row, self.col
    def is_barrier(self):   return self.color == WALL_COLOR
    def is_start(self):     return self.color == START_COLOR
    def is_goal(self):      return self.color == GOAL_COLOR
    def reset(self):        self.color = BG_COLOR
    def make_start(self):   self.color = START_COLOR
    def make_closed(self):  self.color = EXPLORED_COLOR
    def make_open(self):    self.color = EXPLORED_COLOR
    def make_barrier(self): self.color = WALL_COLOR
    def make_goal(self):    self.color = GOAL_COLOR
    def make_flash(self):   self.color = FLASH_COLOR

    def make_path(self):
        if not self.is_start() and not self.is_goal():
            self.color = PATH_COLOR

    def draw(self, win):
        pygame.draw.rect(win, self.color, (self.x, self.y, self.width, self.width))

    def update_neighbors(self, grid):
        self.neighbors = []
        if self.row < self.total_rows - 1 and not grid[self.row+1][self.col].is_barrier():
            self.neighbors.append(grid[self.row+1][self.col])
        if self.row > 0 and not grid[self.row-1][self.col].is_barrier():
            self.neighbors.append(grid[self.row-1][self.col])
        if self.col < self.total_rows - 1 and not grid[self.row][self.col+1].is_barrier():
            self.neighbors.append(grid[self.row][self.col+1])
        if self.col > 0 and not grid[self.row][self.col-1].is_barrier():
            self.neighbors.append(grid[self.row][self.col-1])


def heuristic(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    if HEURISTIC == "MANHATTAN":  return abs(x1-x2) + abs(y1-y2)
    if HEURISTIC == "EUCLIDEAN":  return math.sqrt((x1-x2)**2 + (y1-y2)**2)
    if HEURISTIC == "DIAGONAL":   return max(abs(x1-x2), abs(y1-y2))
    return abs(x1-x2) + abs(y1-y2)


def make_grid(rows, width):
    gap = width // rows
    return [[Node(i, j, gap, rows) for j in range(rows)] for i in range(rows)]


def draw_grid_lines(win, rows, width):
    gap = width // rows
    for i in range(rows):
        pygame.draw.line(win, GRID_COLOR, (0, i*gap), (width, i*gap))
        for j in range(rows):
            pygame.draw.line(win, GRID_COLOR, (j*gap, 0), (j*gap, width))


def draw(win, grid, rows, width, metrics, status):
    win.fill(BG_COLOR)
    for row in grid:
        for node in row:
            node.draw(win)
    draw_grid_lines(win, rows, width)

    font = pygame.font.Font(None, 20)
    y = 10
    win.blit(font.render(f"Algo: {ALGORITHM}",      True, WALL_COLOR), (width+10, y)); y += 20
    win.blit(font.render(f"Heuristic: {HEURISTIC}", True, WALL_COLOR), (width+10, y))

    y = 60
    for key, val in metrics.items():
        win.blit(font.render(f"{key}: {val}", True, WALL_COLOR), (width+10, y)); y += 20

    win.blit(font.render(f"Status: {status}", True, WALL_COLOR), (width+10, y+10))

    y += 45
    for line in ["Controls:", "SPACE: Find path", "R: Reset"]:
        win.blit(font.render(line, True, WALL_COLOR), (width+10, y)); y += 18

    pygame.display.update()


def instant_scatter(grid, rows, start, goal):
    """Instantly place scattered walls with no animation."""
    sp, gp = start.get_pos(), goal.get_pos()
    for i in range(rows):
        for j in range(rows):
            node = grid[i][j]
            if (i, j) == sp or (i, j) == gp:
                continue
            if random.random() < 0.28:
                node.make_barrier()
            else:
                node.reset()
    start.make_start()
    goal.make_goal()


def spawn_dynamic_walls(grid, rows, start, goal, stop_event, interval=0.3):
    """Background thread: randomly spawns 1-3 new walls while algo runs."""
    while not stop_event.is_set():
        time.sleep(interval)
        if stop_event.is_set():
            break
        sp, gp = start.get_pos(), goal.get_pos()
        candidates = [
            grid[i][j]
            for i in range(rows) for j in range(rows)
            if grid[i][j].color == BG_COLOR
            and (i,j) != sp and (i,j) != gp
        ]
        if not candidates:
            continue
        chosen = random.sample(candidates, min(random.randint(1, 3), len(candidates)))
        for node in chosen:
            node.make_flash()
        time.sleep(0.06)
        for node in chosen:
            if node.color == FLASH_COLOR:
                node.make_barrier()
                node.update_neighbors(grid)
                for nb in node.neighbors:
                    nb.update_neighbors(grid)


def clear_search_colors(grid):
    for row in grid:
        for node in row:
            if node.color in (EXPLORED_COLOR, PATH_COLOR):
                node.reset()


def reconstruct_path(came_from, current, draw_func, goal):
    path_length = 0
    while current in came_from:
        current = came_from[current]
        if not current.is_start() and current != goal:
            current.make_path()
        path_length += 1
        draw_func()
    return path_length


def a_star_search(draw_func, grid, start, goal):
    count = 0
    open_set = PriorityQueue()
    open_set.put((0, count, start))
    came_from = {}
    g_score = {node: float("inf") for row in grid for node in row}
    g_score[start] = 0
    f_score = {node: float("inf") for row in grid for node in row}
    f_score[start] = heuristic(start.get_pos(), goal.get_pos())
    open_set_hash = {start}
    nodes_visited = 0

    while not open_set.empty():
        current = open_set.get()[2]
        open_set_hash.discard(current)

        if current == goal:
            path_length = reconstruct_path(came_from, goal, draw_func, goal)
            goal.make_goal()
            return nodes_visited, path_length, True

        for neighbor in current.neighbors:
            if neighbor.is_barrier():
                continue
            temp_g = g_score[current] + 1
            if temp_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor]   = temp_g
                f_score[neighbor]   = temp_g + heuristic(neighbor.get_pos(), goal.get_pos())
                if neighbor not in open_set_hash:
                    count += 1; nodes_visited += 1
                    open_set.put((f_score[neighbor], count, neighbor))
                    open_set_hash.add(neighbor)
                    if neighbor != goal:
                        neighbor.make_open()
        draw_func()
        if current != start and current != goal:
            current.make_closed()

    return nodes_visited, None, False


def greedy_search(draw_func, grid, start, goal):
    count = 0
    open_set = PriorityQueue()
    open_set.put((0, count, start))
    came_from     = {}
    open_set_hash = {start}
    nodes_visited = 0

    while not open_set.empty():
        current = open_set.get()[2]
        open_set_hash.discard(current)

        if current == goal:
            path_length = reconstruct_path(came_from, goal, draw_func, goal)
            goal.make_goal()
            return nodes_visited, path_length, True

        for neighbor in current.neighbors:
            if neighbor.is_barrier():
                continue
            if neighbor not in came_from and neighbor != start:
                came_from[neighbor] = current
                count += 1; nodes_visited += 1
                open_set.put((heuristic(neighbor.get_pos(), goal.get_pos()), count, neighbor))
                open_set_hash.add(neighbor)
                if neighbor != goal:
                    neighbor.make_open()
        draw_func()
        if current != start and current != goal:
            current.make_closed()

    return nodes_visited, None, False


def main(win, width):
    ROWS = 15
    grid = make_grid(ROWS, width)

    start = grid[0][0]
    goal  = grid[ROWS-1][ROWS-1]
    start.make_start()
    goal.make_goal()

    metrics    = {"Nodes Visited": 0, "Path Cost": 0, "Time (ms)": 0}
    path_found = False
    status     = "Ready"

    instant_scatter(grid, ROWS, start, goal)

    run = True
    while run:
        draw(win, grid, ROWS, width, metrics, status)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

            if event.type == pygame.KEYDOWN:

                # SPACE — run pathfinding with live wall spawning
                if event.key == pygame.K_SPACE and not path_found:
                    for row in grid:
                        for node in row:
                            node.update_neighbors(grid)
                    clear_search_colors(grid)
                    start.make_start()
                    goal.make_goal()
                    status = "Searching... (walls spawning!)"
                    draw(win, grid, ROWS, width, metrics, status)

                    stop_event  = threading.Event()
                    wall_thread = threading.Thread(
                        target=spawn_dynamic_walls,
                        args=(grid, ROWS, start, goal, stop_event, 0.3),
                        daemon=True
                    )
                    wall_thread.start()

                    t0 = time.time()
                    if ALGORITHM == "A_STAR":
                        nv, pc, found = a_star_search(
                            lambda: draw(win, grid, ROWS, width, metrics, status),
                            grid, start, goal
                        )
                    else:
                        nv, pc, found = greedy_search(
                            lambda: draw(win, grid, ROWS, width, metrics, status),
                            grid, start, goal
                        )

                    stop_event.set()
                    wall_thread.join(timeout=1)

                    elapsed = (time.time() - t0) * 1000
                    if found:
                        metrics    = {"Nodes Visited": nv, "Path Cost": pc,
                                      "Time (ms)": round(elapsed, 2)}
                        status     = "Path Found!"
                        path_found = True
                    else:
                        status = "No Path Found!"

                # R — reset with animated scatter
                elif event.key == pygame.K_r:
                    grid  = make_grid(ROWS, width)
                    start = grid[0][0]
                    goal  = grid[ROWS-1][ROWS-1]
                    start.make_start()
                    goal.make_goal()
                    path_found = False
                    metrics    = {"Nodes Visited": 0, "Path Cost": 0, "Time (ms)": 0}
                    status     = "Ready"
                    instant_scatter(grid, ROWS, start, goal)

    pygame.quit()


if __name__ == "__main__":
    GRID_SIZE = 600
    WIN       = pygame.display.set_mode((GRID_SIZE+200, GRID_SIZE))
    pygame.display.set_caption(f"Pathfinding - {ALGORITHM} with {HEURISTIC}")
    main(WIN, GRID_SIZE)