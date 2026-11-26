# Pi setup for L0

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
