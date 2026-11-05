This is the dev-env template for creating project-specific containerized development environments.
Remove this lines after customizing the Readme for your project.

# PROJECT_NAME

Describe the application and its users.

# Application Architecture

Describe the main parts of the application and their relations and interdependencies

# Repository layout

- `.devcontainer/` - config files for setting up an isolated DevContainer environment
- `_tooling/` - tooling and scripts for developer and agent assistance and consistent use of development tools
- `project.json` - project configuration file for generic development tooling
- `build-devcontainer.ps1` - PowerShell script for building the DevContainer environment on a Windows Host
- add project-specific directories and files as needed

# Development environment

The development environment is based on dev-env and provides a containerized
Linux environment for VS Code with Python, Node, Docker access, PowerShell and 
Codex with optional Context7 integration (off by default).

Details regarding tooling and developer support can be found in `/_tooling/Readme.md`.

# Production

Describe the production environment, deployment process, and any relevant operational details.
