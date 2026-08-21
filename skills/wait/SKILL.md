---
name: wait
description: Use this skill whenever the requested result depends on a command, job, process, file, service, or external state becoming ready later. Load it before monitoring or checking for completion, including background work, unknown timing, and requests that never explicitly mention waiting.
---

# Wait

A wait cycle is simple: choose an interval, block in a terminal, observe, and
repeat if needed. Treat the interval as a disposable estimate.

1. Pick a useful interval from the available evidence. When evidence is weak,
   make a reasonable assumption. When overshooting has little cost, err long.
   After an estimate proves wrong, scale sharply from seconds to minutes rather
   than climbing through many short intervals.
2. Put the whole wait cycle inside one terminal call so the model stays
   inactive. Attach to an existing resumable terminal when work is already
   running. When readiness can be checked, use one condition loop with a
   generous deadline and terminal timeout. Do not wake the model between
   individual sleep-and-check pairs. Use a simple foreground `sleep` only when
   readiness is hard to observe.
3. When the terminal returns, inspect the current state. Treat an estimate as a
   hint, not a deadline: one missing result is not a failure. A submission
   command may delegate work elsewhere and never create the result itself. Do
   not replace waiting with broad searches or source inspection merely because
   output is late. Unless there is explicit evidence of failure or a
   task-specific stopping point, start another blocking wait immediately. Do
   not return a status message that only promises to keep waiting.

If the terminal tool yields a session or terminal ID, reattach to that exact ID
for the next interval. A condition-based waiter may return as soon as useful
state changes. A simple timer is also valid when readiness is hard to observe.

Wake the model when the interval expires or the waiter observes a useful state
change.
