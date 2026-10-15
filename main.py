import pyglet
from pyglet.window.key import *
from pyglet import shapes as sh
wind = pyglet.window.Window(360, 720)
keyboard = KeyStateHandler()
wind.push_handlers(keyboard)
playr = sh.Rectangle(320, 320, 20, 20)
class Walls:
    def __init__(self, playr):
        self.walls = []
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
            if ((mxwy >= mxpy > mwy) or (mxwy >= mpy > mwy)) and ((mxwx >= mxpx > mwx) or (mxwx >= mpx > mwx)):
                return False
        return True

walls = Walls(playr)
walls.walls.append(sh.Rectangle(200, 200, 50, 100))
def update(dt):
    dx = 0
    dy = 0
    if keyboard[D]:
        dx += 1
    if keyboard[A]:
        dx -= 1
    if keyboard[SPACE]:
        for i in range(3):
            if walls.check_coll(playr, 0, 0.5):
                playr.y += 0.5
    if keyboard[S]:
        dy -=1
    if walls.check_coll(playr, dx) and playr.x - dx >= 0 and playr.x + playr.width + dx <= wind.width:
        playr.x += dx
    if walls.check_coll(playr, 0, 0.5):
        playr.y -= 0.5
    if walls.check_coll(playr, 0, dy):
        playr.y += dy
@wind.event
def on_draw():
    wind.clear()
    playr.draw()
    for wall in walls.walls:
        wall.draw()
pyglet.clock.schedule_interval(update, 1/180)
pyglet.app.run()