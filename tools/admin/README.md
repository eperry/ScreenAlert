# Admin command runner

Runs arbitrary commands elevated on Windows without a UAC popup on every
call, by pre-registering a Scheduled Task once (which itself needs one
UAC prompt) and then triggering that task on demand.

## Setup (one time)

Right-click `admin-setup.bat` -> **Run as administrator**. This registers a
Scheduled Task named `ScreenAlertAdminRunner` that runs
`admin-runner.bat` with highest privileges. The task is created with a
trigger date in the past so it never fires on its own — it only runs when
explicitly started.

## Usage

```bat
admin-run.bat "your command here"
```

Example:

```bat
admin-run.bat "ipconfig /all"
```

This writes the command to `admin-command.txt`, triggers the scheduled
task (`schtasks /run`), waits for it to finish, and prints the captured
output from `admin-output.log`.

## How it avoids the UAC popup

Windows only prompts for UAC consent when a process asks to elevate
*interactively*. Starting an already-registered Scheduled Task that is
configured to run at the "Highest privileges" level does not go through
that interactive consent dialog — the one-time admin approval happened
when the task was registered in `admin-setup.bat`.

## Security notes

- Any command written to `admin-command.txt` runs with full administrator
  rights on this machine. Treat `admin-run.bat` like a root shell: don't
  let untrusted input reach it, and don't leave the machine unattended
  while set up this way.
- To remove the task: `schtasks /delete /tn ScreenAlertAdminRunner /f`.
- `admin-command.txt`, `admin-output.log`, and `admin-status.txt` are
  runtime scratch files (git-ignored) — don't commit them.
