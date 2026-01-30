#!/bin/sh
# Remove generated data/media outputs produced by sync/build scripts.

set -eu

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

TARGETS="
docs/data/posts.json
docs/data/meta.json
docs/data/config.json
docs/data/pages
docs/assets/media
docs/assets/media/thumbs
docs/assets/channel_avatar.jpg
docs/favicon.ico
docs/favicon-32.png
docs/apple-touch-icon.png
docs/feed.xml
docs/atom.xml
docs/sitemap.xml
docs/robots.txt
docs/static
"

for path in $TARGETS; do
  if [ -e "$path" ] || [ -L "$path" ]; then
    rm -rf -- "$path"
    printf 'Removed %s\n' "$path"
  else
    printf 'Skip (not found): %s\n' "$path"
  fi
done
