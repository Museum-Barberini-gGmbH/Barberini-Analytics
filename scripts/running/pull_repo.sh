#!/bin/bash
set -e
cd "$(dirname "$0")"
git pull
../migrations/migrate.sh
