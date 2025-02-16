import sys
import random
import svgwrite

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QPoint

WIDTH = 600
HEIGHT = 800
STEP_SIZE = 10

occupied = set()

def in_bounds(x, y):
    return 0 <= x <= WIDTH and 0 <= y <= HEIGHT

def try_move(x, y, dx, dy):
    nx, ny = x + dx, y + dy
    if not in_bounds(nx, ny):
        return None
    if (nx, ny) in occupied:
        return None
    return (nx, ny)

def occupy_segment(x1, y1, x2, y2):
    occupied.add((x1, y1))
    occupied.add((x2, y2))

class Line:
    """
    A line that can:
      - move diagonally
      - do orth blocks
      - queue up "branch requests" without stopping the parent
    """
    def __init__(self, start_x, start_y, max_steps):
        self.path = [(start_x, start_y)]
        occupy_segment(start_x, start_y, start_x, start_y)

        self.x = start_x
        self.y = start_y
        self.steps_taken = 0
        self.max_steps = max_steps
        self.active = True

        # To block fancy moves for first 10 steps:
        self.forbid_special_until = 10

        # Each line can queue up multiple branch requests
        # (x, y, new_max_steps) in self.branch_requests
        self.branch_requests = []

        # Also allow only one orth block? (Your code had self.used_orth, etc.)
        self.used_orth = False

    def current_pos(self):
        return (self.x, self.y)

    def can_continue(self):
        return self.active and (self.steps_taken < self.max_steps)

    def add_point(self, nx, ny):
        occupy_segment(self.x, self.y, nx, ny)
        self.x, self.y = nx, ny
        self.path.append((nx, ny))
        self.steps_taken += 1

    def step_diagonal(self):
        """Tries (STEP_SIZE,STEP_SIZE). If blocked, stops."""
        moved = try_move(self.x, self.y, STEP_SIZE, STEP_SIZE)
        if moved is None:
            self.active = False
        else:
            nx, ny = moved
            self.add_point(nx, ny)

    def step_diagonal_with_fallback(self):
        """
        The original 'systematic_move' approach:
        prefer (STEP_SIZE, STEP_SIZE), fallback to (STEP_SIZE, 0) or (0, STEP_SIZE).
        """
        # If you want to keep the old fallback logic:
        # Just do your systematic_move(...) calls here.
        moved = try_move(self.x, self.y, STEP_SIZE, STEP_SIZE)
        if moved is not None:
            nx, ny = moved
            self.add_point(nx, ny)
        else:
            # fallback
            fallback_moves = [(STEP_SIZE, 0), (0, STEP_SIZE)]
            done = False
            for (dx, dy) in fallback_moves:
                moved2 = try_move(self.x, self.y, dx, dy)
                if moved2 is not None:
                    nx2, ny2 = moved2
                    self.add_point(nx2, ny2)
                    done = True
                    break
            if not done:
                self.active = False

    def block_of_5_orth(self):
        """Take 5 steps orth in some direction if possible."""
        # (same as your code, except we do not kill parent if blocked mid-way)
        if self.used_orth:
            # if you only want one orth per line, skip
            return

        # pick (dx, dy) randomly
        if random.random() < 0.5:
            primary = (STEP_SIZE, 0)
            fallback = (0, STEP_SIZE)
        else:
            primary = (0, STEP_SIZE)
            fallback = (STEP_SIZE, 0)

        steps_done = 0
        while steps_done < 5 and self.can_continue():
            moved = try_move(self.x, self.y, primary[0], primary[1])
            if moved is None:
                # fallback once
                moved2 = try_move(self.x, self.y, fallback[0], fallback[1])
                if moved2 is None:
                    # can't move -> done
                    self.active = False
                    break
                nx2, ny2 = moved2
                self.add_point(nx2, ny2)
            else:
                nx, ny = moved
                self.add_point(nx, ny)
            steps_done += 1

        self.used_orth = True  # if only one orth block is allowed

    def step(self):
        """One step of logic. Possibly queue branch requests, do orth, or diagonal."""
        if not self.can_continue():
            return

        # For first 10 steps, do diagonal only
        if self.steps_taken < self.forbid_special_until:
            self.step_diagonal_with_fallback()
            return

        # Past the first 10 steps, let's do a random event
        r = random.random()

        # Example: 10% chance to add a branch request
        if r < 0.1:
            leftover = self.max_steps - self.steps_taken
            if leftover >= 10:
                # Instead of stopping the line, just store a "branch request"
                print("Queuing a branch request at", (self.x, self.y))
                self.branch_requests.append((self.x, self.y, leftover + 5))
            else:
                # not enough steps left to do a new branch => do diagonal
                self.step_diagonal_with_fallback()
            return

        # 5% chance to do a 5-step orth block
        elif r < 0.15:
            self.block_of_5_orth()

        else:
            # diagonal
            self.step_diagonal_with_fallback()

