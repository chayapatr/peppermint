from .core import build_core_env
from .math_ import build_math_env
from .ml import build_ml_env
from .viz import build_viz_env
from ..interpreter import Env


def build_global_env() -> Env:
    env = Env()

    # Core functions at top level
    for name, fn in build_core_env().items():
        env.set(name, fn)

    # Namespaced stdlib — pre-bound so ml.kmeans works without `use ml`
    env.set("ml",   build_ml_env())
    env.set("viz",  build_viz_env())
    env.set("math", build_math_env())

    # Also store under _ns_ prefix so `use ml` can find them
    env.set("_ns_ml",   build_ml_env())
    env.set("_ns_viz",  build_viz_env())
    env.set("_ns_math", build_math_env())

    return env
