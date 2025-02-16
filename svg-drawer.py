import sys
import random
import svgwrite

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QPoint

############################
# Algorithm-related globals
############################

WIDTH = 600
HEIGHT = 800
STEP_SIZE = 10

# We'll store all occupied coordinates in this global set
occupied = set()

def in_bounds(x, y):
    """Return True if (x,y) is inside our 0..WIDTH x 0..HEIGHT area."""
    return (0 <= x <= WIDTH) and (0 <= y <= HEIGHT)

def try_move(x, y, dx, dy):
    """
    Attempt one move from (x,y) by (dx,dy).
    Return (nx, ny) if valid and not occupied, else None.
    """
    nx, ny = x + dx, y + dy
    if not in_bounds(nx, ny):
        return None
    if (nx, ny) in occupied:
        return None
    return (nx, ny)

def systematic_move(x, y, primary_direction, fallback_directions):
    """
    Try the primary direction. If blocked, systematically try each fallback in order.
    Return (nx, ny) if successful, else None.
    """
    # 1) Try primary
    attempted = try_move(x, y, primary_direction[0], primary_direction[1])
    if attempted is not None:
        return attempted
    
    # 2) If that fails, try fallback directions in order
    for (fx, fy) in fallback_directions:
        attempted = try_move(x, y, fx, fy)
        if attempted is not None:
            return attempted
    
    # None worked
    return None

def occupy_segment(x1, y1, x2, y2):
    """Mark the segment from (x1,y1) to (x2,y2) as occupied."""
    occupied.add((x1, y1))
    occupied.add((x2, y2))

class Line:
    """
    Represents a line being drawn. It has a path of points
    and logic to do diagonal/orth steps, possibly branching.
    """
    def __init__(self, start_x, start_y, max_steps, allow_branch=True):
        self.path = [(start_x, start_y)]  # list of (x,y)
        occupy_segment(start_x, start_y, start_x, start_y)

        self.x = start_x
        self.y = start_y
        
        self.steps_taken = 0
        self.max_steps = max_steps
        
        # For the first 10 steps, we do not allow special moves
        self.forbid_special_until = 10
        
        # Branch / orth usage flags
        self.used_orth = False      # once we do an orth block, no more
        self.used_branch = False    # once we branch, no more
        self.allow_branch = allow_branch  # can we branch at all?

        self.active = True

    def current_pos(self):
        return (self.x, self.y)

    def add_point(self, nx, ny):
        """Advance to (nx, ny), occupying it."""
        occupy_segment(self.x, self.y, nx, ny)
        self.x, self.y = nx, ny
        self.path.append((nx, ny))
        self.steps_taken += 1

    def can_continue(self):
        """Check if we can still take more steps."""
        return (self.steps_taken < self.max_steps) and self.active

    def step_diagonal_with_systematic_fallback(self):
        """
        We want to move (STEP_SIZE,STEP_SIZE) primarily.
        If blocked, systematically try (STEP_SIZE,0) then (0,STEP_SIZE).
        """
        move = systematic_move(self.x, self.y,
                               (STEP_SIZE, STEP_SIZE),
                               [(STEP_SIZE, 0), (0, STEP_SIZE)])
        if move is None:
            # all blocked -> stop
            self.active = False
            return
        nx, ny = move
        self.add_point(nx, ny)

    def block_of_5_orth(self):
        """
        Do 5 orth steps in either (5,0) or (0,5), with fallback if blocked.
        """
        # 1) pick primary direction at random
        if random.random() < 0.5:
            primary = (STEP_SIZE, 0)
            alternate = (0, STEP_SIZE)
        else:
            primary = (0, STEP_SIZE)
            alternate = (STEP_SIZE, 0)

        # 2) For the first step, if primary is blocked, try alternate
        first_move = systematic_move(self.x, self.y, primary, [alternate])
        if first_move is None:
            self.active = False
            return
        nx, ny = first_move
        self.add_point(nx, ny)

        # figure out which direction we actually used
        # we can deduce it by checking the difference
        dx = nx - self.x
        dy = ny - self.y
        # but we already updated self.x,self.y to nx,ny
        # simpler is: if first_move == None or not, but we are past that point,
        # so let's do it directly:
        if dx == 0:
            chosen_dir = (0, STEP_SIZE)
        else:
            chosen_dir = (STEP_SIZE, 0)

        # 3) Do 4 more steps in the chosen direction with fallback
        for _ in range(4):
            if not self.can_continue():
                break
            # systematically try chosen_dir or the other orth direction
            if chosen_dir == primary:
                fallback2 = [alternate]
            else:
                fallback2 = [primary]

            move2 = systematic_move(self.x, self.y, chosen_dir, fallback2)
            if move2 is None:
                self.active = False
                break
            nx2, ny2 = move2
            self.add_point(nx2, ny2)

    def do_forced_5_orth_branch_start(self):
        """
        For a branch line, forcibly do 5 orth steps at the start.
        """
        self.block_of_5_orth()

    def step(self):
        """
        Take one step, respecting special rules for first 10 steps.
        Possibly do diagonal, an orth block, or branch.
        """
        if not self.can_continue():
            return

        # If we are still in the first-10-step zone, do diagonal only:
        if self.steps_taken < self.forbid_special_until:
            self.step_diagonal_with_systematic_fallback()
            return

        # Past the first 10 steps, we can do branch / orth / diagonal
        # If we've already used them or we can't branch, just do diagonal
        if self.used_branch or self.used_orth or (not self.allow_branch):
            self.step_diagonal_with_systematic_fallback()
            return
        
        # Otherwise, pick a random event
        r = random.random()
        if r < 0.1:
            print("Branching!")
            # Try to branch (only if enough steps remain)
            leftover = self.max_steps - self.steps_taken
            if leftover >= 10:
                # We end this line, mark it branched
                self.used_branch = True
                self.active = False
            else:
                self.step_diagonal_with_systematic_fallback()
            return
        elif r < 0.05:
            print("Orthing!")
            # Orth block
            self.used_orth = True
            self.block_of_5_orth()
        else:
            # Diagonal
            self.step_diagonal_with_systematic_fallback()

