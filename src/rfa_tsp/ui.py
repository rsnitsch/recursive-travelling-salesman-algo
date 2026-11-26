#!/usr/bin/env python3
"""
Visualization base classes, step snapshots, and renderers for RFA.

Copyright (c) 2010-2026 Robert Nitsch
"""

import logging
import turtle
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class Phase(StrEnum):
    INIT = "init"
    FOLD = "fold"
    ANCHOR = "anchor"
    UNFOLD = "unfold"
    POST_PROCESS = "post_process"


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    x: float
    y: float
    depth: int = 0


@dataclass(frozen=True, slots=True)
class StepSnapshot:
    phase: Phase
    nodes: tuple[NodeSnapshot, ...]
    fold_sources: tuple[NodeSnapshot, NodeSnapshot] | None = None
    fold_result: NodeSnapshot | None = None
    unfold_parent: NodeSnapshot | None = None
    unfold_children: tuple[NodeSnapshot, NodeSnapshot] | None = None
    cost: int | None = None


def _snapshot_node(node) -> NodeSnapshot:
    return NodeSnapshot(x=node.x, y=node.y, depth=getattr(node, "depth", 0))


def _snapshot_nodes(nodes: Iterable) -> tuple[NodeSnapshot, ...]:
    return tuple(_snapshot_node(n) for n in nodes)


class Renderer:
    """Base renderer that records algorithm steps as lightweight snapshots."""

    def __init__(self) -> None:
        self.history: list[StepSnapshot] = []

    def record_init(self, nodes: Iterable) -> None:
        self.history.append(StepSnapshot(phase=Phase.INIT, nodes=_snapshot_nodes(nodes)))

    def record_fold(self, active_nodes: Iterable, node1, node2, folded_node) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.FOLD,
                nodes=_snapshot_nodes(active_nodes),
                fold_sources=(_snapshot_node(node1), _snapshot_node(node2)),
                fold_result=_snapshot_node(folded_node),
            )
        )

    def record_anchor(self, route_nodes: Iterable) -> None:
        self.history.append(StepSnapshot(phase=Phase.ANCHOR, nodes=_snapshot_nodes(route_nodes)))

    def record_unfold(self, route_nodes: Iterable, parent_node, child1, child2) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.UNFOLD,
                nodes=_snapshot_nodes(route_nodes),
                unfold_parent=_snapshot_node(parent_node),
                unfold_children=(_snapshot_node(child1), _snapshot_node(child2)),
            )
        )

    def record_post_process(self, route_nodes: Iterable, cost: int | None = None) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.POST_PROCESS,
                nodes=_snapshot_nodes(route_nodes),
                cost=cost,
            )
        )

    def wait_until_closed(self) -> None:
        raise NotImplementedError("wait_until_closed() must be implemented in subclasses")


class RendererTurtle(Renderer):
    def __init__(self, scale=1.5):
        super().__init__()
        self.scale = scale
        self.current_idx = 0
        self.screen = turtle.Screen()
        self.screen.tracer(0, 0)
        self.t = turtle.Turtle(visible=False)
        self.t.speed("fastest")
        self._coords_setup = False

    def _setup_coords(self, nodes: tuple[NodeSnapshot, ...]):
        min_x = min(node.x for node in nodes)
        max_x = max(node.x for node in nodes)
        min_y = min(node.y for node in nodes)
        max_y = max(node.y for node in nodes)
        data_width = max_x - min_x or 1
        data_height = max_y - min_y or 1
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

    def draw_route(self, idx: int):
        if idx < 0 or idx >= len(self.history):
            raise IndexError("Index out of range for step history.")

        step = self.history[idx]
        route = step.nodes
        title = f"Step {self.current_idx + 1}/{len(self.history)} [{step.phase.value}] - Nodes: {len(route)}"
        self.screen.title(title)

        if not self._coords_setup:
            self._setup_coords(self.history[0].nodes)

        self.t.clear()
        self.t.penup()
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.pendown()
        for node in route[1:]:
            self.t.goto(self._tx(node.x), self._ty(node.y))
            self.t.dot(4)
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.dot(8)
        self.screen.update()

    def prev(self):
        self.current_idx = (self.current_idx - 1) % len(self.history)
        self.draw_route(self.current_idx)

    def next(self):
        self.current_idx = (self.current_idx + 1) % len(self.history)
        self.draw_route(self.current_idx)

    def setup_keybindings(self):
        self.screen.listen()
        self.screen.onkey(self.prev, "Left")
        self.screen.onkey(self.next, "Right")

    def wait_until_closed(self):
        self.current_idx = len(self.history) - 1
        self.draw_route(self.current_idx)
        self.setup_keybindings()
        self.screen.mainloop()


