import unittest
from pathlib import Path
from unittest.mock import patch

import db


class DataDirTests(unittest.TestCase):
    def data_dir(self, platform, env):
        with patch("sys.platform", platform), patch.dict("os.environ", env):
            return db._data_dir()

    def test_windows_uses_appdata(self):
        self.assertEqual(self.data_dir("win32", {"APPDATA": r"C:\x"}),
                         Path(r"C:\x") / "BierKoning")

    def test_macos_uses_application_support(self):
        self.assertEqual(self.data_dir("darwin", {}),
                         Path.home() / "Library" / "Application Support" / "BierKoning")

    def test_linux_honours_xdg_data_home(self):
        self.assertEqual(self.data_dir("linux", {"XDG_DATA_HOME": "/data"}),
                         Path("/data") / "bierkoning")

    def test_linux_defaults_to_local_share(self):
        self.assertEqual(self.data_dir("linux", {"XDG_DATA_HOME": ""}),
                         Path.home() / ".local" / "share" / "bierkoning")


if __name__ == "__main__":
    unittest.main()
