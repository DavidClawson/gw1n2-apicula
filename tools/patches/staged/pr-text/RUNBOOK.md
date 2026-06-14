# GW1N-2 upstream submission — runbook (GitHub route)

Paste-ready bodies live next to this file. Commands assume macOS (note the
`sed -i ''` form) and `gh auth login` done. Fork both repos first:
```bash
gh repo fork YosysHQ/apicula  --clone=false
gh repo fork YosysHQ/nextpnr --clone=false
```

```bash
# ---- config ----
GH=<your-github-username>
S=/Users/david/Projects/RESEARCH/gw1n2-apicula/tools/patches/staged
PT=$S/pr-text
```

## Step 1 — Tracking issue (do now)
```bash
ISSUE_URL=$(gh issue create --repo YosysHQ/apicula \
  --title "Add GW1N-2 support" --body-file $PT/00-issue.md)
echo "$ISSUE_URL"
ISSUE=${ISSUE_URL##*/}
# bake the issue number into the PR bodies
sed -i '' "s/#ISSUE/#$ISSUE/g" $PT/pr1-dat.md $PT/pr2-build.md $PT/pr3-io.md $PT/pr-nextpnr.md
```
Then wait for a reply. yrabbit may say "just send the PRs" or have a staging
preference. Everything below is ready when you get the nod.

## Step 2 — Clean clone of your apicula fork
```bash
cd ~ && git clone https://github.com/$GH/apicula && cd apicula
git remote add upstream https://github.com/YosysHQ/apicula
git fetch upstream
```

## Step 3 — PR1: partType-1 .dat (standalone, open first)
```bash
git checkout -b gw1n2-dat upstream/master
git apply $S/01-dat_parser-parttype1.patch     # if it complains, try: git apply --3way
git commit -am "dat_parser: support partType-1 .dat files"
git push -u origin gw1n2-dat
PR1_URL=$(gh pr create --repo YosysHQ/apicula --base master --head $GH:gw1n2-dat \
  --title "dat_parser: support partType-1 .dat files" --body-file $PT/pr1-dat.md)
echo "$PR1_URL"; PR1=${PR1_URL##*/}
sed -i '' "s/#PR1/#$PR1/g" $PT/pr2-build.md $PT/pr3-io.md
```

## Step 4 — PR2 + PR3 (stacked; open after PR1 merges, OR when yrabbit oks stacking)
> Note: opened against `master` while PR1 is still open, PR2's diff will *include*
> PR1's commit until PR1 merges, then narrows automatically. That's normal for
> stacked PRs — or just wait for PR1 to merge, then `git fetch upstream` and rebase.
```bash
git checkout -b gw1n2-build gw1n2-dat
git apply $S/02-recognize-and-build.patch
git commit -am "GW1N-2. Recognize device + build chipdb"
git push -u origin gw1n2-build
PR2_URL=$(gh pr create --repo YosysHQ/apicula --base master --head $GH:gw1n2-build \
  --title "GW1N-2. Recognize device + build chipdb" --body-file $PT/pr2-build.md)
echo "$PR2_URL"; PR2=${PR2_URL##*/}
sed -i '' "s/#PR2/#$PR2/g" $PT/pr3-io.md

git checkout -b gw1n2-io gw1n2-build
git apply $S/03-pinout-io-osc.patch
git commit -am "GW1N-2. Pinout, IO config, OSC"
git push -u origin gw1n2-io
gh pr create --repo YosysHQ/apicula --base master --head $GH:gw1n2-io \
  --title "GW1N-2. Pinout, IO config, OSC" --body-file $PT/pr3-io.md
```

## Step 5 — nextpnr PR (after the apicula PRs land)
```bash
cd ~ && git clone https://github.com/$GH/nextpnr && cd nextpnr
git remote add upstream https://github.com/YosysHQ/nextpnr
git fetch upstream
git checkout -b gw1n2 upstream/master
git apply $S/nextpnr/01-gw1n2-arch-gen.patch
git commit -am "[himbaechel/gowin] Add GW1N-2 device"
git push -u origin gw1n2
gh pr create --repo YosysHQ/nextpnr --base master --head $GH:gw1n2 \
  --title "[himbaechel/gowin] Add GW1N-2 device" --body-file $PT/pr-nextpnr.md
```

## Step 6 — example + CI wiring (last, coordinated)
The `examples/gw1n2/` files (`$S/examples-gw1n2/`) go in the apicula repo. The
files are harmless on their own; the `toolchain.yml` matrix entry
`{target: gw1n2, dir: examples/gw1n2}` must be added **only after** the nextpnr PR
merges and apicula bumps its pinned nextpnr commit — otherwise CI builds examples
against an upstream nextpnr that doesn't know GW1N-2 yet and goes red. Coordinate the
timing (and the board/part naming) with yrabbit/gatecat; they manage the nextpnr pin.

## If `git apply` fails (upstream moved)
```bash
git apply --3way $S/<patch>     # 3-way merge against current master
# or eyeball the reject and apply by hand; the diffs are tiny
```

## Etiquette
A PR is a real merge request: expect possible review comments. To address them,
edit, `git commit --amend` (or add a commit), `git push --force-with-lease` — the PR
updates itself. No CLA / sign-off. Keep additions MIT.
