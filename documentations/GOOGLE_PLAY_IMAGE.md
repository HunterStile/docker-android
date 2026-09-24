# Optional Google Play system image

The published Docker-Android emulator images install a `google_apis` system image. This provides Google Play services, but not the Google Play Store. A locally built image can instead install the Android SDK's `google_apis_playstore` system image. This path is experimental and requires a host that exposes `/dev/kvm` to Docker.

For two Pixel 8 emulators, use a Linux host or VM with at least 8 vCPUs; 12 GB of RAM is a sensible starting point. Both phones booted in a nested KVM test with 8 GB RAM plus 4 GB swap, but the VM used about 2 GB of swap during the second phone's first boot. The example sets four guest CPUs per phone because the default two CPUs produced repeated Android service timeouts in that test. Monitor memory and swap before adding more phones.

Google's [system image documentation](https://developer.android.com/tools/releases/platforms) explains the difference between Google APIs and Google Play images. Google Play system images are signed with release keys, so Android root access is unavailable; see [Create and manage virtual devices](https://developer.android.com/studio/run/managing-avds). This build does not attempt to install Play Store APKs into another system image.

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

The CPU setting in `example/multiple-emulators/avd-config.ini` is applied when each AVD is first created. Changing it later does not rewrite an existing AVD config. To apply a different CPU count to an existing phone, stop its container and edit `hw.cpu.ncore` in that phone's `emulator/config.ini` inside its named volume, then recreate the container while keeping the volume.

The image build, concurrent boot of both phones, and opening the unauthenticated Play Store were verified on a nested KVM VM. Google account sign-in and account persistence have not been verified; each account owner must sign in through the Android UI. Before describing Play Store support as stable, verify that separate accounts can sign in and both sessions survive a restart.
