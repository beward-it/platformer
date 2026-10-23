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
        self.die_msg = pyglet.text.Label("", wind.width / 2, wind.height / 2 + 50, anchor_x='center', anchor_y='center', font_size=100, color=(255, 0, 0))
        self.is_alive = True

    def deadth(self):
        self.die_msg.text = "YOU DIED!!!"
        self.is_alive= False
        self.playr.color = (255, 0, 0)
        for i in range(10):
            self.playr.y += 1
        while self.playr.y >= 0:
            self.playr.y -= 2


playr = Playr(sh.Rectangle(320, 320, 20, 20))
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
            print(mpx, mpy, mxpx, mxpy, " wall ", mwx, mwy, mxwx, mxwy)
            if ((mxwy > mxpy >= mwy) or (mxwy > mpy >= mwy)) and ((mxwx > mxpx >= mwx) or (mxwx > mpx >= mwx)):
                print()
                return True
            return False


class Spikes:
    def __init__(self, playr):
        self.playr = playr
        self.spikes_bat = pyglet.graphics.Batch()
        self.spikes = [sh.Triangle(400, 300, 410, 315, 420, 300, batch=self.spikes_bat)]

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
walls.walls.append(sh.Rectangle(200, 200, 500, 100, batch=walls.walls_bat))
x1, y1 = 0, 0
bat = pyglet.graphics.Batch()
@wind.event
def on_mouse_press(x, y, button, modifiers):
    global x1
    global y1
    x1 = x
    y1 = y
    print(x1, y1)

@wind.event
def on_mouse_release(x, y, button, modifiers):
    global x1
    global y1
    print(x1, y1, x, y)
    global rest
    rest = sh.Rectangle(x1, y1, x - x1, y - y1, batch=walls.walls_bat)
    walls.walls.append(rest)

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
                is_on_wall = wall.y + wall.height == playr.playr.y
                if is_on_wall:
                    break
            if is_on_wall:
                for i in range(100, 0, -1):
                    print("hello", i)
                    if not walls.check_coll(playr.playr, 0, i):
                        print("yes", i)
                        dy = i
                        break
        if keyboard[S]:
            dy -=2
        if not walls.check_coll(playr.playr, dx) and playr.playr.x + playr.playr.width + dx <= wind.width and playr.playr.x - dx >= 0:
            playr.playr.x += dx
        if not walls.check_coll(playr.playr, 0, -1):
            #playr.playr.y -= 1
            if playr.playr.y <= 0:
                playr.deadth()
        if not walls.check_coll(playr.playr, 0, dy):
            print(dy, "dy")
            playr.playr.y += dy
        spikes.damage()
@wind.event
def on_draw():
    wind.clear()
    bat.draw()
    playr.die_msg.draw()
    playr.playr.draw()
    spikes.spikes_bat.draw()
    walls.walls_bat.draw()
pyglet.clock.schedule_interval(update, 1/90)
pyglet.app.run()