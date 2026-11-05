# Coding agent instructions

This is a project with standard generic development environment setup based on the dev-env template. 

Read applicable `AGENTS.md` files, the [project README](Readme.md), and the [tooling guide](/_tooling/Readme.md) 
before changing the application or environment. When working on a specific part of the project in a 
subdirectory, also read the `AGENTS.md` file in that subdirectory.

## Workflow

You should run any command only inside a DevContainer. Use `pwd && python --version && node --version`
if in doubt to make sure the DevContainer is set up correctly with the working directory in
`/workspaces/<projectname>` with Python and NodeJS available. If you are
running in a different environment, tell the user and ask for explicit permission
before continuing. The only exception are commands reading or modifying files in the
current git working directory.

Do not modify any files outside of the current git working directory unless explicitly required
by the user. Specifically do not automatically stage, commit or push any changes. Always ask for explicit
permission before doing so.

Do not run any commands for building or deploying production artifacts. These are operator actions,
agents always have to use the local development environment.

## Change Discipline

- Identify, review and discuss implementation choices during development; do not treat unspecified 
  details as architectural constraints.
- When working on specifications, keep the content architectural, do not anticipate implementation
  details or decisions. These are to be discussed and approved with the operator during implementation.
- When creating new functions or refactor/change code, first analyse similar code in the same file or
  related files and try to follow existing patterns and conventions. If there are no relevant patterns,
  ask the user for explicit instructions on architecture/style/layout decisions.
- When changing or refactoring code or scripts and there are legacy parts that are no longer relevant,
  double check if they could be used somewhere else and then inform the user and ask for explicit
  permission to remove them.  
- Avoid splitting code into small one-time used inline functions. 
- Document long methods with section headers identifying the purpose of logical sections.
- Keep changes scoped to the requested task and preserve unrelated user changes.
- Protect credentials and private state. Do not print secret values, generate real credential files, 
  authenticate for the user or reset state as automatic recovery.
- Use the smallest meaningful verification for the change and complete relevant required checks. 
- Preserve test intent and report unavailable checks honestly.
- When creating or updating documentation, keep it concise and focused on the rationale behind
  decisions rather than repeating code details. Do not duplicate information in multiple locations,
  link to the relevant documentation or code instead.
- When refering to files in documentation or comments that are not in the same directory,
  use absolute paths relative to the repository root.
- Keep Readme's focused on high-level developer information, don't duplicate low-level details. 
- Keep changes to AGENTS.md small and focused to decisions that cannot be deduced from code or 
  other documentation. Approve changes with the operator. Do not duplicate information between
  Readmes and AGENTS.md.
- Keep concerns separated between different modules/subprojectsunless the task explicitly crosses them.
- Do not commit real local `.env` files. Update `.env.example` files instead.
- Preserve UTF-8, German characters and intentional legacy encodings
- Avoid unrelated formatting changes, dependency upgrades and code refactoring not relevant 
  to the current task.
