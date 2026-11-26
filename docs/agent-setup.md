# L0 setup in the experiment VM

## VM host tools

Run the host setup after [VM provisioning](../experiment/setup/provision-vm.sh).
It installs the tools needed to start L0 through the original Linux launcher,
which uses the Dev Containers CLI to build and start the workspace, apply the
configured Features, and run the post-create hook.

| Host tool | Version or requirement |
| --- | --- |
| Bash | 4.4 or newer. The launcher and state helper use Bash. |
| Python 3 | 3.6 or newer for the launcher's f-strings. The VM has 3.14.4. JSON rendering uses the standard library. |
| GNU coreutils | Ubuntu's version provides `env`, `dirname`, `cat`, `mkdir`, and the CLI's `id` fallback. |
| Docker CLI and Linux Engine | The launcher requires access to the daemon. The VM has Engine 29.10.0. |
| Docker Compose and Buildx plugins | Provided by VM provisioning. The CLI builds and starts the Compose service and probes Buildx. Use `docker compose version` and `docker buildx version` for the installed versions. |
| Node.js | The CLI requires Node.js 20.0.0 or newer. Setup pins 24.22.3 LTS. [Release notes](https://nodejs.org/en/blog/release/v24.22.3) |
| npm and npx | Both are bundled with Node.js. npm 11.19.1 installs the CLI. The launcher uses npx only if it cannot find `devcontainer`. |
| Dev Containers CLI | Setup pins `@devcontainers/cli` 0.91.0, the version returned by `npm view @devcontainers/cli version` on 2026-11-26. |

`jq` and Git are also provisioned for the VM. The L0 Compose launch path runs
without either. PowerShell and the post-create tools run inside the container.

The [host setup script](../experiment/setup/setup-devcontainer-cli.sh)
downloads the official Linux x64 Node.js tarball, verifies it against the
release's `SHASUMS256.txt`, and installs it under `/usr/local`. It installs the
published CLI globally with `--ignore-scripts` and installs any missing apt
packages for the launcher or the installer. The installer uses `curl` and the
system CA certificates for HTTPS, `awk` and `sha256sum` for verification, and
`tar` with `xz` for extraction. It prints the Node.js, npm, and Dev Containers
CLI versions and updates their entries in `/work/vm-info.txt` on each run.

## Start L0 and verify the workspace

Run the following in the VM as the provisioning user. If the user was just
added to the `docker` group, log out and back in first.

```bash
cd /work/graded-containment
sudo bash experiment/setup/setup-devcontainer-cli.sh
tail -n 3 /work/vm-info.txt

docker info --format '{{.ServerVersion}}'
env -u CONTEXT7_API_KEY bash template/base/build-devcontainer.sh
```

Press Enter at the launcher's prompt. After it finishes, confirm that Compose
lists the `workspace` service with status `Up`.

```bash
docker compose -f template/base/.devcontainer/devcontainer-compose.yaml \
  ps --status running workspace
```

## Pi setup for L0

The Linux bootstrap reads `template/base/project.json`, generates the Compose configuration, and starts the workspace through the Dev Containers CLI. The Dockerfile copies Node.js from `node:24-trixie-slim` into the Python 3.14 image. Compose selects npm 11. The baseline post-create hook verifies the toolchain and installs Codex.

The experiment installs `@earendil-works/pi-coding-agent@1.6.0` separately. npm reports `engines.node` as `>=22.19.0`, which L0's Node.js 24 satisfies. The npm install pins Pi itself. The package README notes that transitive dependencies can still vary.

Run this from the repository root in the VM after the L0 `workspace` service starts.

```bash
docker compose -f template/base/.devcontainer/devcontainer-compose.yaml \
  exec -T --user vscode -e HOME=/home/vscode workspace bash -s \
  < experiment/agent/install-pi.sh
```

The host shell streams the script into the container. The installer uses `~/.local` as the npm global prefix and verifies `~/.local/bin/pi --version`. A second run reports that the pinned version is already installed.

Pi stores user state under `~/.pi/agent` by default. Sessions go in `~/.pi/agent/sessions/`. A later `/login` saves credentials in `~/.pi/agent/auth.json`.

Pi can refresh its model catalog from `pi.dev` at startup. It also checks for updates to Pi and installed Pi packages, and enables anonymous install/update reporting by default. The separate `enableAnalytics` setting defaults to `false`.

The installer sets `PI_OFFLINE=1` to suppress startup network activity and `PI_TELEMETRY=0` to disable install/update reporting and selected provider attribution headers during version verification. Set both variables in the environment of later experiment runs as well. See the installed package's `docs/environment-variables.md`, `docs/settings.md`, and `docs/models.md`.
