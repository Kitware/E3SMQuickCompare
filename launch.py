import sys
import os
import venv
import traceback
from subprocess import run


def setup_env():
    workdir = os.path.abspath(os.path.dirname(__file__))
    print("Workdir : ", workdir)
    env = os.path.join(workdir, ".pvenv")
    try:
        if os.path.exists(env):
            return True
        else:
            venv.create(env, with_pip=True)
            run(["bin/pip", "install", "--prefer-binary", workdir], cwd=env)
    except Exception as e:
        print("Error occurred while trying to access environment ", e)
        traceback.print_exc()
        return False


if __name__ == "__main__":
    workdir = os.path.abspath(os.path.dirname(__file__))
    app_path = os.path.join(workdir, "src", "e3sm_compareview", "app.py")

    setup_env()
    eampv = os.environ.get("EAMPVIEW")
    if eampv is None or len(eampv) == 0:
        print(
            "Env. variable 'EAMPVIEW' to point to ParaView python 'pvpython' not set/found"
        )
        exit(1)

    args = [
        eampv,
        "--force-offscreen-rendering",
        app_path,
        "--venv",
        os.path.join(workdir, ".pvenv"),
    ]
    args.extend(sys.argv[1:])

    try:
        run(args)
    except Exception as e:
        print(e)
        exit(1)
