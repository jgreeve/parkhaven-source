"""Register this development plug-in for the current Windows user only."""

import argparse
from pathlib import Path
import winreg


PLUGIN_ID = "7ff947f5-d80c-4be6-bc9b-88f77bdfe605"
KEY = rf"Software\McNeel\Rhinoceros\8.0\Plug-ins\{PLUGIN_ID}"
DEFAULT = Path(__file__).resolve().parents[1] / "rhino-plugin/bin/Release/net7.0-windows/ParkHaven.Rhino.rhp"


def register(path: Path) -> None:
    path = path.resolve(strict=True)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        winreg.SetValueEx(key, "Name", 0, winreg.REG_SZ, "ParkHaven")
        winreg.SetValueEx(key, "FileName", 0, winreg.REG_SZ, str(path))
        winreg.SetValueEx(key, "LoadMode", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "IsDotNETPlugIn", 0, winreg.REG_DWORD, 1)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY + r"\PlugIn") as key:
        winreg.SetValueEx(key, "FileName", 0, winreg.REG_SZ, str(path))
    print(f"Registered ParkHaven plug-in: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=DEFAULT)
    register(parser.parse_args().plugin)
