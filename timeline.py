import datetime
import math
import os

from node import Node
from force import Force
from scale import TimeScale, d3_extent

TIMELINE_DEFAULT_OPTIONS = {
    "margin": {"left": 20, "right": 20, "top": 20, "bottom": 20},
    "initialWidth": 400,
    "initialHeight": 400,
    "scale": TimeScale(),
    "domain": None,
    "direction": "right",
    "dotRadius": 3,
    "layerGap": 60,
    "labella": {},
    "timeFn": lambda d: d["time"],
    "textFn": lambda d: d["text"] if "text" in d else None,
    "dotColor": "#222",
    "labelBgColor": "#222",
    "labelTextColor": "#fff",
    "linkColor": "#222",
    "labelPadding": {"left": 2, "right": 2, "top": 3, "bottom": 2},
    "textXOffset": "0.15em",
    "textYOffset": "0.85em",
    "showTicks": True,
    "borderColor": "#000",
    "showBorder": False,
    "latex": {
        "fontsize": "11pt",
        "borderThickness": "very thick",
        "axisThickness": "very thick",
        "tickThickness": "thick",
        "linkThickness": "very thick",
        "tickCross": False,
        "preamble": "",
        "reproducible": False,
    },
}

DEFAULT_WIDTH = 50
TEXT_WIDTH_MULTI = 2
TEXT_HEIGHT = 20

class Item(object):
    def __init__(
        self,
        time,
        width=DEFAULT_WIDTH,
        text=None,
        data=None,
        output_mode="svg",
        tex_fontsize="11pt",
        tex_preamble=None,
        latexmk_options=None,
    ):
        self.time = time
        self.text = text
        self.width = width
        self.data = data
        self.output_mode = output_mode
        self.tex_fontsize = tex_fontsize
        self.tex_preamble = tex_preamble
        self.latexmk_options = latexmk_options
        if self.width is None and self.text:
            self.width, self.height = self.get_text_dimensions()
        else:
            self.height = 13.0

    def get_text_dimensions(self):
        return len(self.text) * TEXT_WIDTH_MULTI, TEXT_HEIGHT

    def __str__(self):
        s = "Item(time=%r, text=%r, width=%r, height=%r, data=%r)" % (
            self.time,
            self.text,
            self.width,
            self.height,
            self.data,
        )
        return s

    def __repr__(self):
        return str(self)

class Timeline(object):
    def __init__(self, dicts, options=None, output_mode="svg"):
        # update timeline options
        self.options = {k: v for k, v in TIMELINE_DEFAULT_OPTIONS.items()}
        if options:
            self.options.update(options)
        self.direction = self.options["direction"]
        self.options["labella"]["direction"] = self.direction
        # parse items
        self.items = self.parse_items(dicts, output_mode=output_mode)
        self.equal_heights()
        self.rotate_items()
        self.init_axis(dicts)

    def equal_heights(self):
        maxheight = max((x.height for x in self.items))
        for item in self.items:
            if item.text:
                item.height = maxheight

    def rotate_items(self):
        if self.direction in ["left", "right"]:
            for item in self.items:
                if item.text:
                    item.height, item.width = item.width, item.height

    def parse_items(self, dicts, output_mode="svg"):
        items = []
        for d in dicts:
            time = d["time"]
            if isinstance(time, datetime.date):
                time = datetime.datetime.combine(
                    time, datetime.datetime.min.time()
                )
                d["time"] = time
            elif isinstance(time, datetime.time):
                time = datetime.datetime.combine(datetime.date.today(), time)
                d["time"] = time
            text = self.textFn(d)
            if text:
                width = d.get("width", None)
            else:
                width = d.get("width", DEFAULT_WIDTH)
            it = Item(
                time,
                width=width,
                text=text,
                data=d,
                output_mode=output_mode,
            )
            items.append(it)
        return items

    def init_axis(self, data):
        if self.options["domain"]:
            self.options["scale"].domain(self.options["domain"])
        else:
            self.options["scale"].domain(
                d3_extent(data, self.options["timeFn"])
            )
            self.options["scale"].nice()
        innerWidth, innerHeight = self.getInnerDims()
        if self.options["direction"] in ["left", "right"]:
            self.options["scale"].range([0, innerHeight])
        else:
            self.options["scale"].range([0, innerWidth])

    def getInnerDims(self):
        innerWidth = (
            self.options["initialWidth"]
            - self.options["margin"]["left"]
            - self.options["margin"]["right"]
        )
        innerHeight = (
            self.options["initialHeight"]
            - self.options["margin"]["top"]
            - self.options["margin"]["bottom"]
        )
        return innerWidth, innerHeight

    def get_nodes(self):
        nodes = []
        for it in self.items:
            n = Node(self.timePos(it.data), it.width, data=it)
            nodes.append(n)
        for node in nodes:
            node.w = (
                node.data.width
                + self.options["labelPadding"]["left"]
                + self.options["labelPadding"]["right"]
            )
            node.h = (
                node.data.height
                + self.options["labelPadding"]["top"]
                + self.options["labelPadding"]["bottom"]
            )
            if self.options["direction"] in ["left", "right"]:
                node.h, node.w = node.w, node.h
                node.width = node.h
            else:
                node.width = node.w
        return nodes

    def compute(self):
        nodes = self.get_nodes()
        if self.direction in ["left", "right"]:
            nodeHeight = max((n.w for n in nodes))
        else:
            nodeHeight = max((n.h for n in nodes))
        renderer = Renderer(
            {
                "nodeHeight": nodeHeight,
                "layerGap": self.options["layerGap"],
                "direction": self.options["direction"],
            }
        )
        renderer.layout(nodes)
        force = Force(self.options["labella"])
        force.nodes(nodes)
        force.compute()
        newnodes = force.nodes()
        renderer.layout(newnodes)
        return newnodes, renderer
    
    def forceCompute(self):
        force = Force(self.options["labella"])
        force.nodes(self.get_nodes())
        force.compute()
        return force.nodes()

    def colorFunc(self, colorName, thedict, i=0):
        if isinstance(self.options[colorName], list):
            return self.options[colorName][i % len(self.options[colorName])]
        theColor = d3_functor(self.options[colorName])
        return theColor(thedict)

    def dotColor(self, thedict, i=0):
        return self.colorFunc("dotColor", thedict, i=i)

    def linkColor(self, thedict, i=0):
        return self.colorFunc("linkColor", thedict, i=i)

    def labelBgColor(self, thedict, i=0):
        return self.colorFunc("labelBgColor", thedict, i=i)

    def labelTextColor(self, thedict, i=0):
        return self.colorFunc("labelTextColor", thedict, i=i)

    def borderColor(self, thedict, i=0):
        return self.colorFunc("borderColor", thedict, i=i)

    def textFn(self, thedict):
        if self.options["textFn"] is None:
            if not "text" in thedict:
                return None
            return thedict.get("text", None)
        return self.options["textFn"](thedict)

    def nodePos(self, d, nodeHeight):
        if self.direction == "right":
            return (d.x, d.y - d.dy / 2)
        elif self.direction == "left":
            return (d.x - d.w + d.dx, d.y - d.dy / 2)
        elif self.direction == "up":
            return (d.x - d.dx / 2, d.y)
        elif self.direction == "down":
            return (d.x - d.dx / 2, d.y)

    def timePos(self, thedict):
        if self.options["scale"] is None:
            return self.options["timeFn"](thedict)
        return self.options["scale"](self.options["timeFn"](thedict))
