#!/bin/sh

VERSION=0.5.1
BUCKET=maven-staging
#BUCKET=maven-production
DRY_RUN="--dry-run"
#DRY_RUN=""
python script.py --release-url "https://github.com/mozilla-mobile/gradle-apilint/releases/download/$VERSION/maven.zip" \
                                     --script-config apilint_config.json \
                                     --bucket $BUCKET \
                                     --version "$VERSION" \
                                     $DRY_RUN
