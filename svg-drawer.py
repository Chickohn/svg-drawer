import random
import svgwrite

# Live preview
# import cairosvg
import tkinter as tk
from PIL import Image, ImageTk
from io import BytesIO


WIDTH = 600   # bounding box width
HEIGHT = 600  # bounding box height
STEP_SIZE = 5

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
    
    primary_direction is a (dx, dy).
    fallback_directions is a list of (dx, dy).
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
    """Mark the segment from (x1,y1) to (x2,y2) as occupied.
       Here, because we move in discrete steps of 5,
       we can just occupy (x2,y2).
    """
    # Actually, let's also add the start to be safe
    occupied.add((x1, y1))
    occupied.add((x2, y2))

class Line:
    """
    Represents a line being drawn.
    """
    def __init__(self, start_x, start_y, max_steps, allow_branch=True):
        self.path = [(start_x, start_y)]  # list of (x,y)
        occupied.add((start_x, start_y))
        
        self.x = start_x
        self.y = start_y
        
        self.steps_taken = 0
        self.max_steps = max_steps
        
        # For the first 10 steps, we do not allow branching or orth
        # unless this is a branch line forced to do orth at start.
        self.forbid_special_until = 10
        
        # This determines if we can do a random orth or branch
        self.used_orth = False      # once we do an orth block, no more
        self.used_branch = False    # once we branch, no more
        self.allow_branch = allow_branch  # some lines might disallow branching from the start
        
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
        We want to move (5,5) primarily.
        If blocked, systematically try (5,0) then (0,5).
        """
        move = systematic_move(self.x, self.y, (STEP_SIZE, STEP_SIZE),
                               [(STEP_SIZE, 0), (0, STEP_SIZE)])
        if move is None:
            # all blocked -> stop
            self.active = False
            return
        nx, ny = move
        self.add_point(nx, ny)

    def block_of_5_orth(self):
        """
        Do a block of 5 orth steps, choosing (5,0) or (0,5) once.
        If the first step is blocked, we systematically try the other orth direction.
        If that fails, we stop immediately.
        Then for each subsequent step, we keep the same direction
        but systematically fallback if blocked.
        """
        # 1) pick primary direction at random
        if random.random() < 0.5:
            primary = (STEP_SIZE, 0)
            alternate = (0, STEP_SIZE)
        else:
            primary = (0, STEP_SIZE)
            alternate = (STEP_SIZE, 0)

        # 2) For the very first step, if primary is blocked, try alternate. 
        #    If that's also blocked, stop line.
        first_move = systematic_move(self.x, self.y, primary, [alternate])
        if first_move is None:
            self.active = False
            return
        nx, ny = first_move
        self.add_point(nx, ny)
        
        # Then do 4 more steps in the chosen direction with fallback
        # but the fallback is the same approach: we systematically try primary->alternate?
        chosen_dir = None
        if (nx - self.x) == STEP_SIZE or (ny - self.y) == STEP_SIZE:
            # We found out which direction we actually used
            # but we must recalc. Actually let's store the difference:
            chosen_dir = (nx - self.x, ny - self.y)
            # But note we updated self.x, self.y to new location
            # so the difference is not correct. Let's do it more explicitly:
            # We'll do it by comparing the old x,y with new x,y,
            # but we've already updated. 
            # Actually we can deduce from the first_move logic:
            # if first_move matched `primary`, we do primary
            # else we do alternate.  Let's do a simpler approach:
            # we check if first_move == None or not. 
            # Actually we know it wasn't None. We can see if it equals the direct try of primary.
            pass
        # We'll do it more directly:
        # Because the first_move used systematic_move with primary, fallback [alternate].
        # If the first attempt was valid, we used primary. Otherwise we used alternate.
        # Let's re-check.
        first_primary = try_move(self.x, self.y, primary[0], primary[1])
        if first_primary is not None and first_primary == (nx, ny):
            chosen_dir = primary
        else:
            chosen_dir = alternate

        # Now do the remaining 4 steps
        for _ in range(4):
            if not self.can_continue():
                break
            move2 = systematic_move(self.x, self.y, chosen_dir, [])
            # no fallback other than same direction? 
            # The user said "If a direction is blocked, systematically try the different directions"
            # but we are in a forced block of orth steps. We'll keep it simpler:
            # We'll systematically try the other orth if primary fails:
            if chosen_dir == primary:
                fallback2 = [alternate]
            else:
                fallback2 = [primary]
            if move2 is None:
                move2 = systematic_move(self.x, self.y, chosen_dir, fallback2)
            if move2 is None:
                self.active = False
                break
            nx2, ny2 = move2
            self.add_point(nx2, ny2)
    
    def do_forced_5_orth_branch_start(self):
        """
        For a branch line, we do 5 forced orth steps at the beginning.
        We do the same systematic approach as block_of_5_orth,
        but we skip the "first 10 steps no orth" rule because branch lines get an exception.
        """
        self.block_of_5_orth()

    def step(self):
        """
        Take one step, respecting the "no special moves for first 10 steps" rule,
        random probabilities, etc.
        - If we are out of steps or inactive, do nothing.
        - Otherwise, do diagonal if we can't do something else.
        """
        if not self.can_continue():
            return

        # If we are still in the first-10-step zone, do diagonal only:
        if self.steps_taken < self.forbid_special_until:
            # do diagonal
            self.step_diagonal_with_systematic_fallback()
            return

        # Past the first 10 steps, we can do branch / orth / diagonal
        if self.used_branch or self.used_orth or (not self.allow_branch):
            # we've either used them or we can't branch => just diagonal
            self.step_diagonal_with_systematic_fallback()
            return
        
        # Otherwise, we pick a random number in [0,1).
        r = random.random()
        if r < 0.01:
            # Try to branch
            # Only if we have at least 10 steps left 
            leftover = self.max_steps - self.steps_taken
            if leftover >= 10:
                # We end this line RIGHT NOW, but we need to spawn the branch line 
                # outside of this method. We'll set used_branch = True so we know we branched.
                self.used_branch = True
                self.active = False  # line finishes
            else:
                # Not enough steps to branch -> do diagonal
                self.step_diagonal_with_systematic_fallback()
            return
        elif r < 0.02:
            # Orth block
            self.used_orth = True
            self.block_of_5_orth()
        else:
            # Diagonal
            self.step_diagonal_with_systematic_fallback()

# class LivePreview:
#     def __init__(self, width, height):
#         self.root = tk.Tk()
#         self.root.title("SVG Live Preview")
#         self.canvas = tk.Canvas(self.root, width=width, height=height, bg="white")
#         self.canvas.pack()
#         self.img_id = None

#     def update_preview(self, svg_data):
#         # Convert SVG to PNG
#         png_data = BytesIO()
#         cairosvg.svg2png(bytestring=svg_data, write_to=png_data)
#         png_data.seek(0)

#         # Load PNG into Tkinter
#         image = Image.open(png_data)
#         photo = ImageTk.PhotoImage(image)

#         # Display image on canvas
#         if self.img_id is not None:
#             self.canvas.delete(self.img_id)
#         self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=photo)

#         # Keep a reference to prevent garbage collection
#         self.canvas.image = photo

#     def start(self):
#         self.root.mainloop()
class LivePreview:
    """Handles live preview using Tkinter."""
    def __init__(self, width, height):
        self.root = tk.Tk()
        self.root.title("SVG Live Preview")
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg="white")
        self.canvas.pack()

    def draw_line(self, line):
        """Draw a line on the canvas."""
        if len(line.path) > 1:
            for i in range(len(line.path) - 1):
                x1, y1 = line.path[i]
                x2, y2 = line.path[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="black", width=2)

    def draw_circle(self, x, y):
        """Draw a circle on the canvas."""
        r = 5
        self.canvas.create_oval(x - r, y - r, x + r, y + r, outline="black")

    def update_preview(self, lines):
        """Update the canvas with all lines and circles."""
        self.canvas.delete("all")  # Clear the canvas
        for line in lines:
            self.draw_line(line)
            if line.path:
                x, y = line.path[-1]
                self.draw_circle(x, y)  # Draw a circle at the end of the line

    def start(self):
        self.root.mainloop()

def create_branch_line(parent_line):
    """
    Create a branch line from the parent's current position,
    with max_steps = leftover + 5.
    Then do forced 5 orth at the start, then diagonal to finish.
    """
    start_x, start_y = parent_line.current_pos()
    leftover = parent_line.max_steps - parent_line.steps_taken
    max_steps = leftover + 5
    if max_steps <= 0:
        return None  # no steps to do

    branch_line = Line(start_x, start_y, max_steps,
                       allow_branch=False)  # no further branching
    # Immediately do 5 forced orth steps
    branch_line.do_forced_5_orth_branch_start()
    return branch_line


def create_svg(lines):
    """
    Build an SVG from all lines, with circles at endpoints.
    """
    dwg = svgwrite.Drawing("output.svg", size=(WIDTH, HEIGHT))
    dwg.add(dwg.rect(insert=(0,0), size=(WIDTH,HEIGHT), fill="white"))

    for ln in lines:
        pts = ln.path
        if len(pts) < 2:
            # Only one point -> no polyline to draw
            if len(pts) == 1:
                # But still a circle at that single point
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


def main():
    from time import sleep
    seed = random.randint(0,1000000)
    random.seed(seed)
    preview = LivePreview(WIDTH, HEIGHT)

    # 1) Create the main line
    main_line = Line(0, 0, max_steps=999999, allow_branch=False)
    all_lines = [main_line]

    def generate_lines():
        # Move diagonally until x>=300 or y>=300
        while main_line.active:
            if main_line.x >= 300 or main_line.y >= 300:
                main_line.active = False
                break
            main_line.step_diagonal_with_systematic_fallback()

        main_length = main_line.steps_taken

        print(f"Main line finished after {main_length} steps.")

        
        # 2) We want 15 more lines with offsets:
        #    (0,5), (5,0), (0,10), (10,0), ...
        # We'll track how many lines have been created so far (besides the main line).
        num_extra_lines = 15
        offset_count = 1  # we start from 1 for the 5-based increments

        # We'll also keep a queue or list in case lines spawn branches
        # as we progress. We'll process them in order.
        # We'll call the lines in the offset pattern "primary lines."
        # If they spawn a branch, we create the branch line and add it after the parent finishes.
        # Each new line also can spawn at most 1 branch.
        # We'll store them in all_lines in the order they are created.
        
        for i in range(num_extra_lines):
            # Compute offset
            # For i=0 -> offset_count=1 => offset=5
            # for i=1 -> offset_count=2 => offset=10
            offset_val = 5 * offset_count
            # Alternate between (0, offset) and (offset, 0)
            if i % 2 == 0:
                start_x, start_y = (0, offset_val)
            else:
                start_x, start_y = (offset_val, 0)

            offset_count += 1

            # Make the line
            max_steps = max(1, main_length - 5)  # ensure it's at least 1
            line_obj = Line(start_x, start_y, max_steps, allow_branch=True)
            # now we step it until it's done
            while line_obj.can_continue():
                
                line_obj.step()
                # Check if it just branched:
                if (line_obj.used_branch and not line_obj.active):
                    # Create the branch line
                    branch_line = create_branch_line(line_obj)
                    if branch_line is not None:
                        all_lines.append(branch_line)
                        # We now run the branch line until it stops
                        while branch_line.can_continue():
                            branch_line.step()
                            # preview.update_preview(all_lines)
                    # The parent line is done for good
                    break
            all_lines.append(line_obj)
            # sleep(1)

    # Run the line generation in a background thread
    # import threading
    # generation_thread = threading.Thread(target=generate_lines, daemon=True)
    # generation_thread.start()
    generate_lines()

    # preview.start()

    # 3) Output everything
    svg = create_svg(all_lines)
    svg.save()
    print("SVG saved as output.svg")
    print("Seed:", seed)


if __name__ == "__main__":
    main()
