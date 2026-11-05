# Development tooling

## DevContainer

### Prerequisites

- A checkout on the WSL Linux filesystem, such as `/work/project1`, and WSL Git.
  Project and checkout folder names are assumed to be valid identifiers.
- A Linux Docker engine accessible from WSL. For Docker Desktop, enable WSL
  integration; for a native WSL engine, give the WSL user access to its socket.
  Check `docker info` in WSL. The daemon must see the checkout and its bind paths.
- Windows PowerShell 7 and Windows VS Code with the WSL and Dev Containers extensions.
- A Windows `devcontainer` application on PATH, or Windows Node/npm providing
  `npx`. Bootstrap prefers `devcontainer` and otherwise runs
  `npx -y @devcontainers/cli`. The optional CLI installation through VS Code is
  described in the [official CLI guide](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli).
- Docker access for the Windows CLI runner. Windows and WSL Docker commands must
  address the same Linux engine; Docker Desktop WSL integration provides this setup.
- Context7 is optional and off by default. Set a non-empty `CONTEXT7_API_KEY` on the
  system where bootstrap runs to enable it.

### Copy, configure and open

1. Copy the template into the new project's checkout. The files should reside on a WSL Linux 
   filesystem path, which can either be accessed via UNC paths or mounted drive letters. Edit
   [project.json](../project.json) to set its name and tool versions.

2. From Windows PowerShell 7, run:

   ```powershell
   Set-Location '\\wsl.localhost\Debian\work\project1'
   .\build-devcontainer.ps1
   ```
   This re-creates the DevContainer configuration `.devcontainer/devcontainer-compose.yaml` 
   and updates `.devcontainer/devcontainer.json` and then builds the DevContainer.  
     
3. Open the project root in a **VS Code WSL window** and choose **Dev Containers:
   Reopen in Container**. The Debian Trixie container provides Python, Node, PowerShell 7 LTS,
   Docker access and the language, Docker, PowerShell and Codex extensions.

The configured project name controls workspace/resource names. For `projectName: "project1"`:

| Setting | Value | 
| --- | --- |
| VS Code display name | `project1` |
| Container workspace | `/workspaces/project1` |
| Compose project/container prefix | `project1_devc` |
| Local image | `project1_build_devcontainer:local` |
| Shared runtime network | `project1_default` |

### Additional info

- For standalone CLI's `--no-lockfile` option is used to avoid the automatic lockfile-path 
  bug on Windows UNC shares. 
- A rebuild of the DevContainer within VSCode should work after the config was
  created/updated by `build-devcontainer.ps1`.
- Docker-outside-of-Docker owns socket access and non-root permissions
- The config uses Docker CE packages (`moby: false`) for Trixie compatibility.
- Bootstrap includes the `CONTEXT7_API_KEY` environment entry only when its host
  variable is non-empty; otherwise it omits the entry entirely. Rerun bootstrap
  after changing whether Context7 is enabled. For VS Code rebuilds with Context7
  enabled, the variable must be visible to the process running Compose.
- The workspace joins its normal Compose network and the external shared runtime
  network. Bootstrap creates the latter if absent and reuses it thereafter; 
  runtime containers can join it; 
- The workspace also resolves `host.docker.internal` through Docker's host gateway. 
- Seccomp, Codex sandbox mode and approval policy use their normal defaults.
- `-WslPath` selects another WSL UNC checkout, including a mapped WSL drive.
- `-NoCache` rebuilds without cached layers. 
- Codex CLI and extension share `$CODEX_HOME/config.toml`. Defaults are created only 
  when that file is missing; subsequent runs preserve all personal settings and MCP
  entries. New configuration includes Context7 only when bootstrap has a non-empty
  key. Existing configuration is never changed: previously saved Context7 entries
  remain in the mounted state, and enabling Context7 later requires adding its MCP
  entry manually if the configuration was initially created without it.

## Personal state

| Path under `.local/devcontainer/` | Container path | Contents |
| --- | --- | --- |
| `vscode/` | `/home/vscode/.vscode-server` | Stable settings, extensions and extension state. |
| `vscode-insiders/` | `/home/vscode/.vscode-server-insiders` | Corresponding Insiders state. |
| `codex/` | `/home/vscode/.codex` (`CODEX_HOME`) | Codex settings, sessions and file-based authentication. |

The WSL user creates missing state directories privately (mode `700`) and a missing
Codex configuration with mode `600`. Private state stays out of Git and Docker build contexts. 

Use **Remote Settings** for personal VS Code settings and `$CODEX_HOME/config.toml`
for Codex settings. 
