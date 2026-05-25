from .core import build_core_env
from ..interpreter import Env
import importlib
from pathlib import Path


def load_stdlib(name: str) -> dict:
    """Load a lib namespace by name, autodiscovered from peppermint/libs/."""
    libs_path = Path(__file__).parent.parent / "libs"

    # Try exact name first, then with trailing underscore (e.g. math_)
    for candidate in [name, f"{name}_"]:
        mod_path = libs_path / f"{candidate}.py"
        if mod_path.exists():
            mod = importlib.import_module(f"peppermint.libs.{candidate}")
            # Find the build_*_env function
            for attr in dir(mod):
                if attr.startswith("build_") and attr.endswith("_env"):
                    return getattr(mod, attr)()

    raise KeyError(f"no lib '{name}' found in peppermint/libs/")


def build_global_env() -> Env:
    from ..interpreter import _ColProxy
    env = Env()
    for name, fn in build_core_env().items():
        env.set(name, fn)
    env.set("col", _ColProxy())
    return env