########################################################
# The rest is mostly the same as your PyQt + generate loop
########################################################

def create_svg(lines):
    dwg = svgwrite.Drawing("output.svg", size=(WIDTH, HEIGHT))
    dwg.add(dwg.rect(insert=(0,0), size=(WIDTH,HEIGHT), fill="white"))

    for ln in lines:
        pts = ln.path
        if len(pts) < 2:
            if len(pts) == 1:
                ex, ey = pts[0]
                dwg.add(dwg.circle(center=(ex,ey), r=5,
                                   fill="none", stroke="black", stroke_width=1))
            continue

        dwg.add(dwg.polyline(points=pts,
                             fill="none",
                             stroke="black",
                             stroke_width=2))
        ex, ey = pts[-1]
        dwg.add(dwg.circle(center=(ex,ey), r=5,
                           fill="none", stroke="black", stroke_width=1))

    return dwg

from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint

class LineDrawingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines = []

    def set_lines(self, lines):
        self.lines = lines
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)

        for line_obj in self.lines:
            pts = line_obj.path
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i+1]
                painter.drawLine(x1, y1, x2, y2)
            # Optionally draw circle only if line_obj is done:
            if not line_obj.can_continue() and len(pts) > 0:
                x_end, y_end = pts[-1]
                painter.drawEllipse(QPoint(x_end, y_end), 5, 5)

class CircuitBoardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Board Art - Live Preview")
        self.setGeometry(100, 100, WIDTH, HEIGHT)

        self.drawing_widget = LineDrawingWidget(self)
        self.setCentralWidget(self.drawing_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.step_generation)

        self.reset_generation()

    def reset_generation(self):
        global occupied
        occupied = set()

        self.lines_stack = []   # We will store lines to step in LIFO order
        self.finished_lines = [] # Store lines once they are done

        # pick a random seed
        seed = random.randint(0, 999999)
        random.seed(seed)
        print("New seed:", seed)

        # create one main line, push it on stack
        main_line = Line(0, 0, max_steps=50)
        self.lines_stack.append(main_line)

        self.drawing_widget.set_lines(self.lines_stack)  # show it
        self.timer.start(50)

    def step_generation(self):
        if not self.lines_stack:
            # Nothing left to step => done
            self.timer.stop()
            self.finish_generation()
            return

        # Take the top line from the stack
        current_line = self.lines_stack[-1]

        # Step it once
        current_line.step()

        # If it's still going, fine. If it's done, pop it from the stack
        if not current_line.can_continue():
            self.lines_stack.pop()
            # Now create branch lines from it in reverse order
            while current_line.branch_requests:
                bx, by, bsteps = current_line.branch_requests.pop()
                branch_line = Line(bx, by, bsteps)
                self.lines_stack.append(branch_line)

            # Also store it in finished_lines
            self.finished_lines.append(current_line)

        # Update the drawing
        # lines currently on the stack + lines finished:
        all_lines = self.finished_lines + self.lines_stack
        self.drawing_widget.set_lines(all_lines)

    def finish_generation(self):
        # Everything done: build the final list of lines
        all_lines = self.finished_lines + self.lines_stack
        svg = create_svg(all_lines)
        svg.save()
        print("SVG saved as output.svg")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.timer.stop()
            self.reset_generation()
        else:
            super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    w = CircuitBoardWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
