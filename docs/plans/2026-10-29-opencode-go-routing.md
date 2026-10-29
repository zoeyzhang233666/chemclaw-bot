# OpenCode Go native routing

ChemClaw's Go preset explicitly sets `api: openai-completions`. DSH rc.3's
documented provider configuration treats this as a protocol override, bypassing
Pi's built-in OpenCode provider and its `x-opencode-session` wrapper. The saved
key and model listing therefore do not prove that a conversation can run.

Use DSH's catalog provider without a route protocol, endpoint or imported model
list. The installed catalog supplies each model's native protocol, endpoint and
session-header implementation. This adopts the official dependency's existing
fix; it requires no DSH patch or new adapter. Older DSH installations without the
built-in provider receive an update message rather than another generic route.

Before model discovery or an Agent request, migrate the exact legacy ChemClaw
preset through the public settings service. Remove its protocol, endpoint and
imported model list, preserving its credential reference and other controls.
Concurrent callers share one migration. Custom endpoints, base-profile overrides
and differently named or configured routes are left alone. The available models
now follow DSH's catalog. A selected Go model missing from that catalog stops the
migration with an update message instead of falling back to another provider.
Model availability and Go account permissions still belong to Go.

Validate against DSH's public plugin API using intercepted synthetic HTTP requests
and the existing mock bench. No real credentials or user DSH data are accessed.
This change addresses main conversation routing; auxiliary callers must still
pass their Session ID, including upstream Auto review paths.

The official Pi 1.3 release contains the native-provider wrapper. Pi 1.4 also
adds transport identity handling to the generic protocol path, so the legacy
preset can already work on a newer dependency installation. Exercise the native
route with both official versions; do not claim every rc.3 installation fails.

References:
- https://github.com/deepseek-ai/deepseek-harness/discussions/5495
- https://opencode.ai/v2/docs/console/go/#where-can-i-use-it
