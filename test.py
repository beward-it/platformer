        mpx = self.playr.x + dx
        mpy = self.playr.y + dy
        mxpx = self.playr.x + self.playr.width + dx
        mxpy = self.playr.y + self.playr.height + dy
        for spike in self.spikes:
            mspx = spike.x
            mspy = spike.y
            mxspx = spike.x3
            mxspy = spike.y2
            #print(mpx, mpy, mxpx, mxpy, " spike ", mspx, mwy, mxspx, mxspy)
            return ((mxspy > mxpy > mspy) or (mxspy > mpy > mspy)) and ((mxspx > mxpx > mspx) or (mxspx > mpx > mspx))