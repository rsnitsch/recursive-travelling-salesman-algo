#!/usr/bin/env python3
import turtle
import copy


class Renderer(object):

    def visualize(self, route):
        raise NotImplementedError("visualize() must be implemented in subclasses")


class RendererTurtle(Renderer):

    def __init__(self, scale=1.5):
        self.scale = scale
        self.route_history = []
        self.current_idx = 0
        self.screen = turtle.Screen()
        self.screen.tracer(0, 0)
        self.t = turtle.Turtle(visible=False)
        self.t.speed("fastest")
        self._coords_setup = False

    def _setup_coords(self, route):
        min_x = min(node.x for node in route)
        max_x = max(node.x for node in route)
        min_y = min(node.y for node in route)
        max_y = max(node.y for node in route)
        data_width = max_x - min_x
        data_height = max_y - min_y
        if data_width == 0:
            data_width = 1
        if data_height == 0:
            data_height = 1
        data_aspect = data_width / float(data_height)
        MAX_DISPLAY_DIMENSION = 500
        display_padding = MAX_DISPLAY_DIMENSION * 0.1
        if data_width > data_height:
            display_width = MAX_DISPLAY_DIMENSION
            display_height = display_width / data_aspect
        else:
            display_height = MAX_DISPLAY_DIMENSION
            display_width = display_height * data_aspect
        w = display_width + 2 * display_padding
        h = display_height + 2 * display_padding

        self.screen.setup(width=w * self.scale, height=h * self.scale)
        self.offset_x = min_x
        self.offset_y = min_y
        self.data_width = data_width
        self.data_height = data_height
        self.display_width = display_width
        self.display_height = display_height
        self._coords_setup = True

    def _tx(self, x):
        return ((x - self.offset_x) / self.data_width * self.display_width - self.display_width / 2.0) * self.scale

    def _ty(self, y):
        return ((y - self.offset_y) / self.data_height * self.display_height - self.display_height / 2.0) * self.scale

    def visualize(self, route):
        self.route_history.append(copy.deepcopy(route))

    def draw_route(self, idx: int):
        if idx < 0 or idx >= len(self.route_history):
            raise IndexError("Index out of range for route history.")

        route = self.route_history[idx]
        title = f"Step {self.current_idx+1} - Nodes: {len(route)}"
        if self.current_idx == len(self.route_history) - 1:
            title += " (Final)"
        self.screen.title(f"Route: {title}")

        if not self._coords_setup:
            self._setup_coords(route)
        self.t.clear()
        self.t.penup()
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.pendown()
        for node in route[1:]:
            self.t.goto(self._tx(node.x), self._ty(node.y))
            self.t.dot(4)
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.dot(8)  # Startpunkt etwas größer
        self.screen.update()

    def prev(self):
        if self.current_idx > 0:
            self.current_idx -= 1
        else:
            self.current_idx = len(self.route_history) - 1
        self.draw_route(self.current_idx)

    def next(self):
        if self.current_idx < len(self.route_history) - 1:
            self.current_idx += 1
        else:
            self.current_idx = 0
        self.draw_route(self.current_idx)

    def setup_keybindings(self):
        self.screen.listen()
        self.screen.onkey(self.prev, "Left")
        self.screen.onkey(self.next, "Right")

    def wait_until_closed(self):
        self.current_idx = len(self.route_history) - 1
        self.draw_route(self.current_idx)
        self.setup_keybindings()
        self.screen.mainloop()
