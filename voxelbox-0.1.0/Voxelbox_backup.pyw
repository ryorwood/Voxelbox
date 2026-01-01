# voxel_demo.py
import sys
import math
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

# --------- Configuration ----------
WINDOW_SIZE = (1280, 720)
FOV = 80.0
NEAR_PLANE = 0.1
FAR_PLANE = 10000.0

MOUSE_SENSITIVITY = 0.15
MOVE_SPEED = 6.7
FLY_SPEED = 6.7
PLACE_DISTANCE = 2.2
# ---------------------------------

def draw_cube_at(pos, size=1.0):
    x, y, z = pos
    s = size / 2.0
    # 8 corners
    v = [
        (x - s, y - s, z - s),
        (x + s, y - s, z - s),
        (x + s, y + s, z - s),
        (x - s, y + s, z - s),
        (x - s, y - s, z + s),
        (x + s, y - s, z + s),
        (x + s, y + s, z + s),
        (x - s, y + s, z + s),
    ]
    # faces as tuples of vertex indices, and normals
    faces = [
        (0,1,2,3, (0,0,-1)),  # back
        (4,5,6,7, (0,0,1)),   # front
        (0,1,5,4, (0,-1,0)),  # bottom
        (3,2,6,7, (0,1,0)),   # top
        (1,2,6,5, (1,0,0)),   # right
        (0,3,7,4, (-1,0,0)),  # left
    ]
    glBegin(GL_QUADS)
    for a,b,c,d, normal in faces:
        glNormal3fv(normal)
        glVertex3fv(v[a])
        glVertex3fv(v[b])
        glVertex3fv(v[c])
        glVertex3fv(v[d])
    glEnd()

def draw_axis(length=1.0):
    glBegin(GL_LINES)
    # X red
    glColor3f(1,0,0); glVertex3f(0,0,0); glVertex3f(length,0,0)
    # Y green
    glColor3f(0,1,0); glVertex3f(0,0,0); glVertex3f(0,length,0)
    # Z blue
    glColor3f(0,0,1); glVertex3f(0,0,0); glVertex3f(0,0,length)
    glEnd()

class Camera:
    def __init__(self, pos=(0,2,5), yaw=0.0, pitch=0.0):
        self.pos = list(pos)
        self.yaw = yaw    # degrees, 0 points along -Z
        self.pitch = pitch  # degrees

    def forward_vector(self):
        # convert yaw/pitch to a forward vector
        yaw_rad = math.radians(self.yaw)
        pitch_rad = math.radians(self.pitch)
        x = math.cos(pitch_rad) * math.sin(yaw_rad)
        y = math.sin(pitch_rad)
        z = -math.cos(pitch_rad) * math.cos(yaw_rad)
        return (x, y, z)

    def right_vector(self):
        yaw_rad = math.radians(self.yaw - 90)
        return (math.sin(yaw_rad), 0, -math.cos(yaw_rad))

    def up_vector(self):
        f = self.forward_vector()
        r = self.right_vector()
        # cross product r x f
        ux = r[1]*f[2] - r[2]*f[1]
        uy = r[2]*f[0] - r[0]*f[2]
        uz = r[0]*f[1] - r[1]*f[0]
        return (ux, uy, uz)

    def apply_gl(self):
        # Build lookAt matrix: camera looks from pos towards pos + forward
        f = self.forward_vector()
        cx, cy, cz = self.pos
        tx = cx + f[0]
        ty = cy + f[1]
        tz = cz + f[2]
        glLoadIdentity()
        gluLookAt(cx, cy, cz, tx, ty, tz, 0,1,0)

def pos_to_grid(p):
    # convert float pos to integer block coords (round to nearest int)
    return (int(math.floor(p[0] + 0.5)), int(math.floor(p[1] + 0.5)), int(math.floor(p[2] + 0.5)))