def create_branch_line(parent_line):
    """
    Create a branch line from the parent's current position.
    The new line gets leftover + 5 steps, starts with 5 forced orth steps.
    """
    start_x, start_y = parent_line.current_pos()
    leftover = parent_line.max_steps - parent_line.steps_taken
    max_steps = leftover + 5
    if max_steps <= 0:
        return None

    branch_line = Line(start_x, start_y, max_steps, allow_branch=False)
    branch_line.do_forced_5_orth_branch_start()
    return branch_line

def create_svg(lines):
    """Build an SVG from all lines, with circles at the end-points."""
    dwg = svgwrite.Drawing("output.svg", size=(WIDTH, HEIGHT))
    dwg.add(dwg.rect(insert=(0,0), size=(WIDTH,HEIGHT), fill="white"))

    for ln in lines:
        pts = ln.path
        if len(pts) < 2:
            if len(pts) == 1:
                (ex, ey) = pts[0]
                dwg.add(dwg.circle(center=(ex,ey), r=5,
                                   fill="none", stroke="black", stroke_width=1))
            continue

        # Draw polyline
        dwg.add(dwg.polyline(points=pts,
                             fill="none",
                             stroke="black",
                             stroke_width=2))

        # Circle at the end
        (ex, ey) = pts[-1]
        dwg.add(dwg.circle(center=(ex, ey), r=5,
                           fill="none", stroke="black", stroke_width=1))

    return dwg


############################
# PyQt Drawing Widget
############################

