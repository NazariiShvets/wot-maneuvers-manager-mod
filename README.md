# Maneuvers Manager mod

World of Tanks hangar mod that signs you into [Maneuvers Manager](https://wot-maneuvers-manager.vercel.app/).

The site is where clan Maneuvers are read: teams, battles, fame, resets, and Repair Parts. This repository is the game-side sign-in. From the hangar it asks the client for a short-lived Wargaming access token and opens the site with that token, plus `periphery_id` and `spa_id`. Your password stays in the game. The mod adds a menu item and opens the browser.

Built for World of Tanks 2.4.1.0. After a game update, copy the `.wotmod` into the new version's `mods` folder.

## Install

1. Build the mod, or take a release `.wotmod`.
2. Put `eagle.maneuvers-manager_<version>.wotmod` in `World_of_Tanks/mods/<game version>/`.
3. Start the game. In the hangar menu, choose **Maneuvers Manager** and confirm. The game opens your browser already signed in.

The session lasts only while the game is running. Close the client and open the mod from the hangar again next time.

The sign-in URL carries the access token, so it can remain in browser history. The token stops working when the game closes.

## Build

From the repo root, on Windows:

```bat
build.bat -v 1.0.1
```

The package is `packages/wot-maneuvers-manager-mod`. Output is `dist/eagle.maneuvers-manager_1.0.1.wotmod`.

The build needs [7-Zip](https://www.7-zip.org/) at `C:\Program Files\7-Zip\7z.exe`, Python 2.7 at `C:\Python27\python.exe` (to compile the client script), and Python 3 on `PATH` as `py -3` (to compile the hangar menu strings).

`AUTH_ORIGIN` in `packages/wot-maneuvers-manager-mod/build.cfg` is written into the script at build time. The shipped value is `https://wot-maneuvers-manager.vercel.app`, so the menu opens `https://wot-maneuvers-manager.vercel.app/auth`.

## What the site receives

| Query param   | Source                                      |
| ------------- | ------------------------------------------- |
| `accessToken` | The game's own short-lived web access token |
| `periphery_id`| Current realm connection                    |
| `spa_id`      | Your account id                             |

The site uses the token to read your clan's Maneuvers journals. It does not repair, reset, buy, or change anything in the game. Details are on the [Maneuvers Manager](https://wot-maneuvers-manager.vercel.app/) page.

This is an unofficial tool. It is not made or endorsed by Wargaming.