class RendererMatplotlib(Renderer):
    """Interactive matplotlib renderer with phase-aware visuals, timeline slider, and playback."""

    def __init__(self, interval_ms: int = 150) -> None:
        super().__init__()
        self.interval_ms = interval_ms
        self.current_idx = 0
        self.is_playing = False
        self._updating_slider = False

    def _compute_bounds(self) -> tuple[float, float, float, float]:
        init_nodes = self.history[0].nodes
        xs = [n.x for n in init_nodes]
        ys = [n.y for n in init_nodes]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Use a square bounding box centered on the nodes so the plot frame stays square
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        half_span = (max(max_x - min_x, max_y - min_y) or 1.0) / 2.0
        half_span *= 1.06  # 6% padding on all sides

        return (cx - half_span, cx + half_span, cy - half_span, cy + half_span)

    def _node_size(self, depth: int) -> float:
        # Scale marker area linearly with folding depth so deeper nodes stand out
        return 22.0 + depth * 28.0

    def _draw_step(self, ax, idx: int, bounds: tuple[float, float, float, float], norm, cmap) -> None:
        step = self.history[idx]
        init_nodes = self.history[0].nodes

        ax.cla()
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, linestyle=":", alpha=0.3)

        # Draw original nodes faintly in the background for spatial orientation
        if step.phase != Phase.INIT:
            ax.scatter(
                [n.x for n in init_nodes],
                [n.y for n in init_nodes],
                s=10,
                color="#cbd5e1",
                alpha=0.5,
                zorder=1,
            )

        # Draw route edges only once a tour exists (anchor, unfold, post-process)
        if step.phase in (Phase.ANCHOR, Phase.UNFOLD, Phase.POST_PROCESS) and len(step.nodes) >= 2:
            rx = [n.x for n in step.nodes] + [step.nodes[0].x]
            ry = [n.y for n in step.nodes] + [step.nodes[0].y]
            ax.plot(rx, ry, color="#334155", linewidth=1.4, alpha=0.85, zorder=2)

        # Draw active nodes colored and sized by folding depth
        if step.nodes:
            ax.scatter(
                [n.x for n in step.nodes],
                [n.y for n in step.nodes],
                c=[n.depth for n in step.nodes],
                s=[self._node_size(n.depth) for n in step.nodes],
                cmap=cmap,
                norm=norm,
                edgecolors="#0f172a",
                linewidths=0.6,
                zorder=3,
            )

        # Highlight folding operation: source pair merging into new midpoint
        if step.phase == Phase.FOLD and step.fold_sources and step.fold_result:
            n1, n2 = step.fold_sources
            res = step.fold_result
            ax.plot([n1.x, res.x], [n1.y, res.y], color="#ef4444", linestyle="--", linewidth=1.6, zorder=4)
            ax.plot([n2.x, res.x], [n2.y, res.y], color="#ef4444", linestyle="--", linewidth=1.6, zorder=4)
            ax.scatter(
                [n1.x, n2.x],
                [n1.y, n2.y],
                s=[self._node_size(n1.depth) + 40, self._node_size(n2.depth) + 40],
                facecolors="none",
                edgecolors="#ef4444",
                linewidths=2.0,
                zorder=5,
            )
            ax.scatter(
                [res.x],
                [res.y],
                s=self._node_size(res.depth) + 60,
                color="#f59e0b",
                edgecolors="#7c2d12",
                linewidths=1.5,
                marker="*",
                zorder=6,
            )

        # Highlight unfolding operation: parent splitting into two inserted children
        if step.phase == Phase.UNFOLD and step.unfold_parent and step.unfold_children:
            parent = step.unfold_parent
            c1, c2 = step.unfold_children
            ax.plot([parent.x, c1.x], [parent.y, c1.y], color="#10b981", linestyle=":", linewidth=1.5, zorder=4)
            ax.plot([parent.x, c2.x], [parent.y, c2.y], color="#10b981", linestyle=":", linewidth=1.5, zorder=4)
            ax.scatter(
                [parent.x],
                [parent.y],
                s=self._node_size(parent.depth) + 30,
                color="#94a3b8",
                marker="x",
                linewidths=2.0,
                zorder=5,
            )
            ax.scatter(
                [c1.x, c2.x],
                [c1.y, c2.y],
                s=[self._node_size(c1.depth) + 50, self._node_size(c2.depth) + 50],
                facecolors="none",
                edgecolors="#10b981",
                linewidths=2.2,
                zorder=6,
            )

        phase_labels = {
            Phase.INIT: "Init",
            Phase.FOLD: "Folding",
            Phase.ANCHOR: "Recursion Anchor",
            Phase.UNFOLD: "Unfolding",
            Phase.POST_PROCESS: "Post-Uncross",
        }
        title = f"Step {idx + 1}/{len(self.history)}  |  {phase_labels[step.phase]}  |  Nodes: {len(step.nodes)}"
        if step.cost is not None:
            title += f"  |  Cost: {step.cost}"
        ax.set_title(title, fontsize=11, fontweight="bold")

    def wait_until_closed(self) -> None:
        if not self.history:
            logger.warning("No steps recorded; skipping visualization.")
            return

        # Lazy import so benchmark runs with disabled renderer stay fast
        import matplotlib.pyplot as plt
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize
        from matplotlib.widgets import Slider

        bounds = self._compute_bounds()
        max_depth = max((n.depth for step in self.history for n in step.nodes), default=1)
        max_depth = max(1, max_depth)
        norm = Normalize(vmin=0, vmax=max_depth)
        cmap = plt.get_cmap("viridis")

        fig, ax = plt.subplots(figsize=(9, 7))
        fig.canvas.manager.set_window_title("RFA-TSP Visualizer")
        plt.subplots_adjust(bottom=0.16, right=0.86)

        # Colorbar for folding depth
        cbar_ax = fig.add_axes((0.88, 0.20, 0.025, 0.6))
        sm = ScalarMappable(norm=norm, cmap=cmap)
        cbar = fig.colorbar(sm, cax=cbar_ax)
        cbar.set_label("Folding Depth")

        # Timeline slider
        slider_ax = fig.add_axes((0.12, 0.05, 0.72, 0.035))
        slider = Slider(
            ax=slider_ax,
            label="Step",
            valmin=1,
            valmax=len(self.history),
            valinit=1,
            valstep=1,
        )

        # Controls hint below the slider
        fig.text(
            0.5,
            0.01,
            "Keys: [Left/Right] Step  |  [Shift+Left/Right] +/-10  |  [Home/End] First/Last  |  [Space] Play/Pause  |  [+/-] Speed",
            ha="center",
            fontsize=8.5,
            color="#475569",
        )

        def go_to(idx: int) -> None:
            self.current_idx = max(0, min(len(self.history) - 1, idx))
            self._draw_step(ax, self.current_idx, bounds, norm, cmap)
            self._updating_slider = True
            slider.set_val(self.current_idx + 1)
            self._updating_slider = False
            fig.canvas.draw_idle()

        def on_slider_change(val: float) -> None:
            if not self._updating_slider:
                go_to(int(val) - 1)

        slider.on_changed(on_slider_change)

        # Playback timer
        timer = fig.canvas.new_timer(interval=self.interval_ms)

        def on_timer() -> None:
            if not self.is_playing:
                return
            if self.current_idx < len(self.history) - 1:
                go_to(self.current_idx + 1)
            else:
                self.is_playing = False
                timer.stop()

        timer.add_callback(on_timer)

        def on_key(event) -> None:
            if event.key == "right":
                go_to(self.current_idx + 1)
            elif event.key == "left":
                go_to(self.current_idx - 1)
            elif event.key == "shift+right":
                go_to(self.current_idx + 10)
            elif event.key == "shift+left":
                go_to(self.current_idx - 10)
            elif event.key == "home":
                go_to(0)
            elif event.key == "end":
                go_to(len(self.history) - 1)
            elif event.key == " ":
                self.is_playing = not self.is_playing
                if self.is_playing:
                    if self.current_idx == len(self.history) - 1:
                        go_to(0)
                    timer.start()
                else:
                    timer.stop()
            elif event.key in ("+", "="):
                self.interval_ms = max(20, int(self.interval_ms * 0.7))
                timer.interval = self.interval_ms
                logger.debug("Playback interval: %d ms", self.interval_ms)
            elif event.key == "-":
                self.interval_ms = min(2000, int(self.interval_ms * 1.4))
                timer.interval = self.interval_ms
                logger.debug("Playback interval: %d ms", self.interval_ms)

        def on_close(_event) -> None:
            self.is_playing = False
            timer.stop()

        fig.canvas.mpl_connect("key_press_event", on_key)
        fig.canvas.mpl_connect("close_event", on_close)

        # Start at step 0 so the user can watch or step through from the beginning
        go_to(0)
        plt.show()

    def _build_export_frame_indices(
        self,
        min_fps: float,
        max_fps: float,
        hold_start_seconds: float,
        hold_anchor_seconds: float,
        hold_final_seconds: float,
    ) -> list[int]:
        """Build frame index sequence with variable step timing and pauses at anchor/final steps."""
        n = len(self.history)
        anchor_idx = next((i for i, step in enumerate(self.history) if step.phase == Phase.ANCHOR), None)
        last_idx = n - 1

        frame_indices: list[int] = []
        frame_budget = 0.0

        # Fixed pause at the initial frame
        if hold_start_seconds:
            start_hold_frames = round(hold_start_seconds * max_fps)
            frame_indices.extend([0] * start_hold_frames)

        for idx, step in enumerate(self.history):
            if anchor_idx is not None and min_fps < max_fps:
                if idx <= anchor_idx:
                    # Distance from anchor: 1.0 at start, 0.0 at anchor
                    t = (anchor_idx - idx) / anchor_idx if anchor_idx > 0 else 0.0
                else:
                    # Distance from anchor: 0.0 at anchor, 1.0 at end
                    span = last_idx - anchor_idx
                    t = (idx - anchor_idx) / span if span > 0 else 1.0
                step_fps = min_fps + (max_fps - min_fps) * t
            else:
                step_fps = max_fps

            # Accumulate fractional frames so slow-to-fast transitions stay smooth
            frame_budget += max_fps / step_fps
            repeat_count = max(1, round(frame_budget))
            frame_budget -= repeat_count
            frame_indices.extend([idx] * repeat_count)

            # Fixed pause at the recursion anchor
            if step.phase == Phase.ANCHOR and hold_anchor_seconds > 0:
                anchor_hold_frames = round(hold_anchor_seconds * max_fps)
                frame_indices.extend([idx] * anchor_hold_frames)

        # Fixed pause at the final frame
        if hold_final_seconds > 0:
            final_hold_frames = round(hold_final_seconds * max_fps)
            frame_indices.extend([last_idx] * final_hold_frames)

        return frame_indices

    def _compute_step_durations_ms(
        self,
        min_fps: float,
        max_fps: float,
        hold_start_seconds: float,
        hold_anchor_seconds: float,
        hold_final_seconds: float,
    ) -> list[int]:
        """Compute display duration in milliseconds for each unique history step."""
        n = len(self.history)
        anchor_idx = next((i for i, step in enumerate(self.history) if step.phase == Phase.ANCHOR), None)
        last_idx = n - 1
        durations_ms: list[int] = []

        for idx, step in enumerate(self.history):
            if anchor_idx is not None and min_fps < max_fps:
                if idx <= anchor_idx:
                    t = (anchor_idx - idx) / anchor_idx if anchor_idx > 0 else 0.0
                else:
                    span = last_idx - anchor_idx
                    t = (idx - anchor_idx) / span if span > 0 else 1.0
                step_fps = min_fps + (max_fps - min_fps) * t
            else:
                step_fps = max_fps

            duration = 1000.0 / step_fps
            if idx == 0 and hold_start_seconds > 0:
                duration += hold_start_seconds * 1000.0
            if step.phase == Phase.ANCHOR and hold_anchor_seconds > 0:
                duration += hold_anchor_seconds * 1000.0
            if idx == last_idx and hold_final_seconds > 0:
                duration += hold_final_seconds * 1000.0

            durations_ms.append(max(20, round(duration)))

        return durations_ms

    def export(
        self,
        output_path: Path,
        fps: float | tuple[float, float] = 8,
        dpi: int = 120,
        hold_start_seconds: float = 2.0,
        hold_anchor_seconds: float = 1.0,
        hold_final_seconds: float = 2.0,
    ) -> None:
        if not self.history:
            logger.warning("No steps recorded; skipping export.")
            return

        import matplotlib.pyplot as plt
        from matplotlib.animation import FFMpegWriter, FuncAnimation
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize

        suffix = output_path.suffix.lower()
        is_image_sequence = suffix in (".png", ".svg")
        if not is_image_sequence and suffix not in (".gif", ".mp4", ".mov", ".webm"):
            raise ValueError(f"Unsupported export format '{suffix}'. Use .png, .svg, .gif, .mp4, .mov, or .webm.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        bounds = self._compute_bounds()
        max_depth = max((n.depth for step in self.history for n in step.nodes), default=1)
        max_depth = max(1, max_depth)
        norm = Normalize(vmin=0, vmax=max_depth)
        cmap = plt.get_cmap("viridis")

        fig, ax = plt.subplots(figsize=(8, 6.5), dpi=dpi)
        plt.subplots_adjust(right=0.86)

        cbar_ax = fig.add_axes((0.88, 0.12, 0.025, 0.76))
        sm = ScalarMappable(norm=norm, cmap=cmap)
        cbar = fig.colorbar(sm, cax=cbar_ax)
        cbar.set_label("Folding Depth")

        if is_image_sequence:
            width = max(2, len(str(len(self.history) - 1)))
            logger.info("Exporting %d frames as %s images...", len(self.history), suffix)
            try:
                for idx, step in enumerate(self.history):
                    self._draw_step(ax, idx, bounds, norm, cmap)
                    frame_path = output_path.with_name(f"{output_path.stem}_{idx:0{width}d}_{step.phase.value}{suffix}")
                    fig.savefig(frame_path, dpi=dpi)
                    logger.debug("Saved frame: %s", frame_path)
                logger.info("Exported %d frames to %s", len(self.history), output_path.parent)
            finally:
                plt.close(fig)
            return

        min_fps, max_fps = fps if isinstance(fps, tuple) else (float(fps), float(fps))

        # Native variable frame durations for GIF: render each step once, zero duplicate frames
        if suffix == ".gif":
            import numpy as np
            from PIL import Image

            durations_ms = self._compute_step_durations_ms(
                min_fps=min_fps,
                max_fps=max_fps,
                hold_start_seconds=hold_start_seconds,
                hold_anchor_seconds=hold_anchor_seconds,
                hold_final_seconds=hold_final_seconds,
            )
            logger.info(
                "Exporting %d unique frames to %s (fps=%g-%g, dpi=%d)...",
                len(self.history),
                output_path,
                min_fps,
                max_fps,
                dpi,
            )
            frames: list[Image.Image] = []
            try:
                for idx in range(len(self.history)):
                    self._draw_step(ax, idx, bounds, norm, cmap)
                    fig.canvas.draw()
                    rgba = np.asarray(fig.canvas.buffer_rgba())
                    frames.append(Image.fromarray(rgba).convert("RGB"))

                frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations_ms,
                    loop=0,
                    optimize=True,
                )
                logger.info("Export finished: %s", output_path)
            finally:
                plt.close(fig)
            return

        # Video export (MP4/MOV/WebM): skip redraws for repeated frames; codec handles compression
        base_fps = max(1, round(max_fps))
        writer = FFMpegWriter(fps=base_fps)
        frame_indices = self._build_export_frame_indices(
            min_fps=min_fps,
            max_fps=float(base_fps),
            hold_start_seconds=hold_start_seconds,
            hold_anchor_seconds=hold_anchor_seconds,
            hold_final_seconds=hold_final_seconds,
        )

        logger.info(
            "Exporting %d video frames to %s (fps=%g-%g, base_fps=%d, dpi=%d)...",
            len(frame_indices),
            output_path,
            min_fps,
            base_fps,
            base_fps,
            dpi,
        )

        last_drawn = {"idx": -1}

        def update(frame_idx: int) -> None:
            if frame_idx != last_drawn["idx"]:
                self._draw_step(ax, frame_idx, bounds, norm, cmap)
                last_drawn["idx"] = frame_idx

        anim = FuncAnimation(fig, update, frames=frame_indices, interval=1000 / base_fps, repeat=False)
        try:
            anim.save(str(output_path), writer=writer, dpi=dpi)
            logger.info("Export finished: %s", output_path)
        except FileNotFoundError as exc:
            logger.error("Export failed (is ffmpeg installed and in PATH for %s?): %s", suffix, exc)
            raise
        finally:
            plt.close(fig)
