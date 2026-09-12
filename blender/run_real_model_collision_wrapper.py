import runpy
import sys

if "--" in sys.argv:
    sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("--") + 1:]
else:
    raise SystemExit("BLENDER_SCRIPT_ARGUMENT_SEPARATOR_MISSING")

runpy.run_path("blender/real_model_collision_test.py", run_name="__main__")
