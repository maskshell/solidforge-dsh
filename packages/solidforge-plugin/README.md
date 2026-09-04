# solidforge

SolidForge on the DeepSeek Harness — the globally installed plugin face. Mounted
through a dsh profile's user patch layer, it gives sessions of **any preset**:

- the five SolidForge skills in the host skill layer (`/` menu + model catalog);
- `/solidforge:<skill>` colon gestures (full names or `pd`/`bc`/`csr`/`psv`/`pas`)
  with deterministic `<skill_content>` injection at the pre-step boundary —
  the plugin-ecosystem answer to Claude Code's `/plugin:skill` addressing;
- an additive `solidforge:discipline` system-prompt section (two-axis discipline
  + the abbreviation map), enabled with `config: { persona: true }`.

The same package can be mounted as a **solidforge preset row**
(`config: { commands: true, gestures: false, skills: false }`) to register the
`/solidforge`, `/arm-tools`, and `/solidforge-status` commands — the patch
layer's context cannot see the `commands`/`tools`/`subprocess` services (the
loader only bridges services declared in `inject`).

## Install

The package must be resolvable from the dsh profile and preset baseUrls:

```bash
mkdir -p "$DSH_HOME/node_modules/@maskshell"
npm install --prefix "$DSH_HOME" solidforge   # or copy the package there
```

Then mount it in the profile patch layer
(`$DSH_HOME/profiles/<profile>/cordis.patch.yml`, hot-reloaded):

```yaml
- insert:
    - id: solidforge
      name: 'solidforge'
      config:
        persona: true
```

Skill bodies are read LIVE from the installed solidforge preset
(`$DSH_HOME/.agent-presets/solidforge`) — the preset is the single source of
content; the plugin degrades honestly (skills unregistered, gestures skipped)
when it is absent. Runtime state (service visibility, registration counts,
per-phase errors) is reported by the `/solidforge-status` command and written
to `$DSH_HOME/.solidforge-status.json`.

Full source, the preset, the structural gate plugins, and the installer:
<https://github.com/maskshell/solidforge-dsh>

## License

Apache-2.0 (LICENSE and NOTICE included in this package)
