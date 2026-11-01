# INF Nickname Bot

When a member joins a configured server, the bot sets their server nickname to
`INF NAME`, uppercased and rendered with Unicode monospace-style letters.
For example, `Ayush Sharma` becomes `𝙸𝙽𝙵 𝙰𝚈𝚄𝚂𝙷 𝚂𝙷𝙰𝚁𝙼𝙰`.
The name comes from the member's Discord profile display name; if they have
not set one, the bot falls back to their Discord username. A server nickname
is not used as the source.

The nickname is truncated to Discord's 32-character limit. Running `/setup`
enables automatic nickname formatting for members who join after setup.
Existing members' nicknames are not changed.

## Discord setup

1. In the Discord Developer Portal, enable **Server Members Intent** for the bot.
2. Invite the bot with the **Manage Nicknames** permission and **Use Application
   Commands** permission.
3. Move the bot's highest role above the members whose nicknames it should set.
4. Run `/setup` in each server. The user running it needs **Manage Server**.

## Deploy on Render

Deploy this folder as a Render Blueprint. The included `render.yaml` sets:

- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Python 3.11.11 and `/healthz` health check

Add only one required secret in Render: `TOKEN`, the Discord bot token. Render
provides `PORT`; no other environment variables or API keys are required.

The settings database is stored in `data/settings.sqlite3`. Render's free
filesystem is temporary; attach a persistent disk at `/opt/render/project/src/data`
if per-server setup should survive service restarts and redeploys.

## Run locally

Install dependencies with `pip install -r requirements.txt`, set `TOKEN`, then
run `python bot.py`.
