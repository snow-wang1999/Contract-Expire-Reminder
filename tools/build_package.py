"""打包离线版：内置 Windows 版 Python 和全部依赖，解压后双击 启动.bat 即可运行，无需联网安装。

用法（在任意能联网的机器上执行一次）：
    python tools/build_package.py [输出 zip 路径]

- Python：来自 Python 官方在 NuGet 发布的 python 包（Windows x64 完整版，带签名）
- 依赖：pip 下载 Windows 版 wheel，直接解压到内置 Python 的 site-packages
"""
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

PY_VERSION = "3.12.10"
NUGET_URL = f"https://api.nuget.org/v3-flatcontainer/python/{PY_VERSION}/python.{PY_VERSION}.nupkg"
PY_TAG = "3.12"
PACKAGES = ["flask", "openpyxl", "comtypes", "colorama", "waitress"]   # colorama 是 click 在 Windows 上的依赖

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
CACHE = os.path.join(BUILD, "cache")
NAME = "Contract-Expire-Reminder"

# 运行用不到的部分，减小体积
TRIM = ["include", "libs", "Lib/ensurepip", "Lib/idlelib", "Lib/turtledemo", "Lib/test", "Lib/lib2to3",
        "Lib/tkinter", "Lib/venv", "Lib/pydoc_data"]


def fetch_python():
    nupkg = os.path.join(CACHE, f"python.{PY_VERSION}.nupkg")
    if not os.path.exists(nupkg):
        print("下载 Python", PY_VERSION, "…")
        urllib.request.urlretrieve(NUGET_URL, nupkg)
    return nupkg


def fetch_wheels():
    wheels = os.path.join(CACHE, "wheels")
    os.makedirs(wheels, exist_ok=True)
    print("下载依赖 wheel …")
    subprocess.check_call([sys.executable, "-m", "pip", "download", "--quiet", "--only-binary=:all:",
                           "--platform", "win_amd64", "--python-version", PY_TAG, "--implementation", "cp",
                           "-d", wheels, *PACKAGES])
    return sorted(os.path.join(wheels, f) for f in os.listdir(wheels) if f.endswith(".whl"))


def project_files():
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode()
    return [f for f in out.split("\0") if f and not f.startswith(("tests/", "tools/")) and f != "conftest.py"]


def main():
    target = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(BUILD, f"{NAME}.zip")
    os.makedirs(CACHE, exist_ok=True)
    stage = os.path.join(BUILD, NAME)
    shutil.rmtree(stage, ignore_errors=True)

    runtime = os.path.join(stage, "runtime", "python")
    with zipfile.ZipFile(fetch_python()) as z:
        for info in z.infolist():
            if info.filename.startswith("tools/") and not info.is_dir():
                dest = os.path.join(runtime, info.filename[len("tools/"):])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(info) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    for rel in TRIM:
        shutil.rmtree(os.path.join(runtime, rel), ignore_errors=True)
    site = os.path.join(runtime, "Lib", "site-packages")
    for entry in os.listdir(site):
        if entry.startswith("pip"):
            shutil.rmtree(os.path.join(site, entry), ignore_errors=True)
    for whl in fetch_wheels():
        with zipfile.ZipFile(whl) as z:
            z.extractall(site)

    for rel in project_files():
        dest = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), dest)

    # Python 的 zipfile 会为中文文件名自动设置 UTF-8 标志，Windows 资源管理器解压不会乱码
    if os.path.exists(target):
        os.remove(target)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder, _, files in os.walk(stage):
            for f in files:
                path = os.path.join(folder, f)
                z.write(path, os.path.relpath(path, BUILD))
    print("已生成", target, f"{os.path.getsize(target) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
