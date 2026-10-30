# Optional route evidence

Use this reference only when the user or project explicitly requires a particular agent/model/effort route. The parent `SKILL.md` Scope discipline controls; route verification must not block unrelated requested work.

Keep requested configuration separate from observed runtime evidence. A profile file, dispatch argument, task name, or agent self-report does not prove which route ran. Report the route as unverified when the required runtime evidence is unavailable; do not claim a mismatch or create a blocker without evidence.

Do not switch to another profile, model, or effort as a fallback unless the user-authorized route allows it and a concrete need for that exact alternative is established. Do not install or modify Hooks or global configuration as part of route verification unless the user explicitly requests that change.
