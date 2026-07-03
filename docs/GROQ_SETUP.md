# How to get and install your own Groq API key (a guide for everyone)

🇮🇹 **[Versione italiana](GROQ_SETUP.it.md)**

SudoBat's **AI turbo** is optional: it analyzes crashes the offline engine doesn't recognize yet. To use it you need a **personal Groq API key** — it's **free**, takes 5 minutes to get and **requires no credit card**.

> **Why a "personal" key?** API keys carry usage limits tied to their owner. If everyone shared the same key, those limits would run out immediately. With YOUR own key the limits are all yours — and for what SudoBat does with it (one call only when a game crashes in an unknown way) the free tier is more than plenty.

---

## Part 1 — Getting the key (from your PC or phone)

1. Open your browser and go to **https://console.groq.com**
2. Click **Sign up**. You can use your Google/GitHub account or any email — with email, you'll receive a confirmation message: open it and click the link.
3. Once inside, find **API Keys** in the menu and open it.
4. Click **Create API Key**. Name it whatever you like, e.g. `SudoBat`.
5. The key is shown to you: a long string that **starts with `gsk_`**.
   **⚠ Copy it IMMEDIATELY** (copy button next to it): for security, Groq shows it **only this once**. Losing it is no drama — you just create another one the same way.
6. Paste it somewhere safe for now (a note on your phone, a text file). Treat it like a password: **don't publish it, don't share it**.

Done. Now it needs to get onto the Batocera box.

---

## Part 2 — Installing the key on Batocera (pick the easiest path)

### Path A — From your PC, no terminal (recommended for beginners)

Batocera shares its folders on your home network:

1. Turn on the Batocera box. From your PC (same Wi-Fi/wired network) open the file explorer:
   - **Windows**: type `\\BATOCERA\share` in the address bar and press Enter
   - **Mac**: Finder → Go → Connect to Server → `smb://batocera.local/share`
2. Enter the folder **`system`** → **`SudoBat`** → **`state`** (if `state` doesn't exist, create it).
3. Create a text file in there named exactly **`groq_key.txt`**.
4. Open it, paste **only the key** (the line starting with `gsk_`, no spaces, no extra lines) and save.

### Path B — With one command (via SSH or the Batocera terminal)

If you know how to SSH in (`ssh root@batocera.local`, default password `linux`):

```bash
cd /userdata/system/SudoBat
python3 -m sudobat.cli key set gsk_YOUR_KEY
```

The command checks the key is well-formed and stores it in the right place with the right permissions.

---

## Part 3 — Verifying it works

From the terminal (network required):

```bash
python3 -m sudobat.cli key         # shows the status: configured or not
python3 -m sudobat.cli key test    # makes a real test call to Groq
```

If `key test` answers `OK`, the turbo is ready. Alternatively, open SudoBat → **Settings**: the **AI turbo (Groq)** row should say *active*.

From now on, when a game crashes in a way SudoBat doesn't know, the Diagnose screen will offer the turbo option (SELECT button).

---

## FAQ

**How much does it cost?** Nothing. Groq's free tier has per-minute/per-day request limits, but SudoBat makes **one** call only when there's an unknown crash — and thanks to distillation each crash is paid once, then it's recognized offline forever.

**Where does my key end up?** Only on your Batocera box, in `state/groq_key.txt` (excluded from the repository, restricted permissions). It's sent to no one except Groq, to authenticate the calls.

**What gets sent to Groq?** Only when the turbo runs: the tail of the crash log (~40 lines), the CPU/GPU model and the game title. No key = no traffic at all.

**How do I remove it?** `python3 -m sudobat.cli key remove`, or delete the `state/groq_key.txt` file. SudoBat keeps working on the offline engine alone.

**I lost my key / published it by mistake.** Go to console.groq.com → API Keys, revoke the old one and create a new one. Then repeat Part 2.
