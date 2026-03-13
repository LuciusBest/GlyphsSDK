#!/bin/bash

FIGMA_TOKEN="TON_TOKEN"
FILE_ID="is6LZSMBRNfATpbhKbwGfO"

curl -H "X-Figma-Token: $FIGMA_TOKEN" \
"https://api.figma.com/v1/files/$FILE_ID" \
-o design/figma.json

echo "Figma export updated."
