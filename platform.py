# Copyright 2020-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from platform import system

from platformio.managers.platform import PlatformBase
from platformio.util import get_systype


class NxpimxrtPlatform(PlatformBase):

    def is_embedded(self):
        return True

    def configure_default_packages(self, variables, targets):
        if variables.get("board"):
            upload_protocol = variables.get("upload_protocol",
                                            self.board_config(
                                                variables.get("board")).get(
                                                    "upload.protocol", ""))
            if upload_protocol == "cmsis-dap":
                self.packages['tool-pyocd']['type'] = "uploader"
                
        if not variables.get("pioframework", []):
            # Temporary for MCUXpresso SDK
            self.packages['toolchain-gccarmnoneeabi']['version'] = "~1.80301.0"  
        elif "zephyr" in variables.get("pioframework", []):
            for p in self.packages:
                if p.startswith("framework-zephyr-") or p in (
                    "tool-cmake", "tool-dtc", "tool-ninja"):
                    self.packages[p]["optional"] = False
            self.packages['toolchain-gccarmnoneeabi']['version'] = "~1.80201.0"
            if "windows" not in get_systype():
                self.packages['tool-gperf']['optional'] = False

        # configure J-LINK tool
        jlink_conds = [
            "jlink" in variables.get(option, "")
            for option in ("upload_protocol", "debug_tool")
        ]
        if variables.get("board"):
            board_config = self.board_config(variables.get("board"))
            jlink_conds.extend([
                "jlink" in board_config.get(key, "")
                for key in ("debug.default_tools", "upload.protocol")
            ])
        jlink_pkgname = "tool-jlink"
        if not any(jlink_conds) and jlink_pkgname in self.packages:
            del self.packages[jlink_pkgname]

        return PlatformBase.configure_default_packages(self, variables,
                                                       targets)

    def get_boards(self, id_=None):
        result = PlatformBase.get_boards(self, id_)
        if not result:
            return result
        if id_:
            return self._add_default_debug_tools(result)
        else:
            for key, value in result.items():
                result[key] = self._add_default_debug_tools(result[key])
        return result

    def _add_default_debug_tools(self, board):
        debug = board.manifest.get("debug", {})
        upload_protocols = board.manifest.get("upload", {}).get(
            "protocols", [])
        if "tools" not in debug:
            debug['tools'] = {}

        # J-Link / BlackMagic Probe
        for link in ("blackmagic", "cmsis-dap", "jlink"):
            if link not in upload_protocols or link in debug['tools']:
                continue

            if link == "blackmagic":
                debug['tools']['blackmagic'] = {
                    "hwids": [["0x1d50", "0x6018"]],
                    "require_debug_port": True
                }

            elif link == "cmsis-dap":
                if debug.get("pyocd_target"):
                    pyocd_target = debug.get("pyocd_target")
                    assert pyocd_target
                    debug['tools'][link] = {
                        "onboard": True,
                        "server": {
                            "package": "tool-pyocd",
                            "executable": "$PYTHONEXE",
                            "arguments": [
                                "pyocd-gdbserver.py",
                                "-t",
                                pyocd_target
                            ]
                        }
                    }
                else:
                    openocd_target = debug.get("openocd_target")
                    assert openocd_target
                    debug['tools'][link] = {
                        "load_cmd": "preload",
                        "onboard": True,
                        "server": {
                            "executable": "bin/openocd",
                            "package": "tool-openocd",
                            "arguments": [
                                "-s", "$PACKAGE_DIR/scripts",
                                "-f", "interface/cmsis-dap.cfg",
                                "-f", "target/%s.cfg" % openocd_target
                            ]
                        }
                    }

            elif link == "jlink":
                assert debug.get("jlink_device"), (
                    "Missed J-Link Device ID for %s" % board.id)
                debug['tools'][link] = {
                    "server": {
                        "package": "tool-jlink",
                        "arguments": [
                            "-singlerun",
                            "-if", "SWD",
                            "-select", "USB",
                            "-device", debug.get("jlink_device"),
                            "-port", "2331"
                        ],
                        "executable": ("JLinkGDBServerCL.exe"
                                       if system() == "Windows" else
                                       "JLinkGDBServer")
                    },
                    "onboard": link in debug.get("onboard_tools", [])
                }

        board.manifest['debug'] = debug
        return board
