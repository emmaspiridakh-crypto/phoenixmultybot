# Panamera — Οδηγίες Εγκατάστασης

## 1. Discord Developer Portal

1. Πήγαινε στο https://discord.com/developers/applications
2. Δημιούργησε νέο application (ή χρησιμοποίησε το υπάρχον Panamera application σου)
3. Tab **"Bot"**:
   - Αντίγραψε το **Token** (θα το βάλεις σαν `DISCORD_TOKEN`)
   - Ενεργοποίησε τα 3 **Privileged Gateway Intents**: `SERVER MEMBERS INTENT`, `MESSAGE CONTENT INTENT`, `PRESENCE INTENT`
4. Tab **"Emojis"**:
   - Ανέβασε τα δικά σου emojis (checkmark, error, warning, logo κλπ)
   - Σημείωσε τα IDs που σου δίνει
   - Άνοιξε `utils/emojis.py` και αντικατέστησε τα placeholder IDs (`BOT_SUCCESS`, `BOT_ERROR`, `BOT_WARNING`, `BOT_LOGO`) με τα πραγματικά
5. Tab **"OAuth2" → "URL Generator"**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: Administrator (πιο απλό) ή τουλάχιστον: Manage Roles, Manage Channels, Manage Nicknames, Kick Members, Ban Members, Moderate Members, Manage Messages, Send Messages, View Channels, Connect, Move Members
   - Αντίγραψε το URL που δημιουργείται → αυτό είναι το invite link του bot

## 2. Turso (δωρεάν database)

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth login
turso db create panamera
turso db show panamera --url
turso db tokens create panamera
```

Κράτησε το URL (`libsql://...`) και το token — θα τα βάλεις σαν `TURSO_DATABASE_URL` και `TURSO_AUTH_TOKEN`.

## 3. Render — Web Service

1. https://dashboard.render.com → **New → Web Service**
2. Σύνδεσε το repo σου (ανέβασε πρώτα αυτό το φάκελο σε ένα GitHub repo)
3. **Language**: Docker
4. **Instance Type**: Free
5. **Environment Variables**:
   ```
   DISCORD_TOKEN=...
   TURSO_DATABASE_URL=libsql://...
   TURSO_AUTH_TOKEN=...
   BOT_DISPLAY_NAME=Panamera
   ```
6. Deploy

**Δεν χρειάζεται Persistent Disk** — όλα τα δεδομένα ζουν στο Turso, εκτός Render.

## 4. Κράτα το bot 24/7 (Render Free κάνει spin down μετά από ~15')

1. Μετά το deploy, θα έχεις URL τύπου `https://panamera.onrender.com`
2. Πήγαινε στο https://uptimerobot.com (δωρεάν λογαριασμός)
3. **Add New Monitor** → HTTP(s) → URL: `https://panamera.onrender.com`
4. Interval: 5 λεπτά

## 5. Πρώτο τρέξιμο σε server

1. Πρόσκλησε το bot στον server σου με το invite link από το βήμα 1
2. Το bot θα φτιάξει αυτόματα ένα κανάλι `#panamera-setup` με welcome μήνυμα
3. Ο **πραγματικός owner** του server τρέχει: `/setserver owner @κάποιος` (μπορεί να διαλέξει και τον εαυτό του)
4. Ο installer τρέχει `/install` για να φτιάξει τη βασική υποδομή (roles, logs, temp voice, server status)
5. Μετά, `/ticketcategory add`, `/application create` κλπ για να χτίσει το περιεχόμενο του δικού του server

## 6. Αλλαγή ονόματος/avatar/banner του bot (global, ίδιο παντού)

Developer Portal → Bot tab → Username/Icon/Banner. Rate limit ~2 αλλαγές/ώρα από το Discord.
Το εμφανιζόμενο κείμενο "Panamera" στα panels αλλάζει μέσω του `BOT_DISPLAY_NAME` env var, χωρίς να αγγίξεις κώδικα.

## 7. Δομή project

```
main.py                  Entry point, φορτώνει τα cogs, συνδέεται στο Turso
config.py                Σταθερές (BOT_DISPLAY_NAME, retention days, λίστα cogs)
keep_alive.py            Flask server για UptimeRobot ping (port 10000)
utils/
  db.py                  Turso σύνδεση + όλο το schema/queries
  permissions.py         Owner/Installer/Granted σύστημα
  emojis.py               Bot Identity emojis + Server Content emoji slots
  components.py            Components V2 panel builder helpers
  embeds.py                 Log embed helper
cogs/
  setup.py                  on_guild_join/remove, /setserver, retention job
  install.py                 /install, /uninstall
  permissions_cog.py          /permissions grant/revoke/list
  settings.py                  /set, /settings
  ticketcategory.py             /ticketcategory ...
  tickets.py                     panels + open/close ticket flow
  application_builder.py          /application ... (question builder)
  applications.py                  applicant flow, accept/deny, lock/unlock
  moderation.py                     ban/kick/timeout/say/dmall
  logging_events.py                  join/leave/roles/channels/messages/voice logs
  autorole.py                         auto-role σε νέο μέλος
  temp_voice.py                        join-to-create voice channels
  staff_activity.py                     on-duty tracking + leaderboard
  suggestions.py                        auto-reactions σε suggestions channel
  server_status.py                       live μετρητές σε voice channels
  invite_tracking.py                      ποιος κάλεσε ποιον
  help.py                                  /help
```

## 8. Επόμενα βήματα / σημειώσεις

- Το bot χρειάζεται να είναι **πάνω από** τους ρόλους που διαχειρίζεται (role hierarchy), αλλιώς θα αποτυγχάνουν οι εντολές roles/moderation σε high-ranked μέλη.
- Το `/settings validate` τρέχεται χειροκίνητα οποτεδήποτε θες — καλό είναι να το τρέχεις μετά από κάθε μαζική αλλαγή στον server (διαγραφή roles/channels/emojis).
- Τα application emojis (βήμα 1.4) πρέπει να μπουν **πριν** πας live, αλλιώς τα error/warning/success μηνύματα δεν θα έχουν εικονίδιο.
