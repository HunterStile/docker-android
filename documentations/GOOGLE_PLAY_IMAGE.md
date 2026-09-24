# Optional Google Play system image

The published Docker-Android emulator images install a `google_apis` system image. This provides Google Play services, but not the Google Play Store. A locally built image can instead install the Android SDK's `google_apis_playstore` system image. This path is experimental and requires a host that exposes `/dev/kvm` to Docker.

For two Pixel 8 emulators, use a Linux host or VM with at least 8 vCPUs; 12 GB of RAM is a sensible starting point. Both phones booted in a nested KVM test with 8 GB RAM plus 4 GB swap, but the VM used about 2 GB of swap during the second phone's first boot. The example sets four guest CPUs per phone because the default two CPUs produced repeated Android service timeouts in that test. Monitor memory and swap before adding more phones.

Google's [system image documentation](https://developer.android.com/tools/releases/platforms) explains the difference between Google APIs and Google Play images. Google Play system images are signed with release keys, so Android root access is unavailable; see [Create and manage virtual devices](https://developer.android.com/studio/run/managing-avds). This build does not attempt to install Play Store APKs into another system image.

The Play image uses the emulator's `software` graphics mode. The repository's existing `swiftshader_indirect` mode is retained for its default images; Android's [graphics acceleration guide](https://developer.android.com/studio/run/emulator-acceleration) lists that mode as deprecated in current emulator releases.

On Linux, Emulator 37.1.11 selects `gles_swangle` for software GLES rendering but ships the ANGLE libraries in `gles_angle`. The Play image adds the missing directory alias when needed. Without it, the emulator silently falls back to legacy SwiftShader GLES; opening the signed-in Play Store reproduced a `RenderThread` SIGSEGV in that configuration. Disabling Vulkan alone did not prevent the crash.

## Build

From the repository root on a Linux Docker host with KVM and Docker Buildx/BuildKit:

```sh
DOCKER_BUILDKIT=1 docker build -f docker/base -t budtmo/docker-android:base_local .
DOCKER_BUILDKIT=1 docker build -f docker/emulator \
  --build-arg DOCKER_ANDROID_VERSION=local \
  --build-arg EMULATOR_ANDROID_VERSION=14.0 \
  --build-arg EMULATOR_API_LEVEL=34 \
  --build-arg EMULATOR_IMG_TYPE=google_apis_playstore \
  -t docker-android:playstore-14.0 .
```

The `EMULATOR_IMG_TYPE` build argument defaults to `google_apis`, preserving the existing image behavior. The public CLI is installed directly by the Dockerfile. The optional `extension.sh` build secret is still used when supplied, but a local build no longer requires that file.

## Run two independent phones

```sh
docker compose -f example/multiple-emulators/docker-compose.yml up -d
```

Open `http://localhost:6080` and `http://localhost:6081`. Each service has its own container and persistent volume. Sign in to the desired Google account through the Android UI on each phone. Do not put account passwords in the Compose file or environment variables. To check startup, use `docker compose -f example/multiple-emulators/docker-compose.yml logs phone-one` and the equivalent command for `phone-two`.

When Docker runs on a remote Linux host, forward the two loopback ports from your own computer before opening those URLs:

```sh
ssh -L 6080:127.0.0.1:6080 -L 6081:127.0.0.1:6081 user@linux-host
```

The example disables user behavior analytics for a locally modified build, consistent with the fork requirement in [LICENSE.md](../LICENSE.md).

The volumes retain app and account data across container restarts. A new volume starts a new phone; using the same volume in both services would mix their data. Changing the Android version or system image on an existing volume may require creating a new volume and signing in again.

After rebuilding the image, recreate one phone while retaining its named volume:

```sh
docker compose -f example/multiple-emulators/docker-compose.yml up -d --no-deps --force-recreate phone-two
```

This also gives the display server a fresh container filesystem; a plain container restart left a stale X11 lock during testing. Do not remove the named volumes to recover from a runtime crash. Keep the same device profile and system image when reusing existing account data.

Check Android responsiveness directly:

```sh
docker compose -f example/multiple-emulators/docker-compose.yml exec phone-two \
  timeout 15 adb -s emulator-5554 shell getprop sys.boot_completed
```

The result should be `1`. A working noVNC page or a saved `READY` status alone is insufficient: both remained present after QEMU crashed in testing.

The CPU setting in `example/multiple-emulators/avd-config.ini` is applied when each AVD is first created. Changing it later does not rewrite an existing AVD config. To apply a different CPU count to an existing phone, stop its container and edit `hw.cpu.ncore` in that phone's `emulator/config.ini` inside its named volume, then recreate the container while keeping the volume.

## Control a phone with ADB

Each container has its own ADB server and a device named `emulator-5554`. Select the phone by its Compose service, even though both devices have the same ADB serial. The example publishes only the loopback noVNC ports; it does not expose ADB over the network.

From the repository directory on the Docker host:

```sh
docker compose -f example/multiple-emulators/docker-compose.yml exec phone-two \
  adb -s emulator-5554 shell
```

At the Android prompt, such as `emu64xa:/ $`, run Android commands directly:

```sh
input keyevent KEYCODE_HOME
input tap 500 800
input text "EXAMPLE123"
input keyevent KEYCODE_ENTER
input swipe 500 1500 500 500 500
```

Focus the desired text field before using `input text`. Simple ASCII text is the most reliable; use `%s` for a space, for example `input text "hello%sworld"`. Use the Android UI for passwords and account sign-in. Exit the Android shell with `exit`.

Do not type `adb shell` again inside the Android shell: `adb` is a host tool and is not installed inside Android. For a single command from the Docker host, keep the complete prefix:

```sh
docker compose -f example/multiple-emulators/docker-compose.yml exec phone-two \
  adb -s emulator-5554 shell input keyevent KEYCODE_HOME
```

From PowerShell or another terminal on your computer, SSH can run the container's ADB without installing ADB locally. For the default Compose project name:

```sh
ssh -t user@linux-host "sudo docker exec -it multiple-emulators-phone-two-1 adb -s emulator-5554 shell"
```

Replace `phone-two` with `phone-one` to control the other phone. Replace `user@linux-host` with your SSH destination; omit `sudo` if that user already has Docker access.

## Validation scope

The Android 14 Play image was tested with Emulator 37.1.11 on an Ubuntu 24.04 VM with nested KVM. Both phones ran concurrently with separate volumes. After the ANGLE correction, the signed-in phone completed an initial run of over 12 minutes, including manual Play Store use. Its session then survived container recreation and 22 navigation cycles over another 10 minutes with Vulkan enabled. QEMU remained active, ADB responded, rendering counters advanced, and neither container reported an OOM kill. The image build and 32 CLI unit tests also passed.

This remains an experimental configuration tested on one host. Two distinct authenticated sessions and longer-term stability still require validation by the account owner; sign in through the Android UI and verify that both sessions survive recreation.
