from dataclasses import dataclass

__all__ = ["CameraMode"]


@dataclass(frozen=True, slots=True)
class CameraMode:
    width: int
    height: int
    fps: int
    fourcc: str

    def __repr__(self):
        return f"{self.width}x{self.height} @ {self.fps} fps ({self.fourcc})"