class LineDrawingWidget(QWidget):
    """
    A QWidget that knows how to draw multiple lines and circles at their endpoints.
    We simply store references to all the lines, and in paintEvent we draw them.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines = []  # a list of Line objects

    def set_lines(self, lines):
        """Replace the entire list of lines to be drawn."""
        self.lines = lines
        self.update()  # trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)

        for line_obj in self.lines:
            pts = line_obj.path
            # draw the segments
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i+1]
                painter.drawLine(x1, y1, x2, y2)

            # draw a circle at the end
            if len(pts) > 0:
                x_end, y_end = pts[-1]
                painter.drawEllipse(QPoint(x_end, y_end), 5, 5)


############################
# Main Window
############################

class CircuitBoardWindow(QMainWindow):
    """
    QMainWindow that runs the multi-line generation algorithm in small steps
    and shows the lines being drawn in real time using a QTimer.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Board Art - Live Preview")
        self.setGeometry(100, 100, WIDTH, HEIGHT)

        # Our custom drawing widget
        self.drawing_widget = LineDrawingWidget(self)
        self.setCentralWidget(self.drawing_widget)

        # Timer to step the generation
        self.timer = QTimer()
        self.timer.timeout.connect(self.generate_step)

        # Setup initial generation state
        self.reset_generation()  # so we start with a random seed & lines
    
    def reset_generation(self):
        """
        Clear everything and start generation from scratch with a new random seed.
        """
        self.timer.stop()

        global occupied
        occupied = set()  # reset the global set

        self.all_lines = []

        # new random seed
        self.seed = random.randint(0, 1000000)
        random.seed(self.seed)
        print("New Seed:", self.seed)

        # create main line
        self.main_line = Line(0, 0, max_steps=50, allow_branch=False)
        self.all_lines.append(self.main_line)

        # extra lines logic
        self.num_extra_lines = 15
        self.offset_count = 1
        self.extra_lines_created = 0
        self.current_extra_line = None

        self.generation_finished = False

        # clear the drawing widget
        self.drawing_widget.set_lines(self.all_lines)

        # restart the timer
        self.timer.start(20)

    def generate_step(self):
        """
        Called periodically by QTimer. We do a small piece of the line-generation,
        then update the drawing.
        """
        if self.generation_finished:
            return  # already done

        # 1) If the main line can still continue, step it
        if self.main_line.can_continue():
            self.main_line.step()
            # Check if it just branched:
            if self.main_line.used_branch and not self.main_line.active:
                # create the branch line
                branch_line = create_branch_line(self.main_line)
                if branch_line:
                    self.all_lines.append(branch_line)
                    # run that branch line immediately to completion (step by step)
                    # or you can also do partial stepping for animation:
                    while branch_line.can_continue():
                        branch_line.step()
            # done stepping main line (for this timer tick)

        else:
            # The main line is done (or never started).
            # Start / continue generating extra lines with offsets
            if self.current_extra_line and self.current_extra_line.can_continue():
                # step the current extra line
                self.current_extra_line.step()
                # check for branching
                if self.current_extra_line.used_branch and not self.current_extra_line.active:
                    branch_line = create_branch_line(self.current_extra_line)
                    if branch_line:
                        self.all_lines.append(branch_line)
                        while branch_line.can_continue():
                            branch_line.step()
            else:
                # If the current extra line is finished (or None), create the next one
                if self.extra_lines_created < self.num_extra_lines:
                    # compute offset
                    offset_val = 5 * self.offset_count
                    if offset_val % 10 != 0:
                        offset_val += 5
                    self.offset_count += 1
                    if self.extra_lines_created % 2 == 0:
                        start_x, start_y = (0, offset_val)
                    else:
                        start_x, start_y = (offset_val, 0)

                    # let it match the main line's length minus 5
                    main_length = self.main_line.steps_taken
                    max_steps = max(1, main_length - (random.randrange(2 * self.extra_lines_created, 2 * self.extra_lines_created + 4)))

                    line_obj = Line(start_x, start_y, max_steps, allow_branch=True)
                    self.all_lines.append(line_obj)
                    self.current_extra_line = line_obj
                    self.extra_lines_created += 1
                else:
                    # No more extra lines to create.
                    # If we have a current_extra_line that can't continue, we're done.
                    if not (self.current_extra_line and self.current_extra_line.can_continue()):
                        # All done
                        self.finish_generation()

        # Update the widget so the user sees the new lines
        self.drawing_widget.set_lines(self.all_lines)

    def finish_generation(self):
        """We are done generating everything; stop the timer and save SVG."""
        self.generation_finished = True
        self.timer.stop()

        # Create and save the SVG
        svg = create_svg(self.all_lines)
        svg.save()
        print("SVG saved as output.svg")
        print("All generation finished.")
    
    def keyPressEvent(self, event):
        """
        Listen for spacebar press. If pressed, reset generation with a new seed.
        """
        if event.key() == Qt.Key_Space:
            self.reset_generation()
        else:
            # pass it to the parent class in case there are other shortcuts
            super().keyPressEvent(event)

############################
# main() to run it
############################

def main():
    app = QApplication(sys.argv)
    window = CircuitBoardWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()