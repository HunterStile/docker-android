import mock

from device.emulator import Emulator
from tests.device import BaseDeviceTest


class TestEmulator(BaseDeviceTest):
    def setUp(self) -> None:
        super().setUp()
        self.name = "my_emu"
        self.device = "Nexus 4"
        self.a_version = "10.0"
        self.d_partition = "550m"
        self.additional_args = ""
        self.i_type = "google_apis"
        self.s_img = "x86"
        self.emu = Emulator(self.name, self.device, self.a_version, self.d_partition,
                            self.additional_args, self.i_type, self.s_img)

    def tearDown(self) -> None:
        super().tearDown()

    def test_adb_name(self):
        my_emu = Emulator("my_other_emu", self.device, self.a_version, self.d_partition,
                          self.additional_args, self.i_type, self.s_img)
        self.assertNotEqual(self.emu.adb_name, my_emu.adb_name)

    def test_invalid_device(self):
        with self.assertRaises(RuntimeError):
            Emulator("my_other_emu", "unknown device", self.a_version, self.d_partition,
                     self.additional_args, self.i_type, self.s_img)
        with self.assertRaises(RuntimeError):
            Emulator("my_other_emu", "NEXUS 5", self.a_version, self.d_partition,
                     self.additional_args, self.i_type, self.s_img)

    def test_invalid_android_version(self):
        with self.assertRaises(RuntimeError):
            Emulator("my_other_emu", self.device, "0.0", self.d_partition,
                     self.additional_args, self.i_type, self.s_img)

    @mock.patch("os.path.exists", mock.MagicMock(return_value=False))
    def test_initialisation_config_not_exist(self):
        self.assertEqual(self.emu.is_initialized(), False)

    @mock.patch("os.path.exists", mock.MagicMock(return_value=True))
    @mock.patch("builtins.open", mock.mock_open(read_data=""))
    def test_initialisation_device_not_exist(self):
        self.assertEqual(self.emu.is_initialized(), False)

    @mock.patch("os.path.exists", mock.MagicMock(return_value=True))
    @mock.patch("builtins.open", mock.mock_open(read_data="hw.device.name=Nexus 4\n"))
    def test_initialisation_device_exists(self):
        self.assertEqual(self.emu.is_initialized(), True)

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("builtins.open", mock.mock_open(read_data="hw.device.name = pixel_8\n"))
    def test_initialisation_pixel_profile_exists(self, _exists):
        self.emu.device = "Pixel 8"
        self.assertTrue(self.emu.is_initialized())

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("builtins.open", mock.mock_open(read_data="hw.device.name = pixel_8\n"))
    def test_initialized_pixel_is_not_wiped(self, _exists):
        self.emu.device = "Pixel 8"
        with mock.patch("subprocess.Popen") as popen:
            self.emu.deploy()
        self.assertNotIn("-wipe-data", popen.call_args.args[0])

    def test_check_adb_command(self):
        with mock.patch("subprocess.check_output", mock.MagicMock(return_value="1".encode("utf-8"))):
            self.emu.check_adb_command(
                self.emu.ReadinessCheck.BOOTED, "mocked_command", "1", 3, 0)

    def test_popup_check_ignores_case(self):
        focus = b"mCurrentFocus=Application Not Responding: com.android.systemui"
        with mock.patch("subprocess.check_output", return_value=focus), \
                mock.patch("subprocess.check_call") as action:
            self.emu.check_adb_command(
                self.emu.ReadinessCheck.POP_UP_WINDOW, "mocked_command",
                "Not Responding: com.android.systemui", 2, 0,
                "adb shell input keyevent KEYCODE_ENTER")

        action.assert_called_once_with("adb shell input keyevent KEYCODE_ENTER", shell=True)

    def test_play_store_popup_does_not_require_root(self):
        self.emu.img_type = "google_apis_playstore"
        with mock.patch("time.sleep"), \
                mock.patch.object(self.emu, "check_adb_command") as check:
            self.emu.wait_until_ready()

        system_ui_check = check.call_args_list[1]
        self.assertEqual(system_ui_check.args[-1], "adb shell input keyevent KEYCODE_ENTER")
        readiness_check = check.call_args_list[-1]
        self.assertIn("pm path com.android.vending", readiness_check.args[1])

    def test_check_adb_command_out_of_attempts(self):
        with mock.patch("subprocess.check_output", mock.MagicMock(return_value=" ".encode("utf-8"))):
            with self.assertRaises(RuntimeError):
                self.emu.check_adb_command(
                    self.emu.ReadinessCheck.BOOTED, "mocked_command", "1", 3, 0)

    def test_deploy_preserves_spaces_in_quoted_additional_args(self):
        self.emu.additional_args = '-turncfg "cat /tmp/turn.cfg"'

        with mock.patch.object(self.emu, "is_initialized", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            self.emu.deploy()

        popen.assert_called_once_with([
            "emulator", "@my_emu", "-gpu", "swiftshader_indirect", "-accel", "on",
            "-writable-system", "-verbose", "-turncfg", "cat /tmp/turn.cfg"
        ])

    def test_play_store_image_starts_without_writable_system(self):
        self.emu.img_type = "google_apis_playstore"

        with mock.patch.object(self.emu, "is_initialized", return_value=True), \
                mock.patch("subprocess.Popen") as popen:
            self.emu.deploy()

        popen.assert_called_once_with([
            "emulator", "@my_emu", "-gpu", "swiftshader_indirect", "-accel", "on",
            "-verbose"
        ])

    def test_play_store_image_is_selected_when_creating_avd(self):
        self.emu.img_type = "google_apis_playstore"

        with mock.patch("device.Device.create"), \
                mock.patch.object(self.emu, "is_initialized", return_value=False), \
                mock.patch.object(self.emu, "_add_profile"), \
                mock.patch.object(self.emu, "_add_skin"), \
                mock.patch.object(self.emu, "_use_override_config"), \
                mock.patch("subprocess.check_call") as check_call:
            self.emu.create()

        creation_command = check_call.call_args.args[0]
        self.assertIn("-b google_apis_playstore/x86", creation_command)
        self.assertIn("system-images;android-29;google_apis_playstore;x86", creation_command)

    def test_play_store_avd_is_enabled(self):
        self.emu.img_type = "google_apis_playstore"
        with mock.patch("builtins.open", mock.mock_open()) as config:
            self.emu._add_skin()

        config().write.assert_any_call("PlayStore.enabled=yes\n")

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("subprocess.check_call")
    def test_change_permission_keeps_system_users(self, check_call, _exists):
        self.emu.change_permission()

        check_call.assert_called_once_with("sudo chown 1300:1301 /dev/kvm", shell=True)

    def test_use_override_config_no_env(self):
        with mock.patch("os.getenv", return_value=None):
            self.emu._use_override_config()

    def test_use_override_config_file_not_exist(self):
        with mock.patch("os.getenv", return_value="mock/path/to/config"):
            with mock.patch("os.path.isfile", return_value=False):
                self.emu._use_override_config()

    def test_use_override_config_file_not_readable(self):
        with mock.patch("os.getenv", return_value="mock/path/to/config"):
            with mock.patch("os.path.isfile", return_value=True):
                with mock.patch("os.access", return_value=False):
                    self.emu._use_override_config()

    def test_use_override_config_malformed_content(self):
        with mock.patch("os.getenv", return_value="mock/path/to/config"):
            with mock.patch("os.path.isfile", return_value=True):
                with mock.patch("os.access", return_value=True):
                    with mock.patch("builtins.open", mock.mock_open(read_data="malformed data")):
                        self.emu._use_override_config()
