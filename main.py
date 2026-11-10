import pyglet
from pyglet.window.key import *
from pyglet import shapes as sh
import time
wind = pyglet.window.Window(1080, 720)
keyboard = KeyStateHandler()
wind.push_handlers(keyboard)
class Playr:
    def __init__(self, playr):
        self.playr = playr
        self.die_msg = pyglet.text.Label("", wind.width / 2, wind.height / 2 + 50, 100,anchor_x='center', anchor_y='center', font_size=100, color=(255, 0, 0))
        self.is_alive = True

    def deadth(self):
        self.die_msg.text = "YOU DIED!!!"
        self.is_alive= False
        self.playr.color = (255, 0, 0)
        for i in range(10):
            self.playr.y += 1
        while self.playr.y >= 0:
            self.playr.y -= 2

walls_created = []
spikes_created = []
playr = Playr(sh.Rectangle(300, 300, 20, 20))
class Walls:
    def __init__(self, playr):
        self.walls = []
        self.walls_bat = pyglet.graphics.Batch()
        self.playr = playr

    def check_coll(self, unity, dx=0, dy=0):
        mpx = unity.x + dx
        mpy = unity.y + dy
        mxpx = unity.x + unity.width + dx
        mxpy = unity.y + unity.height + dy
        for wall in self.walls:
            mwx = wall.x
            mwy = wall.y
            mxwx = wall.x + wall.width
            mxwy = wall.y + wall.height
            #print("x", mpx, mxpx, "y", mpy, mxpy, " wall ", "x", mwx, mxwx, "y", mwy, mxwy)
            if ((mxwy > mxpy > mwy) or (mxwy > mpy > mwy)) and ((mxwx > mxpx > mwx) or (mxwx > mpx > mwx)):
                #print(True)
                return True
            #print(False)
        return False


class Moving_damagers:
    def __init__(self, playr):
        self.playr = playr
        self.dmgrs_bat = pyglet.graphics.Batch()
        self.movers = {
        }


class Spikes:
    def __init__(self, playr):
        self.playr = playr
        self.spikes_bat = pyglet.graphics.Batch()
        self.spikes = [sh.Triangle(400, 300, 410, 320, 420, 300, batch=self.spikes_bat)]

    def damage(self):
        mpx = self.playr.playr.x
        mpy = self.playr.playr.y
        mxpx = self.playr.playr.x + self.playr.playr.width
        mxpy = self.playr.playr.y + self.playr.playr.height
        for spike in self.spikes:
            mspx = spike.x
            mspy = spike.y
            mxspx = spike.x3 - spike.x
            mxspy = spike.y2 - spike.y
            #print(mpx, mpy, mxpx, mxpy, " spike ", mspx, mspy, mxspx, mxspy)
            if ((mxspy >= mxpy >= mspy) or (mxspy >= mpy >= mspy)) and ((mxspx >= mxpx >= mspx) or (mxspx >= mpx >= mspx)):
                self.playr.deadth()

spikes = Spikes(playr)
walls = Walls(playr)

walls.walls.append(sh.Rectangle(280, 280, 60, 20, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(400, 240, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(500, 190, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(600, 140, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(700, 190, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(800, 240, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(900, 190, 40, 10, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(1000, 140, 60, 10, batch=walls.walls_bat, color=(200, 100, 50)))
walls.walls.append(sh.Rectangle(0, 0, 60, 20, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(280, 0, 60, 20, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(520, 0, 40, 20, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(760, 0, 40, 20, batch=walls.walls_bat, color=(230, 210, 150)))
walls.walls.append(sh.Rectangle(1000, 0, 80, 20, batch=walls.walls_bat, color=(230, 210, 150)))
for x in range(0, 1080, 20):
    safe_r = [(0, 60), (280, 340), (520, 560), (760, 800), (1000, 1080)]
    if not any(a <= x and x+20 <= b for a, b in safe_r):
        spikes.spikes.append(sh.Triangle(x, 20, x+10, 40, x+20, 20, batch=spikes.spikes_bat))

x1, y1 = 0, 0
bat = pyglet.graphics.Batch()

@wind.event
def on_mouse_press(x, y, button, modifiers):
    if modifiers:
        global x1
        global y1
        x1 = int(x)
        y1 = int(y)
        return
    global spikes_created
    global spike
    spike = sh.Triangle(x, y, x + 10, y + 20, x + 20, y, batch=spikes.spikes_bat)
    spikes_created.append(f"sh.Triangle({x}, {y}, {x + 10}, {y + 20}, {x + 20}, {y}, batch=spikes.spikes_bat)\n")
    print(spikes_created)
    spikes.spikes.append(spike)

@wind.event
def on_mouse_release(x, y, button, modifiers):
    if modifiers:
        global walls_created
        global x1
        global y1
        global rest
        rest = sh.Rectangle(min(x1, int(x)), min(y1, int(y)), max(x1, int(x)) - min(x1, int(x)), max(y1, int(y)) - min(y1, int(y)), batch=walls.walls_bat, color=(230, 210, 150))
        walls.walls.append(rest)
        walls_created.append(f"sh.Rectangle({min(x1, int(x))}, {min(y1, int(y))}, {max(x1, int(x)) - min(x1, int(x))}, {max(y1, int(y)) - min(y1, int(y))}, batch=walls.walls_bat, color=(230, 210, 150))")
        print(walls_created)

def update(dt):
    if playr.is_alive:
        dx = 0
        dy = 0
        if keyboard[D]:
            dx += 2
        if keyboard[A]:
            dx -= 2
        if keyboard[SPACE]:
            for wall in walls.walls:
                if wall.y + wall.height == playr.playr.y and wall.x - playr.playr.width <= playr.playr.x <= wall.x + wall.width :
                    for i in range(101):
                        #print("hello", i)
                        dy = i
                        if walls.check_coll(playr.playr, 0, i):
                            #print("yes", i)
                            dy -= 1
                            break
                    break
        if keyboard[S]:
            dy -=2
        if not walls.check_coll(playr.playr, dx) and playr.playr.x + playr.playr.width + dx <= wind.width and playr.playr.x - dx >= 0:
            playr.playr.x += dx
        if not walls.check_coll(playr.playr, 0, -1):
            playr.playr.y -= 1
            if playr.playr.y <= 0:
                playr.deadth()
        if not walls.check_coll(playr.playr, 0, dy):
            playr.playr.y += dy
        spikes.damage()
@wind.event
def on_draw():
    wind.clear()
    bat.draw()
    playr.playr.draw()
    spikes.spikes_bat.draw()
    walls.walls_bat.draw()
    playr.die_msg.draw()
pyglet.clock.schedule_interval(update, 1/90)
pyglet.app.run()