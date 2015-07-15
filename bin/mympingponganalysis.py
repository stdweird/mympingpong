#!/usr/bin/env python
##
# Copyright 2010-2015 Ghent University
#
# This file is part of mympingpong,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.ugent.be/hpcugent/mympingpong
#
# mympingpong is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# mympingpong is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mympingpong. If not, see <http://www.gnu.org/licenses/>.
##

"""
@author: Stijn De Weirdt (Ghent University)
@author: Jeroen De Clerck (Ghent University)

Generate plots from output from mympingpong.py
"""

import sys
from math import sqrt

import h5py
import matplotlib as mp
import matplotlib.pyplot as ppl
import matplotlib.cm as cm
import numpy as n
from matplotlib.colorbar import Colorbar, make_axes

from vsc.utils.generaloption import simple_option


class PingPongAnalysis(object):

    def __init__(self, logger):
        self.log = logger

        self.data = None
        self.count = None
        self.fail = None
        self.nodemap = None

        # use multiplication of 10e6 (ie microsec)
        self.scaling = 1e6

        self.meta = None

        self.cmap = None

    def collecthdf5(self, fn):
        """collects metatags, failures, counters and timingdata from fn"""
        f = h5py.File(fn, 'r')

        self.meta = dict(f.attrs.items())
        self.log.debug("collect meta: %s" % self.meta)     

        if self.meta['failed']:
            self.fail = f['fail'][:]
            self.log.debug("collect fail: %s" % self.fail)

        # http://stackoverflow.com/a/118508
        self.count = n.ma.array(f['data'][...,0])
        self.log.debug("collect count: %s" % self.count)

        data = f['data'][...,1]
        data = data*self.scaling
        data = data/n.where(self.count == 0, 1, self.count)
        self.data = n.ma.array(data)
        self.log.debug("collect data: %s" % data)

        f.close()

    def addtext(self, meta, sub, fig):
        self.log.debug("addtext")

        sub.set_axis_off()

        # build a rectangle in axes coords
        left, width = .1, .9
        bottom, height = .1, .9
        right = left + width
        top = bottom + height

        cols = 3
        tags = self.meta.keys()
        nrmeta = len(tags)
        while nrmeta % cols != 0:
            nrmeta += 1
            tags.append(None)
        layout = n.array(tags).reshape(nrmeta/cols, cols)

        for r in xrange(nrmeta/cols):
            for c in xrange(cols):
                m = layout[r][c]
                if not (m and meta.has_key(m)):
                    continue
                val = meta[m]
                sub.text(left+c*width/cols, bottom+r*height/(nrmeta/cols), "%s: %s" %
                         (m, val), horizontalalignment='left', verticalalignment='top', transform=sub.transAxes)

    def addlatency(self, data, sub, fig, latencymin, latencymax):
        """make and show the main latency graph"""
        vmin = latencymin if latencymin else n.min(data[(data > 1/self.scaling).nonzero()])
        vmax = latencymax if latencymax else n.max(data[(data < 1.0*self.scaling).nonzero()])

        self.log.debug("adddata: normalize vmin %s vmax %s" % (vmin, vmax))

        maskeddata = n.ma.masked_where(data == 0, data)
        cax = sub.imshow(maskeddata, cmap=self.cmap, interpolation='nearest', vmin=vmin, vmax=vmax)
        fig.colorbar(cax)

        axlim = sub.axis()
        sub.axis(n.append(axlim[0:2], axlim[2::][::-1]))
        sub.set_title(r'Latency ($\mu s$)')

    def addhistogram(self, data, sub, fig1):
        """make and show the histogram"""

        # prepare and filter out 0-data
        d = data.ravel()
        d = d[(d > 1/self.scaling).nonzero()]
        vmin = n.min(d)
        d = d[(d < 1.0*self.scaling).nonzero()]
        vmax = n.max(d)

        self.log.debug("histogram data: %s", d)
        #calculate bins


        (nn, bins, patches) = sub.hist(d, bins=50)#, range=(vmin, vmax))
        # sub.set_xlim(int(vmin-1),int(vmax+1))

        # black magic: set colormap to histogram bars
        avgbins = (bins[1:]+bins[0:-1])/2
        newc = sub.pcolor(avgbins.reshape(avgbins.shape[0], 1), cmap=self.cmap)
        sub.figure.canvas.draw()
        fcs = newc.get_facecolors()
        newc.set_visible(False)
        newc.remove()
        for i in xrange(avgbins.size):
            patches[i].set_facecolor(fcs[i])
        sub.figure.canvas.draw()

    def addsamplesize(self, count, sub, fig):
        self.log.debug("addcount")

        maskedcount = n.ma.masked_where(count == 0, count)
        cax = sub.imshow(maskedcount, cmap=self.cmap, interpolation='nearest', vmin = 0)
        cb = fig.colorbar(cax)

        axlim = sub.axis()
        sub.axis(n.append(axlim[0:2], axlim[2::][::-1]))
        sub.set_title('Pair samples (#)')

    def plot(self, latencymin, latencymax, data=None, count=None, meta=None):
        self.log.debug("plot")
        if not data:
            data = self.data
        if not count:
            count = self.count
        if not meta:
            meta = self.meta

        # enable LaTeX processing. Internal mathtext should work fine too
        # mp.rcParams['text.usetex']=True
        mp.rcParams['mathtext.fontset'] = 'custom'

        # set colormap
        self.cmap = ppl.get_cmap('jet')
        self.cmap.set_bad(color='grey', alpha=0.25)

        # scale for ISO Ax
        figscale = sqrt(2)
        # A4: 210 mm width
        # 1 millimeter = 0.0393700787 inch
        mmtoin = 0.0393700787
        figwa4 = 210*mmtoin
        figha4 = figwa4*figscale
        fig1 = ppl.figure(figsize=(figwa4, figha4))
        fig1.show()

        def shrink(rec, s=None):
            if not s:
                s = 0.1
            l, b, w, h = rec

            nl = l+w*s/2
            nb = b+h*s/2
            nw = (1-s)*w
            nh = (1-s)*h

            ans = [nl, nb, nw, nh]
            return ans

        texth = 0.1
        subtext = fig1.add_axes(shrink([0, 1-texth, 1, texth]))
        self.addtext(meta, subtext, fig1)

        datah = 1/figscale
        subdata = fig1.add_axes(shrink([0, 1-texth-datah, 1, datah]))
        self.addlatency(data, subdata, fig1, latencymin, latencymax)

        histw = 0.7
        subhist = fig1.add_axes(shrink([0, 0, histw, 1-datah-texth], 0.3))
        self.addhistogram(data, subhist, fig1)

        subcount = fig1.add_axes(shrink([1-histw, 0, histw, 1-datah-texth], 0.3))
        self.addsamplesize(count, subcount, fig1)

        fig1.canvas.draw()

        ppl.show()


if __name__ == '__main__':

    # dict = {longopt:(help_description,type,action,default_value,shortopt),}
    options = {
        'input': ('set the inputfile', str, 'store', 'test2', 'f'),
        'latencyscale': ('set the minimum and maximum of the latency graph', 'strtuple', 'store', ('0','0'), 'l'),
    }

    go = simple_option(options)
    ppa = PingPongAnalysis(go.log)
    ppa.collecthdf5(go.options.input)
    ppa.plot(
        latencymin=int(go.options.latencyscale[0]), 
        latencymax=int(go.options.latencyscale[1]),
        )
