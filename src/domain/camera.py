from dataclasses import dataclass, field

__all__ = ["CameraInfo", "CameraMode"]


@dataclass(frozen=True, slots=True)
class CameraMode:
    width: int
    height: int
    fps: int
    fourcc: str

    def __repr__(self):
        return f"{self.width}x{self.height} @ {self.fps} fps ({self.fourcc})"


@dataclass
class CameraInfo:
    index: int  # Системный индекс камеры (порядок DirectShow)
    name: str
    modes: list[CameraMode] = field(default_factory=list)

    def __repr__(self):
        return f"Устройство {self.index:02d}: {self.name}"