def main():
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("voxel demo")
    clock = pygame.time.Clock()

    # OpenGL setup
    glEnable(GL_DEPTH_TEST)
    #glEnable(GL_CULL_FACE)
    #glCullFace(GL_BACK)
    glEnable(GL_NORMALIZE)
    glShadeModel(GL_SMOOTH)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, (WINDOW_SIZE[0] / WINDOW_SIZE[1]), NEAR_PLANE, FAR_PLANE)
    glMatrixMode(GL_MODELVIEW)

    cam = Camera()

    # hide and capture cursor
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()  # flush

    # world blocks stored in a dict or set of (x,y,z) tuples
    blocks = set()

    # Create flat platform of blocks from x,z -10..10 at y=0
    PLATFORM_RADIUS = 3
    for x in range(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1):
        for z in range(-PLATFORM_RADIUS, PLATFORM_RADIUS + 1):
            blocks.add((x, 0, z))  # platform at y=0
    # a few blocks above to make interesting
    blocks.add((0,1,0))
    blocks.add((1,1,0))

    running = True
    paused = False

    while running:
        dt = clock.tick(60) / 1000.0  # seconds
        # handle events
        for ev in pygame.event.get():
            if ev.type == QUIT:
                running = False
            elif ev.type == KEYDOWN:
                if ev.key == K_ESCAPE:
                    running = False
                if ev.key == K_p:
                    paused = not paused
                    pygame.mouse.set_visible(paused)
                    pygame.event.set_grab(not paused)
            elif ev.type == MOUSEBUTTONDOWN:
                if not paused:
                    if ev.button == 1:  # left click: place block in front
                        f = cam.forward_vector()
                        px, py, pz = cam.pos
                        place_pos = (px + f[0] * PLACE_DISTANCE,
                                     py + f[1] * PLACE_DISTANCE,
                                     pz + f[2] * PLACE_DISTANCE)
                        grid = pos_to_grid(place_pos)
                        # don't place where player stands (simple check)
                        player_grid = pos_to_grid(cam.pos)
                        if grid != player_grid and grid not in blocks:
                            blocks.add(grid)
                    elif ev.button == 3:  # right click: remove nearest block in front
                        f = cam.forward_vector()
                        px, py, pz = cam.pos
                        # check steps along the ray
                        removed = False
                        steps = 64
                        for i in range(1, steps+1):
                            t = i * (PLACE_DISTANCE / steps) * 2.0
                            check = (px + f[0] * t, py + f[1] * t, pz + f[2] * t)
                            grid = pos_to_grid(check)
                            if grid in blocks:
                                blocks.remove(grid)
                                removed = True
                                break
                        if not removed:
                            # try remove block right in front if nothing found
                            grid = pos_to_grid((px + f[0]*PLACE_DISTANCE, py + f[1]*PLACE_DISTANCE, pz + f[2]*PLACE_DISTANCE))
                            if grid in blocks:
                                blocks.remove(grid)
            elif ev.type == MOUSEMOTION and not paused:
                mx, my = ev.rel
                cam.yaw += mx * MOUSE_SENSITIVITY
                cam.pitch -= my * MOUSE_SENSITIVITY
                # clamp pitch to avoid flip
                cam.pitch = max(-89.9, min(89.9, cam.pitch))

        keys = pygame.key.get_pressed()
        if not paused:
            # movement
            move_dir = [0.0, 0.0, 0.0]
            forward = cam.forward_vector()
            right = cam.right_vector()
            # WASD
            if keys[K_w]:
                move_dir[0] += forward[0]
                move_dir[1] += forward[1]
                move_dir[2] += forward[2]
            if keys[K_s]:
                move_dir[0] -= forward[0]
                move_dir[1] -= forward[1]
                move_dir[2] -= forward[2]
            if keys[K_a]:
                move_dir[0] += right[0]
                move_dir[2] += right[2]
            if keys[K_d]:
                move_dir[0] -= right[0]
                move_dir[2] -= right[2]
            # vertical movement (fly) - optional
            if keys[K_SPACE]:
                move_dir[1] += 1.0
            if keys[K_LCTRL] or keys[K_c]:
                move_dir[1] -= 1.0

            # normalize horizontal
            length = math.sqrt(move_dir[0]**2 + move_dir[1]**2 + move_dir[2]**2)
            if length > 0.0001:
                move_dir = [move_dir[0]/length, move_dir[1]/length, move_dir[2]/length]
                speed = MOVE_SPEED
                cam.pos[0] += move_dir[0] * speed * dt
                cam.pos[1] += move_dir[1] * FLY_SPEED * dt
                cam.pos[2] += move_dir[2] * speed * dt

        # Rendering
        glClearColor(0.53, 0.8, 0.92, 1.0)  # sky-ish
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        cam.apply_gl()

        # draw simple ground plane grid (optional)
        glDisable(GL_LIGHTING)
        glColor3f(0.6, 0.6, 0.6)
        # draw blocks
        for b in blocks:
            # color by height
            bx, by, bz = b
            # simple color mapping by y
            h = (by + 4) / 10.0
            g = max(0.18, min(0.9, 0.6 - 0.2*h))
            r = max(0.05, min(0.9, 0.32 + 0.2*h))
            bcol = max(0.05, min(0.9, 0.2 + 0.1*h))
            glColor3f(r, g, bcol)
            glPushMatrix()
            glTranslatef(bx, by, bz)
            draw_cube_at((0,0,0), size=1.0)
            glPopMatrix()

        # crosshair (2D overlay)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, WINDOW_SIZE[0], WINDOW_SIZE[1], 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glColor3f(0,0,0)
        cx = WINDOW_SIZE[0] // 2
        cy = WINDOW_SIZE[1] // 2
        glBegin(GL_LINES)
        glVertex2f(cx - 8, cy)
        glVertex2f(cx + 8, cy)
        glVertex2f(cx, cy - 8)
        glVertex2f(cx, cy + 8)
        glEnd()
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        # HUD text (fps & instructions) using pygame surfaces
        fps = int(clock.get_fps() if clock.get_fps() > 0 else 0)
        pygame.display.set_caption(f"Voxel-Box {fps}")
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
